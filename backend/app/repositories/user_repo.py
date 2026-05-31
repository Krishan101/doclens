from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.database import User


async def get_by_email(db: AsyncSession, email: str) -> User | None:
    result = await db.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


async def create(db: AsyncSession, email: str, hashed_pw: str) -> User:
    user = User(email=email, hashed_pw=hashed_pw)
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user
