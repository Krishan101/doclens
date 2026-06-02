from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.models.database import Document, Chunk


async def create(
    db: AsyncSession,
    user_id: UUID,
    filename: str,
    file_type: str,
    file_size: int,
) -> Document:
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


async def get_by_id(
    db: AsyncSession,
    doc_id: UUID,
    user_id: UUID | None = None,
) -> Document | None:
    query = select(Document).where(Document.id == doc_id)
    if user_id is not None:
        query = query.where(Document.user_id == user_id)
    result = await db.execute(query)
    return result.scalar_one_or_none()


async def list_by_user(db: AsyncSession, user_id: UUID) -> list[Document]:
    result = await db.execute(
        select(Document)
        .where(Document.user_id == user_id)
        .order_by(Document.created_at.desc())
    )
    return list(result.scalars().all())


async def update_status(
    db: AsyncSession,
    doc_id: UUID,
    status: str,
    error_msg: str | None = None,
    raw_text: str | None = None,
    page_count: int | None = None,
    summary: str | None = None,
) -> None:
    result = await db.execute(select(Document).where(Document.id == doc_id))
    doc = result.scalar_one_or_none()
    if doc:
        doc.status = status
        if error_msg is not None:
            doc.error_msg = error_msg
        if raw_text is not None:
            doc.raw_text = raw_text
        if page_count is not None:
            doc.page_count = page_count
        if summary is not None:
            doc.summary = summary
        await db.commit()


async def delete(db: AsyncSession, doc_id: UUID, user_id: UUID) -> bool:
    result = await db.execute(
        select(Document).where(Document.id == doc_id, Document.user_id == user_id)
    )
    doc = result.scalar_one_or_none()
    if not doc:
        return False
    await db.delete(doc)
    await db.commit()
    return True


async def get_chunk_count(db: AsyncSession, doc_id: UUID) -> int:
    result = await db.execute(
        select(func.count(Chunk.id)).where(Chunk.document_id == doc_id)
    )
    return result.scalar() or 0
