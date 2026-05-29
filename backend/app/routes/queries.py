from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as aioredis

from app.dependencies import get_db, get_current_user_id, get_embedding_model, get_redis
from app.models.schemas import QueryRequest, QueryResponse, QueryHistoryItem, BudgetResponse
from app.services import query_service
from app.services.groq_budget import GroqBudgetManager

router = APIRouter(prefix="/api", tags=["queries"])


@router.post("/queries", response_model=QueryResponse)
async def ask_question(
    req: QueryRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
    redis_client: aioredis.Redis = Depends(get_redis),
):
    embedding_model = get_embedding_model()
    try:
        result = await query_service.ask_question(
            db=db,
            user_id=UUID(user_id),
            document_id=req.document_id,
            question=req.question,
            embedding_model=embedding_model,
            redis_client=redis_client,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/queries", response_model=list[QueryHistoryItem])
async def get_query_history(
    document_id: UUID,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    return await query_service.get_query_history(db, UUID(user_id), document_id)


@router.get("/budget", response_model=BudgetResponse)
async def get_budget(
    redis_client: aioredis.Redis = Depends(get_redis),
    user_id: str = Depends(get_current_user_id),
):
    budget_mgr = GroqBudgetManager(redis_client)
    return await budget_mgr.get_budget_status()
