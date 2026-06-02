from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.models.database import Feedback


async def create(db: AsyncSession, query_id: UUID, user_id: UUID, rating: str) -> Feedback:
    fb = Feedback(query_id=query_id, user_id=user_id, rating=rating)
    db.add(fb)
    await db.commit()
    await db.refresh(fb)
    return fb


async def get_stats(db: AsyncSession, user_id: UUID) -> dict:
    """Get feedback stats for a user's queries."""
    result = await db.execute(
        select(func.count(Feedback.id)).where(Feedback.user_id == user_id)
    )
    total = result.scalar() or 0

    if total == 0:
        return {"total": 0, "positive_pct": None}

    result = await db.execute(
        select(func.count(Feedback.id))
        .where(Feedback.user_id == user_id, Feedback.rating == "up")
    )
    positive = result.scalar() or 0

    return {
        "total": total,
        "positive_pct": round((positive / total) * 100, 1) if total > 0 else None,
    }


async def get_for_query(db: AsyncSession, query_id: UUID, user_id: UUID) -> Feedback | None:
    result = await db.execute(
        select(Feedback).where(
            Feedback.query_id == query_id,
            Feedback.user_id == user_id,
        )
    )
    return result.scalar_one_or_none()
