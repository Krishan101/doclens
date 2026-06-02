from uuid import UUID

from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, BackgroundTasks, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, get_current_user_id, get_embedding_model, async_session_factory, get_redis
from app.models.schemas import DocumentResponse, DocumentChunksResponse
from app.services import document_service
from app.config import get_settings
import redis.asyncio as aioredis

settings = get_settings()
router = APIRouter(prefix="/api/documents", tags=["documents"])

ALLOWED_TYPES = {
    "application/pdf": "pdf",
    "text/plain": "txt",
}
ALLOWED_EXTENSIONS = {".pdf", ".txt"}


@router.post("", response_model=DocumentResponse, status_code=202)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
    redis_client: aioredis.Redis = Depends(get_redis),
):
    # Validate file type
    ext = "." + file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    content_type = file.content_type or ""

    file_type = ALLOWED_TYPES.get(content_type)
    if not file_type and ext in ALLOWED_EXTENSIONS:
        file_type = ext.lstrip(".")
    if not file_type:
        raise HTTPException(status_code=400, detail=f"Unsupported file type. Allowed: PDF, TXT")

    # Read and validate size
    file_bytes = await file.read()
    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    if len(file_bytes) > max_bytes:
        raise HTTPException(status_code=413, detail=f"File too large. Maximum: {settings.max_upload_size_mb}MB")

    # Create document record
    doc = await document_service.create_document(
        db=db,
        user_id=UUID(user_id),
        filename=file.filename,
        file_type=file_type,
        file_size=len(file_bytes),
    )

    # Process in background
    embedding_model = get_embedding_model()

    async def _process():
        async with async_session_factory() as bg_session:
            await document_service.process_document(
                db=bg_session,
                document_id=doc.id,
                file_bytes=file_bytes,
                file_type=file_type,
                embedding_model=embedding_model,
                redis_client=redis_client,
            )

    background_tasks.add_task(_process)

    return DocumentResponse(
        id=doc.id,
        filename=doc.filename,
        file_type=doc.file_type,
        file_size=doc.file_size,
        status=doc.status,
        created_at=doc.created_at,
    )


@router.get("", response_model=list[DocumentResponse])
async def list_documents(
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    docs = await document_service.get_user_documents(db, UUID(user_id))
    return docs


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: UUID,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    doc = await document_service.get_document(db, document_id, UUID(user_id))
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


@router.get("/{document_id}/chunks", response_model=DocumentChunksResponse)
async def get_document_chunks(
    document_id: UUID,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    chunks = await document_service.get_document_chunks(db, document_id, UUID(user_id))
    if chunks is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return DocumentChunksResponse(chunks=chunks)


@router.delete("/{document_id}", status_code=204)
async def delete_document(
    document_id: UUID,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    deleted = await document_service.delete_document(db, document_id, UUID(user_id))
    if not deleted:
        raise HTTPException(status_code=404, detail="Document not found")
