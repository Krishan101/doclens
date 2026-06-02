from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as aioredis
import json

from app.dependencies import get_db, get_current_user_id, get_embedding_model, get_redis
from app.models.schemas import (
    QueryRequest, QueryResponse, QueryHistoryItem, BudgetResponse,
    FeedbackRequest, FeedbackResponse, DashboardStats,
)
from app.services import query_service
from app.services.groq_budget import GroqBudgetManager
from app.repositories import feedback_repo, query_repo, document_repo

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


@router.post("/feedback", response_model=FeedbackResponse, status_code=201)
async def submit_feedback(
    req: FeedbackRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """Submit thumbs up/down feedback on an answer."""
    existing = await feedback_repo.get_for_query(db, req.query_id, UUID(user_id))
    if existing:
        raise HTTPException(status_code=409, detail="Feedback already submitted for this answer")
    fb = await feedback_repo.create(db, req.query_id, UUID(user_id), req.rating)
    return fb


@router.get("/stats", response_model=DashboardStats)
async def get_dashboard_stats(
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
    redis_client: aioredis.Redis = Depends(get_redis),
):
    """Dashboard analytics: total docs, queries, avg confidence, feedback stats."""
    from sqlalchemy import select, func
    from app.models.database import Document, Query

    # Total documents
    result = await db.execute(
        select(func.count(Document.id)).where(Document.user_id == UUID(user_id))
    )
    total_docs = result.scalar() or 0

    # Total queries
    result = await db.execute(
        select(func.count(Query.id)).where(Query.user_id == UUID(user_id))
    )
    total_queries = result.scalar() or 0

    # Average confidence
    result = await db.execute(
        select(Query.confidence).where(Query.user_id == UUID(user_id))
    )
    confidences = [r[0] for r in result.fetchall()]
    conf_scores = {"high": 100, "low": 50, "none": 0}
    avg_conf = 0.0
    if confidences:
        avg_conf = round(sum(conf_scores.get(c, 0) for c in confidences) / len(confidences), 1)

    # Feedback stats
    fb_stats = await feedback_repo.get_stats(db, UUID(user_id))

    # Budget
    budget_mgr = GroqBudgetManager(redis_client)
    budget = await budget_mgr.get_budget_status()

    return DashboardStats(
        total_documents=total_docs,
        total_queries=total_queries,
        avg_confidence_pct=avg_conf,
        positive_feedback_pct=fb_stats["positive_pct"],
        total_feedback=fb_stats["total"],
        budget_remaining_pct=budget["remaining_pct"],
    )
