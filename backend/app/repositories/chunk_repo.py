from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text

from app.models.database import Chunk
from app.utils.chunking import ChunkData


async def bulk_insert(
    db: AsyncSession,
    document_id: UUID,
    chunks: list[ChunkData],
    embeddings: list[list[float]],
) -> None:
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
    await db.flush()


async def list_by_document(db: AsyncSession, doc_id: UUID) -> list[Chunk]:
    result = await db.execute(
        select(Chunk)
        .where(Chunk.document_id == doc_id)
        .order_by(Chunk.chunk_index)
    )
    return list(result.scalars().all())


async def vector_search(
    db: AsyncSession,
    doc_id: UUID,
    embedding: list[float],
    limit: int = 5,
) -> list[dict]:
    embedding_str = "[" + ",".join(str(x) for x in embedding) + "]"

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
        "doc_id": str(doc_id),
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


async def hybrid_search(
    db: AsyncSession,
    doc_id: UUID,
    embedding: list[float],
    query_text: str,
    limit: int = 5,
) -> list[dict]:
    """Stub — delegates to vector_search for now."""
    return await vector_search(db, doc_id, embedding, limit)
