import asyncio
import json
import logging
import re

from config import settings

logger = logging.getLogger(__name__)

MAX_RETRIES = 2
BACKOFF_SECONDS = [1]
_semaphore = asyncio.Semaphore(3)


def _strip_code_fences(text: str) -> str:
    """Remove markdown code fences (```json ... ``` or ``` ... ```) from LLM output."""
    stripped = re.sub(r"^```(?:json)?\s*\n?", "", text.strip(), flags=re.IGNORECASE)
    stripped = re.sub(r"\n?```\s*$", "", stripped)
    return stripped.strip()


async def call_llm(system_prompt: str, user_prompt: str) -> str:
    async with _semaphore:
        last_exc: Exception | None = None
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                logger.info("LLM call attempt %d/%d (provider=%s)", attempt, MAX_RETRIES, settings.llm_provider)
                result = await _call_llm_raw(system_prompt, user_prompt)
                return result
            except Exception as exc:
                last_exc = exc
                if attempt < MAX_RETRIES:
                    wait = BACKOFF_SECONDS[attempt - 1]
                    logger.warning("LLM call attempt %d failed (%s), retrying in %ds…", attempt, exc, wait)
                    await asyncio.sleep(wait)
                else:
                    logger.error("LLM call failed after %d attempts: %s", MAX_RETRIES, exc)
        if last_exc is not None:
            raise last_exc
        raise RuntimeError("LLM call failed with no retries configured")


async def _call_llm_raw(system_prompt: str, user_prompt: str) -> str:
    if settings.llm_provider == "openai":
        if not settings.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY is not configured. Set it in your .env file.")
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=settings.openai_api_key)
        response = await client.chat.completions.create(
            model=settings.llm_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.7
        )
        return response.choices[0].message.content

    elif settings.llm_provider == "anthropic":
        if not settings.anthropic_api_key:
            raise RuntimeError("ANTHROPIC_API_KEY is not configured. Set it in your .env file.")
        import anthropic
        client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        message = await client.messages.create(
            model=settings.llm_model,
            max_tokens=4096,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}]
        )
        return message.content[0].text

    raise ValueError(f"Unsupported LLM provider: {settings.llm_provider}")


async def call_llm_json(system_prompt: str, user_prompt: str) -> dict:
    """Always returns parsed JSON dict — raises ValueError on parse failure."""
    raw = await call_llm(
        system_prompt + "\n\nIMPORTANT: Respond ONLY with valid JSON. No markdown, no backticks, no preamble.",
        user_prompt
    )
    cleaned = _strip_code_fences(raw)
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise ValueError(f"LLM returned invalid JSON: {e}\nRaw: {raw}")
    if not isinstance(parsed, dict):
        raise ValueError(f"Expected JSON dict but got {type(parsed).__name__}: {parsed}")
    return parsed


async def call_llm_json_list(system_prompt: str, user_prompt: str) -> list:
    """Always returns a parsed JSON list — raises ValueError on parse failure."""
    raw = await call_llm(
        system_prompt + "\n\nIMPORTANT: Respond ONLY with a valid JSON array. No markdown, no backticks, no preamble.",
        user_prompt
    )
    cleaned = _strip_code_fences(raw)
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise ValueError(f"LLM returned invalid JSON: {e}\nRaw: {raw}")
    if not isinstance(parsed, list):
        raise ValueError(f"Expected JSON list but got {type(parsed).__name__}: {parsed}")
    return parsed
