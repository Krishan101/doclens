import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sentence_transformers import SentenceTransformer

from app.models.database import Document, Chunk
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
) -> Document:
    """Create a document record in 'processing' state."""
    doc = Document(
        user_id=user_id,
        filename=filename,
        file_type=file_type,
        file_size=file_size,
        status="processing",
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)
    return doc


async def process_document(
    db: AsyncSession,
    document_id: UUID,
    file_bytes: bytes,
    file_type: str,
    embedding_model: SentenceTransformer,
):
    """Full processing pipeline: extract → validate → chunk → embed → store."""
    try:
        # Get document
        result = await db.execute(select(Document).where(Document.id == document_id))
        doc = result.scalar_one_or_none()
        if not doc:
            logger.error(f"Document {document_id} not found")
            return

        # 1. Extract text
        if file_type == "pdf":
            extraction = extract_text_from_pdf(file_bytes)
        else:
            extraction = extract_text_from_txt(file_bytes)

        if extraction.error:
            doc.status = "failed"
            doc.error_msg = f"Extraction failed: {extraction.error}"
            await db.commit()
            return

        # 2. Validate
        if extraction.is_image_only:
            doc.status = "failed"
            doc.error_msg = "This PDF appears to be image-based. Only text-based PDFs are supported."
            await db.commit()
            return

        if not extraction.raw_text.strip():
            doc.status = "empty"
            doc.error_msg = "No text content found in the document."
            await db.commit()
            return

        # 3. Store raw text
        doc.raw_text = extraction.raw_text
        doc.page_count = extraction.page_count

        # 4. Chunk
        chunks = chunk_text(extraction.raw_text, extraction.tables)
        if not chunks:
            doc.status = "empty"
            doc.error_msg = "Document produced no usable text chunks."
            await db.commit()
            return

        # 5. Embed
        chunk_texts = [c.content for c in chunks]
        embeddings = embed_texts(embedding_model, chunk_texts)

        # 6. Store chunks
        for chunk_data, embedding in zip(chunks, embeddings):
            chunk = Chunk(
                document_id=document_id,
                content=chunk_data.content,
                chunk_type=chunk_data.chunk_type,
                chunk_index=chunk_data.chunk_index,
                page_number=chunk_data.page_number,
                char_start=chunk_data.char_start,
                char_end=chunk_data.char_end,
                token_count=chunk_data.token_count,
                embedding=embedding,
            )
            db.add(chunk)

        doc.status = "ready"
        await db.commit()
        logger.info(f"Document {document_id} processed: {len(chunks)} chunks")

    except Exception as e:
        logger.error(f"Error processing document {document_id}: {e}")
        try:
            result = await db.execute(select(Document).where(Document.id == document_id))
            doc = result.scalar_one_or_none()
            if doc:
                doc.status = "failed"
                doc.error_msg = f"Processing error: {str(e)[:200]}"
                await db.commit()
        except Exception:
            pass


async def get_user_documents(db: AsyncSession, user_id: UUID) -> list[dict]:
    """Get all documents for a user with chunk counts."""
    result = await db.execute(
        select(Document)
        .where(Document.user_id == user_id)
        .order_by(Document.created_at.desc())
    )
    docs = result.scalars().all()

    doc_list = []
    for doc in docs:
        chunk_count_result = await db.execute(
            select(func.count(Chunk.id)).where(Chunk.document_id == doc.id)
        )
        chunk_count = chunk_count_result.scalar() or 0

        doc_list.append({
            "id": doc.id,
            "filename": doc.filename,
            "file_type": doc.file_type,
            "file_size": doc.file_size,
            "page_count": doc.page_count,
            "status": doc.status,
            "error_msg": doc.error_msg,
            "chunk_count": chunk_count,
            "created_at": doc.created_at,
        })

    return doc_list


async def get_document(db: AsyncSession, document_id: UUID, user_id: UUID) -> dict | None:
    """Get a single document by ID, scoped to user."""
    result = await db.execute(
        select(Document).where(Document.id == document_id, Document.user_id == user_id)
    )
    doc = result.scalar_one_or_none()
    if not doc:
        return None

    chunk_count_result = await db.execute(
        select(func.count(Chunk.id)).where(Chunk.document_id == doc.id)
    )
    chunk_count = chunk_count_result.scalar() or 0

    return {
        "id": doc.id,
        "filename": doc.filename,
        "file_type": doc.file_type,
        "file_size": doc.file_size,
        "page_count": doc.page_count,
        "status": doc.status,
        "error_msg": doc.error_msg,
        "chunk_count": chunk_count,
        "created_at": doc.created_at,
    }


async def get_document_chunks(db: AsyncSession, document_id: UUID, user_id: UUID) -> list[dict] | None:
    """Get all chunks for a document, verifying user ownership."""
    # Verify ownership
    result = await db.execute(
        select(Document).where(Document.id == document_id, Document.user_id == user_id)
    )
    doc = result.scalar_one_or_none()
    if not doc:
        return None

    result = await db.execute(
        select(Chunk)
        .where(Chunk.document_id == document_id)
        .order_by(Chunk.chunk_index)
    )
    chunks = result.scalars().all()

    return [
        {
            "id": c.id,
            "content": c.content,
            "chunk_type": c.chunk_type,
            "chunk_index": c.chunk_index,
            "page_number": c.page_number,
            "char_start": c.char_start,
            "char_end": c.char_end,
        }
        for c in chunks
    ]


async def delete_document(db: AsyncSession, document_id: UUID, user_id: UUID) -> bool:
    """Delete a document (cascades to chunks and queries)."""
    result = await db.execute(
        select(Document).where(Document.id == document_id, Document.user_id == user_id)
    )
    doc = result.scalar_one_or_none()
    if not doc:
        return False

    await db.delete(doc)
    await db.commit()
    return True
