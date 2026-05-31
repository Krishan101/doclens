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
    """Hybrid search: combines vector similarity + BM25 full-text via Reciprocal Rank Fusion."""
    embedding_str = "[" + ",".join(str(x) for x in embedding) + "]"

    sql = text("""
        WITH vector_ranked AS (
            SELECT id,
                   1 - (embedding <=> CAST(:emb AS vector)) AS cosine_score,
                   ROW_NUMBER() OVER (
                     ORDER BY embedding <=> CAST(:emb AS vector)
                   ) AS vec_rank
            FROM chunks
            WHERE document_id = CAST(:doc_id AS uuid)
            LIMIT 20
        ),
        bm25_ranked AS (
            SELECT id,
                   ts_rank_cd(content_tsv,
                     plainto_tsquery('english', :qtext)) AS bm25_score,
                   ROW_NUMBER() OVER (
                     ORDER BY ts_rank_cd(content_tsv,
                       plainto_tsquery('english', :qtext)) DESC
                   ) AS bm25_rank
            FROM chunks
            WHERE document_id = CAST(:doc_id AS uuid)
              AND content_tsv @@ plainto_tsquery('english', :qtext)
            LIMIT 20
        ),
        combined AS (
            SELECT
                COALESCE(v.id, b.id) AS id,
                COALESCE(v.cosine_score, 0.0) AS cosine_score,
                COALESCE(b.bm25_score, 0.0) AS bm25_score,
                (1.0 / (60 + COALESCE(v.vec_rank, 100))) +
                (1.0 / (60 + COALESCE(b.bm25_rank, 100))) AS rrf_score
            FROM vector_ranked v
            FULL OUTER JOIN bm25_ranked b ON v.id = b.id
        )
        SELECT c.id, c.content, c.chunk_type, c.page_number,
               c.char_start, c.char_end,
               combined.cosine_score,
               combined.bm25_score,
               combined.rrf_score AS similarity
        FROM combined
        JOIN chunks c ON c.id = combined.id
        ORDER BY rrf_score DESC
        LIMIT :limit
    """)

    result = await db.execute(sql, {
        "emb": embedding_str,
        "doc_id": str(doc_id),
        "qtext": query_text,
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
            "cosine_score": round(float(row.cosine_score), 4),
            "bm25_score": round(float(row.bm25_score), 4),
        }
        for row in rows
    ]
