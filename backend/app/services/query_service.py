import re
import time
import asyncio
import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sentence_transformers import SentenceTransformer
import redis.asyncio as aioredis

from app.config import get_settings
from app.models.database import Document, Chunk, Query
from app.repositories import document_repo, chunk_repo, query_repo
from app.services.llm_service import LLMService
from app.utils.embeddings import embed_with_cache

settings = get_settings()
logger = logging.getLogger(__name__)


async def ask_question(
    db: AsyncSession,
    user_id: UUID,
    document_id: UUID,
    question: str,
    embedding_model: SentenceTransformer,
    redis_client: aioredis.Redis,
) -> dict:
    """Full RAG pipeline: enrich → embed → retrieve → gate → generate → store."""
    start_time = time.time()

    # Verify document ownership and readiness
    doc = await document_repo.get_by_id(db, document_id, user_id)
    if not doc:
        raise ValueError("Document not found")
    if doc.status != "ready":
        raise ValueError(f"Document is not ready (status: {doc.status})")

    # 1. Enrich vague queries
    enriched = await _enrich_query(db, user_id, document_id, question)

    # 2. Embed the question (with Redis cache, in thread pool)
    loop = asyncio.get_event_loop()
    query_embedding = await embed_with_cache(embedding_model, enriched, redis_client)

    # 3. Vector similarity search via repo
    retrieved = await chunk_repo.vector_search(db, document_id, query_embedding, limit=5)

    # Debug: log similarity scores
    if retrieved:
        scores = [(r["similarity"], r["content"][:60]) for r in retrieved]
        logger.info(f"Query: '{question}' | Top scores: {scores}")
    else:
        logger.info(f"Query: '{question}' | No chunks retrieved")

    # 4. Relevance gate
    if not retrieved or retrieved[0]["similarity"] < settings.relevance_threshold:
        confidence = "none"
        answer = "I couldn't find relevant information in the document for this question. Try rephrasing or asking about a specific topic covered in the document."
        query_record = await query_repo.create(
            db,
            user_id=user_id,
            document_id=document_id,
            question=question,
            enriched_question=enriched if enriched != question else None,
            answer=answer,
            confidence=confidence,
            retrieved_chunk_ids=[],
            llm_model="none",
            prompt_tokens=0,
            completion_tokens=0,
            latency_ms=int((time.time() - start_time) * 1000),
        )
        budget_status = await LLMService(redis_client).budget.get_budget_status()
        return _format_response(query_record, [], budget_status)

    # 5. Trim context to token budget
    trimmed_chunks = _trim_to_budget(retrieved, settings.max_context_tokens)

    # 6. Determine confidence (calibrated for all-MiniLM-L6-v2)
    top_similarity = trimmed_chunks[0]["similarity"]
    if top_similarity > 0.25:
        confidence = "high"
    elif top_similarity > 0.1:
        confidence = "low"
    else:
        confidence = "none"

    # 7. Generate answer with Groq
    llm = LLMService(redis_client)
    llm_result = await llm.generate_answer(
        question=enriched,
        context_chunks=trimmed_chunks,
    )

    # 8. Store query via repo
    latency_ms = int((time.time() - start_time) * 1000)
    query_record = await query_repo.create(
        db,
        user_id=user_id,
        document_id=document_id,
        question=question,
        enriched_question=enriched if enriched != question else None,
        answer=llm_result["answer"],
        confidence=confidence,
        retrieved_chunk_ids=[c["id"] for c in trimmed_chunks],
        llm_model=llm_result["model"],
        prompt_tokens=llm_result["prompt_tokens"],
        completion_tokens=llm_result["completion_tokens"],
        latency_ms=latency_ms,
    )

    budget_status = await llm.budget.get_budget_status()
    return _format_response(query_record, trimmed_chunks, budget_status)


