from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.models.database import Query, Document


async def create(db: AsyncSession, **kwargs) -> Query:
    query = Query(**kwargs)
    db.add(query)
    await db.commit()
    await db.refresh(query)
    return query


async def list_by_document(
    db: AsyncSession,
    doc_id: UUID,
    user_id: UUID,
    limit: int = 20,
) -> list[Query]:
    result = await db.execute(
        select(Query)
        .where(Query.document_id == doc_id, Query.user_id == user_id)
        .order_by(Query.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def get_last_for_document(
    db: AsyncSession,
    doc_id: UUID,
    user_id: UUID,
) -> Query | None:
    result = await db.execute(
        select(Query)
        .where(Query.document_id == doc_id, Query.user_id == user_id)
        .order_by(Query.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def count_by_user(db: AsyncSession, user_id: UUID) -> int:
    result = await db.execute(
        select(func.count(Query.id)).where(Query.user_id == user_id)
    )
    return result.scalar() or 0


async def recent_by_user(
    db: AsyncSession,
    user_id: UUID,
    limit: int = 5,
) -> list[dict]:
    result = await db.execute(
        select(Query, Document.filename)
        .join(Document, Query.document_id == Document.id)
        .where(Query.user_id == user_id)
        .order_by(Query.created_at.desc())
        .limit(limit)
    )
    rows = result.all()
    return [
        {
            "id": str(q.id),
            "question": q.question,
            "answer_preview": q.answer[:80] + "..." if len(q.answer) > 80 else q.answer,
            "document_filename": filename,
            "document_id": str(q.document_id),
            "created_at": q.created_at,
        }
        for q, filename in rows
    ]
