import asyncio
import time
from datetime import datetime, timezone, timedelta

import redis.asyncio as aioredis

from app.config import get_settings

settings = get_settings()


class BudgetExhaustedError(Exception):
    def __init__(self, message: str, resets_at: str = ""):
        self.message = message
        self.resets_at = resets_at
        super().__init__(message)


class GroqBudgetManager:
    """
    Manages Groq free-tier rate limits across two models.
    Limits are per-model, so using both 70B and 8B gives ~1,900 RPD combined.
    """

    RPD_PER_MODEL = 1000
    RPD_RESERVE = 50              # keep 50 requests in reserve
    MIN_REQUEST_SPACING_S = 2.5   # TPM protection: 6000 TPM is tight

    def __init__(self, redis_client: aioredis.Redis):
        self.redis = redis_client
        self.primary = settings.llm_primary_model
        self.fallback = settings.llm_fallback_model

    def _today(self) -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")

    def _next_midnight_utc(self) -> str:
        tomorrow = datetime.now(timezone.utc).date() + timedelta(days=1)
        return datetime(tomorrow.year, tomorrow.month, tomorrow.day, tzinfo=timezone.utc).isoformat()

    async def select_model(self) -> str:
        """Pick model based on remaining RPD budget."""
        primary_used = int(await self.redis.get(f"groq:rpd:{self.primary}:{self._today()}") or 0)
        fallback_used = int(await self.redis.get(f"groq:rpd:{self.fallback}:{self._today()}") or 0)

        primary_remaining = self.RPD_PER_MODEL - self.RPD_RESERVE - primary_used
        fallback_remaining = self.RPD_PER_MODEL - self.RPD_RESERVE - fallback_used

        if primary_remaining > 0:
            return self.primary
        elif fallback_remaining > 0:
            return self.fallback
        else:
            raise BudgetExhaustedError(
                "Daily AI quota reached for all models. Resets at midnight UTC.",
                resets_at=self._next_midnight_utc(),
            )

    async def pre_request_throttle(self):
        """Enforce minimum spacing between requests to stay under TPM."""
        last_ts = await self.redis.get("groq:last_request_ts")
        if last_ts:
            elapsed = time.time() - float(last_ts)
            if elapsed < self.MIN_REQUEST_SPACING_S:
                delay = self.MIN_REQUEST_SPACING_S - elapsed
                await asyncio.sleep(delay)

    async def record_usage(self, model: str, prompt_tokens: int, completion_tokens: int):
        """Record usage after a successful LLM call."""
        pipe = self.redis.pipeline()
        # Daily request count per model
        rpd_key = f"groq:rpd:{model}:{self._today()}"
        pipe.incr(rpd_key)
        pipe.expire(rpd_key, 86400)
        # Last request timestamp (for spacing)
        pipe.set("groq:last_request_ts", str(time.time()), ex=120)
        # Token tracking (informational)
        tpd_key = f"groq:tpd:{model}:{self._today()}"
        pipe.incrby(tpd_key, prompt_tokens + completion_tokens)
        pipe.expire(tpd_key, 86400)
        await pipe.execute()

    async def get_budget_status(self) -> dict:
        """Return current budget status for the /api/budget endpoint."""
        primary_used = int(await self.redis.get(f"groq:rpd:{self.primary}:{self._today()}") or 0)
        fallback_used = int(await self.redis.get(f"groq:rpd:{self.fallback}:{self._today()}") or 0)

        usable_per_model = self.RPD_PER_MODEL - self.RPD_RESERVE
        total_budget = usable_per_model * 2
        total_used = primary_used + fallback_used
        remaining_pct = max(0, round((1 - total_used / max(total_budget, 1)) * 100))

        return {
            "primary_model": self.primary,
            "primary_requests_today": primary_used,
            "primary_remaining": max(0, usable_per_model - primary_used),
            "fallback_model": self.fallback,
            "fallback_requests_today": fallback_used,
            "fallback_remaining": max(0, usable_per_model - fallback_used),
            "total_remaining": max(0, total_budget - total_used),
            "remaining_pct": remaining_pct,
            "active_model": self.primary if primary_used < usable_per_model else self.fallback,
            "resets_at": self._next_midnight_utc(),
        }