async def ask_question_stream(
    db: AsyncSession,
    user_id: UUID,
    document_id: UUID,
    question: str,
    embedding_model: SentenceTransformer,
    redis_client: aioredis.Redis,
):
    """Streaming RAG pipeline — yields SSE events."""
    start_time = time.time()

    # Verify document
    doc = await document_repo.get_by_id(db, document_id, user_id)
    if not doc or doc.status != "ready":
        yield {"type": "error", "error": "Document not found or not ready"}
        return

    # Enrich + embed
    enriched = await _enrich_query(db, user_id, document_id, question)
    query_embedding = await embed_with_cache(embedding_model, enriched, redis_client)

    # Retrieve
    retrieved = await chunk_repo.vector_search(db, document_id, query_embedding, limit=5)

    # Relevance gate
    if not retrieved or retrieved[0]["similarity"] < settings.relevance_threshold:
        yield {
            "type": "sources",
            "sources": [],
            "confidence": "none",
        }
        yield {
            "type": "token",
            "token": "I couldn't find relevant information in the document for this question.",
        }
        yield {"type": "done", "query_id": None, "answer": "", "latency_ms": 0,
               "model_used": "none", "budget": None}
        return

    trimmed = _trim_to_budget(retrieved, settings.max_context_tokens)
    top_sim = trimmed[0]["similarity"]
    confidence = "high" if top_sim > 0.25 else "low" if top_sim > 0.1 else "none"

    # Emit sources first (before answer starts)
    yield {
        "type": "sources",
        "sources": [_format_source(c) for c in trimmed],
        "confidence": confidence,
    }

    # Stream LLM response
    llm = LLMService(redis_client)
    try:
        model = await llm.budget.select_model()
        await llm.budget.pre_request_throttle()
    except Exception as e:
        yield {"type": "error", "error": str(e)}
        return

    context_parts = []
    for i, chunk in enumerate(trimmed):
        page = chunk.get("page_number", "?")
        context_parts.append(f"[SOURCE {i+1}] (p.{page}): {chunk['content']}")

    from app.services.llm_service import SYSTEM_PROMPT

    full_answer = ""
    prompt_tokens = 0
    completion_tokens = 0

    try:
        stream = await llm.client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": "\n\n".join(context_parts) + f"\n\nQ: {question}"},
            ],
            temperature=0.1,
            max_tokens=settings.max_completion_tokens,
            stream=True,
        )

        async for chunk_resp in stream:
            token = chunk_resp.choices[0].delta.content or ""
            if token:
                full_answer += token
                yield {"type": "token", "token": token}

        # Record usage
        await llm.budget.record_usage(model=model, prompt_tokens=0, completion_tokens=len(full_answer.split()))

    except Exception as e:
        logger.error(f"Streaming error: {e}")
        yield {"type": "error", "error": "LLM streaming failed"}
        return

    # Store query
    latency_ms = int((time.time() - start_time) * 1000)
    query_record = await query_repo.create(
        db,
        user_id=user_id,
        document_id=document_id,
        question=question,
        enriched_question=enriched if enriched != question else None,
        answer=full_answer,
        confidence=confidence,
        retrieved_chunk_ids=[c["id"] for c in trimmed],
        llm_model=model,
        prompt_tokens=0,
        completion_tokens=len(full_answer.split()),
        latency_ms=latency_ms,
    )

    budget_status = await llm.budget.get_budget_status()
    yield {
        "type": "done",
        "query_id": str(query_record.id),
        "answer": full_answer,
        "latency_ms": latency_ms,
        "model_used": model,
        "budget": {
            "remaining_pct": budget_status["remaining_pct"],
            "model_tier": "primary" if model == settings.llm_primary_model else "fallback",
            "daily_reset_utc": budget_status["resets_at"],
        },
    }


async def get_query_history(
    db: AsyncSession,
    user_id: UUID,
    document_id: UUID,
) -> list[dict]:
    queries = await query_repo.list_by_document(db, document_id, user_id)
    return [
        {
            "id": q.id, "question": q.question, "answer": q.answer,
            "confidence": q.confidence,
            "source_count": len(q.retrieved_chunk_ids) if q.retrieved_chunk_ids else 0,
            "created_at": q.created_at,
        }
        for q in queries
    ]


