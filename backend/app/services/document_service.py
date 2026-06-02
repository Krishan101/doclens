import asyncio
import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sentence_transformers import SentenceTransformer
import redis.asyncio as aioredis

from app.repositories import document_repo, chunk_repo
from app.utils.text_extraction import extract_text_from_pdf, extract_text_from_txt
from app.utils.chunking import chunk_text
from app.utils.embeddings import embed_texts

logger = logging.getLogger(__name__)


async def create_document(
    db: AsyncSession,
    user_id: UUID,
    filename: str,
    file_type: str,
    file_size: int,
):
    return await document_repo.create(db, user_id, filename, file_type, file_size)


async def process_document(
    db: AsyncSession,
    document_id: UUID,
    file_bytes: bytes,
    file_type: str,
    embedding_model: SentenceTransformer,
    redis_client: aioredis.Redis | None = None,
):
    """Full pipeline: extract → validate → chunk → embed → store → summarize."""
    try:
        # 1. Extract text
        if file_type == "pdf":
            extraction = extract_text_from_pdf(file_bytes)
        else:
            extraction = extract_text_from_txt(file_bytes)

        if extraction.error:
            await document_repo.update_status(db, document_id, "failed",
                                              error_msg=f"Extraction failed: {extraction.error}")
            return

        # 2. Validate
        if extraction.is_image_only:
            await document_repo.update_status(db, document_id, "failed",
                                              error_msg="This PDF appears to be image-based. Only text-based PDFs are supported.")
            return

        if not extraction.raw_text.strip():
            await document_repo.update_status(db, document_id, "empty",
                                              error_msg="No text content found in the document.")
            return

        # 3. Store raw text + page count
        await document_repo.update_status(db, document_id, "processing",
                                          raw_text=extraction.raw_text,
                                          page_count=extraction.page_count)

        # 4. Chunk
        chunks = chunk_text(extraction.raw_text, extraction.tables,
                           page_offsets=extraction.page_offsets)
        if not chunks:
            await document_repo.update_status(db, document_id, "empty",
                                              error_msg="Document produced no usable text chunks.")
            return

        # 5. Embed (in thread pool to avoid blocking event loop)
        chunk_texts = [c.content for c in chunks]
        loop = asyncio.get_event_loop()
        embeddings = await loop.run_in_executor(
            None,
            lambda: embed_texts(embedding_model, chunk_texts)
        )

        # 6. Store chunks via repo
        await chunk_repo.bulk_insert(db, document_id, chunks, embeddings)

        # 7. Generate AI summary
        summary = await _generate_summary(chunks, redis_client)

        # 8. Mark ready
        await document_repo.update_status(db, document_id, "ready", summary=summary)
        await db.commit()
        logger.info(f"Document {document_id} processed: {len(chunks)} chunks")

    except Exception as e:
        logger.error(f"Error processing document {document_id}: {e}")
        try:
            doc = await document_repo.get_by_id(db, document_id, user_id=None)
            if doc:
                await document_repo.update_status(db, document_id, "failed",
                                                  error_msg=f"Processing error: {str(e)[:200]}")
        except Exception:
            pass


async def get_user_documents(db: AsyncSession, user_id: UUID) -> list[dict]:
    docs = await document_repo.list_by_user(db, user_id)
    result = []
    for doc in docs:
        chunk_count = await document_repo.get_chunk_count(db, doc.id)
        result.append({
            "id": doc.id, "filename": doc.filename, "file_type": doc.file_type,
            "file_size": doc.file_size, "page_count": doc.page_count,
            "status": doc.status, "error_msg": doc.error_msg, "summary": doc.summary,
            "chunk_count": chunk_count, "created_at": doc.created_at,
        })
    return result


async def get_document(db: AsyncSession, document_id: UUID, user_id: UUID) -> dict | None:
    doc = await document_repo.get_by_id(db, document_id, user_id)
    if not doc:
        return None
    chunk_count = await document_repo.get_chunk_count(db, doc.id)
    return {
        "id": doc.id, "filename": doc.filename, "file_type": doc.file_type,
        "file_size": doc.file_size, "page_count": doc.page_count,
        "status": doc.status, "error_msg": doc.error_msg, "summary": doc.summary,
        "chunk_count": chunk_count, "created_at": doc.created_at,
    }


async def get_document_chunks(db: AsyncSession, document_id: UUID, user_id: UUID) -> list[dict] | None:
    doc = await document_repo.get_by_id(db, document_id, user_id)
    if not doc:
        return None
    chunks = await chunk_repo.list_by_document(db, document_id)
    # Sort: text chunks by char_start, tables by page_number (fixes table-on-top issue)
    sorted_chunks = sorted(chunks, key=lambda c: (c.page_number or 0, c.char_start if c.chunk_type == 'text' else c.char_start))
    return [
        {
            "id": c.id, "content": c.content, "chunk_type": c.chunk_type,
            "chunk_index": c.chunk_index, "page_number": c.page_number,
            "char_start": c.char_start, "char_end": c.char_end,
        }
        for c in sorted_chunks
    ]


async def delete_document(db: AsyncSession, document_id: UUID, user_id: UUID) -> bool:
    return await document_repo.delete(db, document_id, user_id)


async def _generate_summary(chunks, redis_client) -> str | None:
    """Generate a 2-3 sentence summary of the document using the LLM."""
    if not redis_client or not chunks:
        return None

    try:
        from app.services.llm_service import LLMService

        context = "\n".join([c.content for c in chunks[:3]])[:1500]
        llm = LLMService(redis_client)

        model = await llm.budget.select_model()
        await llm.budget.pre_request_throttle()

        response = await llm.client.chat.completions.create(
            model=model,
            messages=[{
                "role": "user",
                "content": f"Summarize this document in 2-3 sentences. Be specific about what the document covers, key topics, and any important numbers.\n\nDocument:\n{context}"
            }],
            temperature=0.3,
            max_tokens=150,
        )

        usage = response.usage
        await llm.budget.record_usage(
            model=model,
            prompt_tokens=usage.prompt_tokens if usage else 0,
            completion_tokens=usage.completion_tokens if usage else 0,
        )

        return response.choices[0].message.content.strip()

    except Exception as e:
        logger.error(f"Failed to generate summary: {e}")
        return None
