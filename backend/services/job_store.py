"""
Redis-backed job store for persisting job status across restarts.
Falls back to in-memory dict when Redis is unavailable.
"""

import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)

_redis_client = None
_fallback_store: dict = {}


def _get_redis():
    """Lazily connect to Redis. Returns None if unavailable."""
    global _redis_client
    if _redis_client is not None:
        return _redis_client
    try:
        from config import settings
        import redis
        _redis_client = redis.Redis.from_url(
            settings.redis_url,
            decode_responses=True,
            socket_connect_timeout=3,
        )
        _redis_client.ping()
        logger.info("Redis job store connected at %s", settings.redis_url)
        return _redis_client
    except Exception as exc:
        logger.warning("Redis unavailable (%s), using in-memory job store", exc)
        _redis_client = None
        return None


JOB_PREFIX = "narrato:job:"
JOB_TTL = 86400  # 24 hours


def _key(job_id: str) -> str:
    return f"{JOB_PREFIX}{job_id}"


def set_job(job_id: str, status: str, path: Optional[str] = None,
            error: Optional[str] = None, progress: Optional[int] = None,
            preview_urls: Optional[list] = None, html_slides: Optional[list] = None,
            structured_slides: Optional[list] = None) -> None:
    """Create or update a job entry."""
    data = {
        "status": status,
        "path": path,
        "error": error,
        "progress": progress,
        "preview_urls": preview_urls,
        "html_slides": html_slides,
        "structured_slides": structured_slides,
    }
    r = _get_redis()
    if r is not None:
        try:
            r.setex(_key(job_id), JOB_TTL, json.dumps(data))
            return
        except Exception:
            logger.exception("Redis set_job failed, falling back to memory")
    _fallback_store[job_id] = data


def get_job(job_id: str) -> Optional[dict]:
    """Retrieve a job entry. Returns None if not found."""
    r = _get_redis()
    if r is not None:
        try:
            raw = r.get(_key(job_id))
            if raw:
                return json.loads(raw)
            return None
        except Exception:
            logger.exception("Redis get_job failed, falling back to memory")
    return _fallback_store.get(job_id)


def update_job(job_id: str, **kwargs) -> None:
    """Partially update fields on an existing job."""
    existing = get_job(job_id)
    if existing is None:
        existing = {"status": "unknown", "path": None, "error": None,
                    "progress": None, "preview_urls": None,
                    "html_slides": None, "structured_slides": None}
    existing.update({k: v for k, v in kwargs.items() if v is not None})
    set_job(job_id, **existing)