async def generate_suggestions(
    db: AsyncSession,
    user_id: UUID,
    document_id: UUID,
    redis_client: aioredis.Redis,
) -> list[str]:
    """Generate 4 smart suggested questions from document content."""
    import json

    cache_key = f"suggestions:{document_id}"
    try:
        cached = await redis_client.get(cache_key)
        if cached:
            return json.loads(cached)
    except Exception:
        pass

    doc = await document_repo.get_by_id(db, document_id, user_id)
    if not doc or doc.status != "ready":
        raise ValueError("Document not found or not ready")

    chunks = await chunk_repo.list_by_document(db, document_id)
    if not chunks:
        return []

    context = "\n\n".join([c.content for c in chunks[:4]])

    llm = LLMService(redis_client)
    suggestion_prompt = f"""Based on this document content, generate exactly 4 insightful questions that a reader would want to ask. The questions should:
- Cover different aspects of the document (facts, analysis, comparisons, implications)
- Range from specific ("What is X?") to analytical ("How does X compare to Y?")
- Be answerable from the document content

Document content:
{context[:2000]}

Return ONLY the 4 questions, one per line, numbered 1-4. No other text."""

    try:
        model = await llm.budget.select_model()
        await llm.budget.pre_request_throttle()

        response = await llm.client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": suggestion_prompt}],
            temperature=0.7,
            max_tokens=300,
        )

        usage = response.usage
        await llm.budget.record_usage(
            model=model,
            prompt_tokens=usage.prompt_tokens if usage else 0,
            completion_tokens=usage.completion_tokens if usage else 0,
        )

        raw = response.choices[0].message.content
        questions = []
        for line in raw.strip().split("\n"):
            line = line.strip()
            if line and line[0].isdigit():
                q = line.lstrip("0123456789.)- ").strip()
                if q and len(q) > 10:
                    questions.append(q)

        suggestions = questions[:4]
        try:
            await redis_client.set(cache_key, json.dumps(suggestions), ex=3600)
        except Exception:
            pass
        return suggestions

    except Exception as e:
        logger.error(f"Failed to generate suggestions: {e}")
        return []


# === Private helpers ===

async def _enrich_query(
    db: AsyncSession,
    user_id: UUID,
    document_id: UUID,
    question: str,
) -> str:
    words = question.strip().split()
    pronouns = {"it", "this", "that", "they", "them", "more", "those", "these"}
    is_vague = len(words) < 5 or any(w.lower() in pronouns for w in words)

    if not is_vague:
        return question

    last_query = await query_repo.get_last_for_document(db, document_id, user_id)
    if last_query:
        return f"Previous Q: {last_query.question}\nPrevious A: {last_query.answer[:200]}\nFollow-up: {question}"
    return question


def _trim_to_budget(chunks: list[dict], max_tokens: int) -> list[dict]:
    trimmed = []
    total_tokens = 0
    for chunk in chunks:
        chunk_tokens = len(chunk["content"].split()) * 1.3
        if total_tokens + chunk_tokens > max_tokens and trimmed:
            break
        trimmed.append(chunk)
        total_tokens += chunk_tokens
    return trimmed


def _parse_cited_sources(answer: str) -> set[int]:
    matches = re.findall(r'\[SOURCE\s*(\d+)\]', answer, re.IGNORECASE)
    return {int(m) for m in matches}


def _format_source(s: dict) -> dict:
    return {
        "chunk_id": s["id"],
        "content": s["content"],
        "chunk_type": s["chunk_type"],
        "page_number": s["page_number"],
        "char_start": s["char_start"],
        "char_end": s["char_end"],
        "similarity": s["similarity"],
    }


def _format_response(query: Query, sources: list[dict], budget: dict) -> dict:
    cited_indices = _parse_cited_sources(query.answer)
    if cited_indices:
        filtered_sources = [s for i, s in enumerate(sources) if (i + 1) in cited_indices]
    else:
        filtered_sources = sources[:1] if sources else []

    return {
        "id": query.id,
        "question": query.question,
        "answer": query.answer,
        "confidence": query.confidence,
        "sources": [_format_source(s) for s in filtered_sources],
        "latency_ms": query.latency_ms,
        "model_used": query.llm_model,
        "budget": {
            "remaining_pct": budget["remaining_pct"],
            "model_tier": "primary" if budget["active_model"] == budget["primary_model"] else "fallback",
            "daily_reset_utc": budget["resets_at"],
        },
        "created_at": query.created_at,
    }
