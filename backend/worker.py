"""
Celery worker for Narrato pipeline execution.

Usage:
    celery -A worker.celery_app worker --loglevel=info

The worker picks up presentation generation jobs from the Redis broker,
runs the full pipeline, and stores results back in the job store.
"""

import asyncio
import logging

from celery import Celery
from config import settings

logger = logging.getLogger(__name__)

celery_app = Celery(
    "narrato",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_soft_time_limit=120,
    task_time_limit=180,
    broker_connection_retry_on_startup=True,
)


def _run_async(coro):
    """Helper to run an async function from a sync Celery task."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@celery_app.task(bind=True, name="narrato.generate_presentation", max_retries=2,
                 default_retry_delay=10)
def generate_presentation_task(self, job_id: str, prompt: str, options: dict):
    """Celery task that executes the full Narrato pipeline."""
    from services.job_store import set_job, update_job

    try:
        update_job(job_id, status="processing", progress=10)

        from orchestrator import run_pipeline
        output_path = _run_async(run_pipeline(prompt, options))

        set_job(job_id, status="completed", path=output_path, progress=100)
        logger.info("[celery] Job %s completed: %s", job_id, output_path)
        return {"status": "completed", "path": output_path}

    except Exception as exc:
        logger.exception("[celery] Job %s failed", job_id)
        set_job(job_id, status="failed", error=str(exc))
        raise self.retry(exc=exc) if self.request.retries < self.max_retries else None
