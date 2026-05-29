import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.dependencies import engine, get_redis, get_embedding_model
from app.routes import auth, documents, queries
from app.models.database import Base

settings = get_settings()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting DocLens API...")

    # Create tables (for dev — production uses Alembic)
    async with engine.begin() as conn:
        await conn.execute(__import__("sqlalchemy").text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables ready")

    # Pre-load embedding model
    model = get_embedding_model()
    logger.info(f"Embedding model loaded: {model.get_sentence_embedding_dimension()}d")

    yield

    # Shutdown
    await engine.dispose()
    redis = await get_redis()
    await redis.close()
    logger.info("DocLens API shutdown complete")


app = FastAPI(
    title="DocLens API",
    description="Document-grounded RAG with source highlighting",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
origins = [o.strip() for o in settings.backend_cors_origins.split(",")]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes
app.include_router(auth.router)
app.include_router(documents.router)
app.include_router(queries.router)


@app.get("/api/health")
async def health():
    checks = {"postgres": False, "redis": False, "embedding_model": False}

    # Postgres
    try:
        async with engine.begin() as conn:
            await conn.execute(__import__("sqlalchemy").text("SELECT 1"))
        checks["postgres"] = True
    except Exception:
        pass

    # Redis
    try:
        redis = await get_redis()
        await redis.ping()
        checks["redis"] = True
    except Exception:
        pass

    # Embedding model
    try:
        model = get_embedding_model()
        checks["embedding_model"] = model is not None
    except Exception:
        pass

    all_ok = all(checks.values())
    return {"status": "healthy" if all_ok else "degraded", **checks}
