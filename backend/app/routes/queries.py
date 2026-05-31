from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as aioredis
import json

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


@router.post("/queries/stream")
async def stream_question(
    req: QueryRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
    redis_client: aioredis.Redis = Depends(get_redis),
):
    """Streaming RAG endpoint — returns SSE events."""
    embedding_model = get_embedding_model()

    async def event_generator():
        try:
            async for event in query_service.ask_question_stream(
                db=db,
                user_id=UUID(user_id),
                document_id=req.document_id,
                question=req.question,
                embedding_model=embedding_model,
                redis_client=redis_client,
            ):
                yield f"data: {json.dumps(event, default=str)}\n\n"
        except HTTPException as e:
            yield f"data: {json.dumps({'type': 'error', 'error': e.detail})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/queries", response_model=list[QueryHistoryItem])
async def get_query_history(
    document_id: UUID,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    return await query_service.get_query_history(db, UUID(user_id), document_id)


@router.get("/documents/{document_id}/suggestions")
async def get_suggested_questions(
    document_id: UUID,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
    redis_client: aioredis.Redis = Depends(get_redis),
):
    """Generate smart suggested questions based on document content."""
    try:
        suggestions = await query_service.generate_suggestions(
            db=db,
            user_id=UUID(user_id),
            document_id=document_id,
            redis_client=redis_client,
        )
        return {"suggestions": suggestions}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/budget", response_model=BudgetResponse)
async def get_budget(
    redis_client: aioredis.Redis = Depends(get_redis),
    user_id: str = Depends(get_current_user_id),
):
    budget_mgr = GroqBudgetManager(redis_client)
    return await budget_mgr.get_budget_status()
