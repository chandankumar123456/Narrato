"""
Celery worker for Narrato pipeline execution.

Usage:
    cd backend && celery -A worker.celery_app worker --loglevel=info

The worker picks up presentation generation jobs from the Redis broker,
runs the full pipeline, and stores results back in the job store.
"""

import asyncio
import logging
import os
import sys

# Ensure the backend directory is in sys.path so that forked worker
# processes can resolve imports (services, orchestrator, config, etc.).
_backend_dir = os.path.dirname(os.path.abspath(__file__))
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)

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
    # Ensure backend dir is in path for forked worker processes
    import os, sys
    _bd = os.path.dirname(os.path.abspath(__file__))
    if _bd not in sys.path:
        sys.path.insert(0, _bd)

    from services.job_store import set_job, update_job, append_event

    try:
        update_job(job_id, status="processing", progress=5)

        def _progress(pct: int):
            update_job(job_id, progress=pct)

        def _event(evt):
            """Store event in the job event log for SSE streaming."""
            append_event(job_id, evt.to_dict())
            update_job(job_id, progress=evt.progress)

        from orchestrator import run_pipeline
        run_options = {**options, "_job_id": job_id}
        result = _run_async(run_pipeline(prompt, run_options,
                                         progress_callback=_progress,
                                         event_callback=_event))

        # Extract results
        if isinstance(result, dict):
            html_slides = result.get("html_slides", [])
            structured_slides = result.get("structured_slides", [])
            pdf_path = result.get("pdf_path")
            image_paths = result.get("image_paths", [])
        else:
            html_slides = []
            structured_slides = []
            pdf_path = None
            image_paths = []

        # Save HTML slides to job-specific directory
        safe_id = os.path.basename(job_id)
        job_output_dir = os.path.join(settings.output_dir, safe_id)
        os.makedirs(job_output_dir, exist_ok=True)
        html_slide_paths = []
        for idx, html in enumerate(html_slides):
            slide_path = os.path.join(job_output_dir, f"slide_{idx + 1}.html")
            with open(slide_path, "w", encoding="utf-8") as f:
                f.write(html)
            html_slide_paths.append(f"/outputs/{safe_id}/slide_{idx + 1}.html")

        set_job(job_id, status="completed", progress=100,
                html_slides=html_slide_paths, structured_slides=structured_slides,
                pdf_path=pdf_path, image_paths=image_paths)
        logger.info("[celery] Job %s completed", job_id)
        return {"status": "completed"}

    except Exception as exc:
        logger.exception("[celery] Job %s failed", job_id)
        # Emit failure event
        try:
            from services.event_system import PipelineEvent, EventType
            fail_evt = PipelineEvent(
                job_id=job_id, type=EventType.JOB_FAILED,
                stage="failed", progress=0,
                label="Generation failed",
                data={"error": str(exc)},
            )
            append_event(job_id, fail_evt.to_dict())
        except Exception:
            pass
        set_job(job_id, status="failed", error=str(exc))
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc)
