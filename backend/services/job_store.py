"""
Redis-backed job store for persisting job status across restarts.
Falls back to in-memory dict when Redis is unavailable.

Also provides an append-only event log per job for SSE streaming.
"""

import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)

_redis_client = None
_fallback_store: dict = {}

# In-memory event logs: job_id -> list[dict]
_event_store: dict[str, list[dict]] = {}


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
EVENT_PREFIX = "narrato:events:"
JOB_TTL = 86400  # 24 hours


def _key(job_id: str) -> str:
    return f"{JOB_PREFIX}{job_id}"


def _event_key(job_id: str) -> str:
    return f"{EVENT_PREFIX}{job_id}"


def set_job(job_id: str, status: str, path: Optional[str] = None,
            error: Optional[str] = None, progress: Optional[int] = None,
            preview_urls: Optional[list] = None, html_slides: Optional[list] = None,
            structured_slides: Optional[list] = None,
            pdf_path: Optional[str] = None,
            image_paths: Optional[list] = None) -> None:
    """Create or update a job entry."""
    data = {
        "status": status,
        "path": path,
        "error": error,
        "progress": progress,
        "preview_urls": preview_urls,
        "html_slides": html_slides if html_slides is not None else [],
        "structured_slides": structured_slides,
        "pdf_path": pdf_path,
        "image_paths": image_paths if image_paths is not None else [],
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
                    "html_slides": [], "structured_slides": None,
                    "pdf_path": None, "image_paths": []}
    existing.update({k: v for k, v in kwargs.items() if v is not None})
    set_job(job_id, **existing)


# ── Event log helpers ──────────────────────────────────────────────


def append_event(job_id: str, event: dict) -> None:
    """Append a pipeline event to the job's event log."""
    r = _get_redis()
    if r is not None:
        try:
            r.rpush(_event_key(job_id), json.dumps(event))
            r.expire(_event_key(job_id), JOB_TTL)
            return
        except Exception:
            logger.exception("Redis append_event failed, falling back to memory")
    _event_store.setdefault(job_id, []).append(event)


def get_events(job_id: str, after: int = 0) -> list[dict]:
    """Return events for a job starting from index *after*.

    The caller tracks its cursor and passes it back so we only
    return new events each time (efficient for SSE polling).
    """
    r = _get_redis()
    if r is not None:
        try:
            raw_list = r.lrange(_event_key(job_id), after, -1)
            return [json.loads(raw) for raw in raw_list]
        except Exception:
            logger.exception("Redis get_events failed, falling back to memory")
    return _event_store.get(job_id, [])[after:]
