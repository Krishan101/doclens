import hashlib
import json
from sentence_transformers import SentenceTransformer
import redis.asyncio as aioredis

CACHE_TTL = 3600  # 1 hour


def embed_texts(model: SentenceTransformer, texts: list[str]) -> list[list[float]]:
    """Embed a list of texts using the sentence-transformers model."""
    if not texts:
        return []
    embeddings = model.encode(texts, batch_size=32, normalize_embeddings=True, show_progress_bar=False)
    return embeddings.tolist()


def embed_single(model: SentenceTransformer, text: str) -> list[float]:
    """Embed a single text."""
    embedding = model.encode(text, normalize_embeddings=True, show_progress_bar=False)
    return embedding.tolist()


async def embed_with_cache(
    model: SentenceTransformer,
    text: str,
    redis_client: aioredis.Redis | None = None,
) -> list[float]:
    """Embed text with Redis caching."""
    cache_key = f"embed:{hashlib.md5(text.encode()).hexdigest()}"

    # Try cache first
    if redis_client:
        try:
            cached = await redis_client.get(cache_key)
            if cached:
                return json.loads(cached)
        except Exception:
            pass  # Cache miss or Redis down — proceed without cache

    # Compute embedding
    embedding = embed_single(model, text)

    # Cache result
    if redis_client:
        try:
            await redis_client.set(cache_key, json.dumps(embedding), ex=CACHE_TTL)
        except Exception:
            pass  # Don't fail on cache write errors

    return embedding
