import time
import asyncio
import logging

from groq import AsyncGroq

# Error classes vary across groq SDK versions — import defensively
try:
    from groq import RateLimitError, APITimeoutError, APIError
except ImportError:
    try:
        from groq._exceptions import RateLimitError, APITimeoutError, APIError
    except ImportError:
        RateLimitError = Exception
        APITimeoutError = TimeoutError
        APIError = Exception

import redis.asyncio as aioredis

from app.config import get_settings
from app.services.groq_budget import GroqBudgetManager, BudgetExhaustedError

settings = get_settings()
logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an expert document analyst. Answer the user's question using ONLY the SOURCE passages provided below.

Guidelines:
- Give thorough, well-structured answers (3-5 sentences minimum for factual questions)
- Quote specific numbers, names, and details directly from the sources
- When multiple sources are relevant, synthesize information across them
- Cite sources inline as [SOURCE N] after each claim
- If the question asks for analysis or comparison, provide your reasoning based on the source material
- If the context only partially covers the question, answer what you can and note what's missing
- If the context doesn't address the question at all, say so clearly
- Use bullet points when listing 3+ items
- NEVER invent information not present in the sources"""


class LLMService:
    def __init__(self, redis_client: aioredis.Redis):
        self.client = AsyncGroq(api_key=settings.groq_api_key, timeout=30.0)
        self.budget = GroqBudgetManager(redis_client)

    async def generate_answer(
        self,
        question: str,
        context_chunks: list[dict],
    ) -> dict:
        """
        Generate an answer using Groq with budget management.
        Returns: {answer, model, prompt_tokens, completion_tokens, latency_ms}
        """
        # Build prompt
        context_parts = []
        for i, chunk in enumerate(context_chunks):
            page = chunk.get("page_number", "?")
            context_parts.append(f"[SOURCE {i+1}] (p.{page}): {chunk['content']}")

        context_str = "\n\n".join(context_parts)
        user_prompt = f"{context_str}\n\nQ: {question}"

        # Budget check + throttle
        try:
            model = await self.budget.select_model()
        except BudgetExhaustedError as e:
            return {
                "answer": f"⚠️ {e.message}",
                "model": "none",
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "latency_ms": 0,
            }

        await self.budget.pre_request_throttle()

        # Call Groq
        start_time = time.time()
        try:
            response = await self.client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.1,
                max_tokens=settings.max_completion_tokens,
            )

            latency_ms = int((time.time() - start_time) * 1000)
            answer = response.choices[0].message.content
            usage = response.usage

            # Record usage
            await self.budget.record_usage(
                model=model,
                prompt_tokens=usage.prompt_tokens if usage else 0,
                completion_tokens=usage.completion_tokens if usage else 0,
            )

            return {
                "answer": answer,
                "model": model,
                "prompt_tokens": usage.prompt_tokens if usage else 0,
                "completion_tokens": usage.completion_tokens if usage else 0,
                "latency_ms": latency_ms,
            }

        except RateLimitError as e:
            logger.warning(f"Groq rate limit hit: {e}")
            # Try once more after a short delay
            try:
                await asyncio.sleep(3)
                response = await self.client.chat.completions.create(
                    model=self.budget.fallback,  # Use fallback model on retry
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=0.1,
                    max_tokens=settings.max_completion_tokens,
                )
                latency_ms = int((time.time() - start_time) * 1000)
                answer = response.choices[0].message.content
                usage = response.usage
                await self.budget.record_usage(
                    model=self.budget.fallback,
                    prompt_tokens=usage.prompt_tokens if usage else 0,
                    completion_tokens=usage.completion_tokens if usage else 0,
                )
                return {
                    "answer": answer,
                    "model": self.budget.fallback,
                    "prompt_tokens": usage.prompt_tokens if usage else 0,
                    "completion_tokens": usage.completion_tokens if usage else 0,
                    "latency_ms": latency_ms,
                }
            except Exception:
                return {
                    "answer": "The AI service is temporarily rate-limited. Please wait a moment and try again.",
                    "model": "none",
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "latency_ms": int((time.time() - start_time) * 1000),
                }

        except (APITimeoutError, APIError) as e:
            logger.error(f"Groq API error: {e}")
            return {
                "answer": "The AI service is temporarily unavailable. Please try again.",
                "model": "none",
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "latency_ms": int((time.time() - start_time) * 1000),
            }
