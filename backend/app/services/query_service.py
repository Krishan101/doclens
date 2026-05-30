import time
import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text
from sentence_transformers import SentenceTransformer
import redis.asyncio as aioredis

from app.config import get_settings
from app.models.database import Document, Chunk, Query
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
    result = await db.execute(
        select(Document).where(Document.id == document_id, Document.user_id == user_id)
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise ValueError("Document not found")
    if doc.status != "ready":
        raise ValueError(f"Document is not ready (status: {doc.status})")

    # 1. Enrich vague queries
    enriched = await _enrich_query(db, user_id, document_id, question)

    # 2. Embed the question (with Redis cache)
    query_embedding = await embed_with_cache(embedding_model, enriched, redis_client)

    # 3. Vector similarity search
    retrieved = await _vector_search(db, document_id, query_embedding, limit=5)

    # 4. Relevance gate
    if not retrieved or retrieved[0]["similarity"] < settings.relevance_threshold:
        # No good matches — don't call LLM
        confidence = "none"
        answer = "I couldn't find relevant information in the document for this question. Try rephrasing or asking about a specific topic covered in the document."
        query_record = Query(
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
        db.add(query_record)
        await db.commit()
        await db.refresh(query_record)

        budget_status = await LLMService(redis_client).budget.get_budget_status()
        return _format_response(query_record, [], budget_status)

    # 5. Trim context to token budget
    trimmed_chunks = _trim_to_budget(retrieved, settings.max_context_tokens)

    # 6. Determine confidence
    top_similarity = trimmed_chunks[0]["similarity"]
    if top_similarity > 0.5:
        confidence = "high"
    elif top_similarity > 0.3:
        confidence = "low"
    else:
        confidence = "none"

    # 7. Generate answer with Groq
    llm = LLMService(redis_client)
    llm_result = await llm.generate_answer(
        question=enriched,
        context_chunks=trimmed_chunks,
    )

    # 8. Store query
    latency_ms = int((time.time() - start_time) * 1000)
    query_record = Query(
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
    db.add(query_record)
    await db.commit()
    await db.refresh(query_record)

    budget_status = await llm.budget.get_budget_status()
    return _format_response(query_record, trimmed_chunks, budget_status)


async def get_query_history(
    db: AsyncSession,
    user_id: UUID,
    document_id: UUID,
) -> list[dict]:
    """Get past queries for a document."""
    result = await db.execute(
        select(Query)
        .where(Query.document_id == document_id, Query.user_id == user_id)
        .order_by(Query.created_at.desc())
        .limit(20)
    )
    queries = result.scalars().all()

    return [
        {
            "id": q.id,
            "question": q.question,
            "answer": q.answer,
            "confidence": q.confidence,
            "source_count": len(q.retrieved_chunk_ids) if q.retrieved_chunk_ids else 0,
            "created_at": q.created_at,
        }
        for q in queries
    ]


async def _enrich_query(
    db: AsyncSession,
    user_id: UUID,
    document_id: UUID,
    question: str,
) -> str:
    """Enrich vague queries by prepending last Q&A context."""
    words = question.strip().split()
    pronouns = {"it", "this", "that", "they", "them", "more", "those", "these"}

    is_vague = len(words) < 5 or any(w.lower() in pronouns for w in words)

    if not is_vague:
        return question

    # Fetch last query for this document
    result = await db.execute(
        select(Query)
        .where(Query.document_id == document_id, Query.user_id == user_id)
        .order_by(Query.created_at.desc())
        .limit(1)
    )
    last_query = result.scalar_one_or_none()

    if last_query:
        return f"Previous Q: {last_query.question}\nPrevious A: {last_query.answer[:200]}\nFollow-up: {question}"

    return question


async def _vector_search(
    db: AsyncSession,
    document_id: UUID,
    query_embedding: list[float],
    limit: int = 5,
) -> list[dict]:
    """Search pgvector for similar chunks within a document."""
    embedding_str = "[" + ",".join(str(x) for x in query_embedding) + "]"

    sql = text("""
        SELECT id, content, chunk_type, page_number, char_start, char_end,
               1 - (embedding <=> CAST(:embedding AS vector)) AS similarity
        FROM chunks
        WHERE document_id = CAST(:doc_id AS uuid)
        ORDER BY embedding <=> CAST(:embedding AS vector)
        LIMIT :limit
    """)

    result = await db.execute(sql, {
        "embedding": embedding_str,
        "doc_id": str(document_id),
        "limit": limit,
    })

    rows = result.fetchall()
    return [
        {
            "id": row.id,
            "content": row.content,
            "chunk_type": row.chunk_type,
            "page_number": row.page_number,
            "char_start": row.char_start,
            "char_end": row.char_end,
            "similarity": round(float(row.similarity), 4),
        }
        for row in rows
    ]


def _trim_to_budget(chunks: list[dict], max_tokens: int) -> list[dict]:
    """Trim chunks to fit within token budget."""
    trimmed = []
    total_tokens = 0

    for chunk in chunks:
        chunk_tokens = len(chunk["content"].split()) * 1.3  # rough estimate
        if total_tokens + chunk_tokens > max_tokens and trimmed:
            break
        trimmed.append(chunk)
        total_tokens += chunk_tokens

    return trimmed


def _format_response(query: Query, sources: list[dict], budget: dict) -> dict:
    """Format the final response."""
    return {
        "id": query.id,
        "question": query.question,
        "answer": query.answer,
        "confidence": query.confidence,
        "sources": [
            {
                "chunk_id": s["id"],
                "content": s["content"],
                "chunk_type": s["chunk_type"],
                "page_number": s["page_number"],
                "char_start": s["char_start"],
                "char_end": s["char_end"],
                "similarity": s["similarity"],
            }
            for s in sources
        ],
        "latency_ms": query.latency_ms,
        "model_used": query.llm_model,
        "budget": {
            "remaining_pct": budget["remaining_pct"],
            "model_tier": "primary" if budget["active_model"] == budget["primary_model"] else "fallback",
            "daily_reset_utc": budget["resets_at"],
        },
        "created_at": query.created_at,
    }
