from pydantic import BaseModel, Field
from datetime import datetime
from uuid import UUID
from typing import Optional


# === Auth ===

class SignupRequest(BaseModel):
    email: str = Field(..., min_length=5, max_length=255)
    password: str = Field(..., min_length=6, max_length=128)


class LoginRequest(BaseModel):
    email: str
    password: str


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class UserResponse(BaseModel):
    id: UUID
    email: str
    created_at: datetime

    class Config:
        from_attributes = True


# === Documents ===

class DocumentResponse(BaseModel):
    id: UUID
    filename: str
    file_type: str
    file_size: int
    page_count: Optional[int] = None
    status: str
    error_msg: Optional[str] = None
    chunk_count: Optional[int] = None
    created_at: datetime

    class Config:
        from_attributes = True


class ChunkResponse(BaseModel):
    id: UUID
    content: str
    chunk_type: str
    chunk_index: int
    page_number: Optional[int] = None
    char_start: int
    char_end: int

    class Config:
        from_attributes = True


class DocumentChunksResponse(BaseModel):
    chunks: list[ChunkResponse]


# === Queries ===

class QueryRequest(BaseModel):
    document_id: UUID
    question: str = Field(..., min_length=1, max_length=1000)


class SourceChunk(BaseModel):
    chunk_id: UUID
    content: str
    chunk_type: str
    page_number: Optional[int] = None
    char_start: int
    char_end: int
    similarity: float
    bm25_score: Optional[float] = None
    cosine_score: Optional[float] = None


class BudgetInfo(BaseModel):
    remaining_pct: int
    model_tier: str
    daily_reset_utc: str


class QueryResponse(BaseModel):
    id: UUID
    question: str
    answer: str
    confidence: str
    sources: list[SourceChunk]
    latency_ms: Optional[int] = None
    model_used: Optional[str] = None
    budget: Optional[BudgetInfo] = None
    created_at: datetime

    class Config:
        from_attributes = True


class QueryHistoryItem(BaseModel):
    id: UUID
    question: str
    answer: str
    confidence: str
    source_count: int
    created_at: datetime

    class Config:
        from_attributes = True


# === Budget ===

class BudgetResponse(BaseModel):
    primary_model: str
    primary_requests_today: int
    primary_remaining: int
    fallback_model: str
    fallback_requests_today: int
    fallback_remaining: int
    total_remaining: int
    remaining_pct: int
    active_model: str
    resets_at: str


# === Health ===

class HealthResponse(BaseModel):
    status: str
    postgres: bool
    redis: bool
    embedding_model: bool
