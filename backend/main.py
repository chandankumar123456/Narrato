import uuid, asyncio, os, logging, glob, subprocess, traceback
from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from orchestrator import run_pipeline
from config import settings
from services.job_store import set_job, get_job, update_job

logger = logging.getLogger(__name__)

app = FastAPI(title="Narrato API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve preview images as static files
PREVIEW_DIR = os.path.join(settings.output_dir, "previews")
os.makedirs(PREVIEW_DIR, exist_ok=True)
app.mount("/previews", StaticFiles(directory=PREVIEW_DIR), name="previews")


class GenerateRequest(BaseModel):
    prompt: str
    options: dict = {}


class GenerateResponse(BaseModel):
    job_id: str
    status: str
    estimated_seconds: int = 30


class StatusResponse(BaseModel):
    job_id: str
    status: str
    progress: Optional[int] = None
    download_url: Optional[str] = None
    preview_urls: Optional[list] = None
    error: Optional[str] = None


class ErrorResponse(BaseModel):
    error: str
    detail: Optional[str] = None


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.exception("Unhandled exception: %s", exc)
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "detail": str(exc)},
    )


def _try_celery() -> bool:
    """Check if Celery workers are reachable."""
    try:
        from worker import celery_app
        insp = celery_app.control.inspect(timeout=1.0)
        return bool(insp.ping())
    except Exception:
        return False


@app.post("/generate", response_model=GenerateResponse)
async def generate(req: GenerateRequest, background_tasks: BackgroundTasks):
    if not req.prompt.strip():
        raise HTTPException(status_code=400, detail="Prompt cannot be empty")
    if len(req.prompt) > 5000:
        raise HTTPException(status_code=400, detail="Prompt exceeds maximum length of 5000 characters")

    job_id = uuid.uuid4().hex
    set_job(job_id, status="queued", progress=0)

    # Try Celery first; fall back to background task
    if _try_celery():
        from worker import generate_presentation_task
        generate_presentation_task.delay(job_id, req.prompt, req.options)
        logger.info("[api] Job %s enqueued to Celery", job_id)
    else:
        background_tasks.add_task(_run_job, job_id, req.prompt, req.options)
        logger.info("[api] Job %s running as background task (no Celery)", job_id)

    return GenerateResponse(job_id=job_id, status="queued", estimated_seconds=30)


async def _run_job(job_id: str, prompt: str, options: dict):
    """Fallback: run pipeline directly in a background task."""
    try:
        update_job(job_id, status="processing", progress=5)

        def _progress(pct: int):
            update_job(job_id, progress=pct)

        path = await run_pipeline(prompt, options, progress_callback=_progress)
        set_job(job_id, status="completed", path=path, progress=100)
    except Exception as e:
        logger.exception("[api] Job %s failed", job_id)
        set_job(job_id, status="failed", error=str(e))


@app.get("/status/{job_id}", response_model=StatusResponse)
async def status(job_id: str):
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    resp = StatusResponse(
        job_id=job_id,
        status=job["status"],
        progress=job.get("progress"),
    )
    if job["status"] == "completed":
        resp.download_url = f"/download/{job_id}"
        resp.preview_urls = job.get("preview_urls")
    if job["status"] == "failed":
        resp.error = job.get("error")
    return resp


@app.get("/download/{job_id}")
async def download(job_id: str):
    job = get_job(job_id)
    if not job or job["status"] != "completed":
        raise HTTPException(status_code=404, detail="File not ready")
    path = job.get("path")
    if not path or not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="File not found on disk")
    return FileResponse(
        path,
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        filename="narrato.pptx"
    )


@app.post("/preview/{job_id}")
async def generate_preview(job_id: str, background_tasks: BackgroundTasks):
    """Convert a completed .pptx to slide thumbnail images using LibreOffice."""
    job = get_job(job_id)
    if not job or job["status"] != "completed":
        raise HTTPException(status_code=404, detail="Job not completed")

    pptx_path = job.get("path")
    if not pptx_path or not os.path.isfile(pptx_path):
        raise HTTPException(status_code=404, detail="PPTX file not found")

    # Check if previews already exist
    existing = job.get("preview_urls")
    if existing:
        return {"preview_urls": existing}

    background_tasks.add_task(_generate_previews, job_id, pptx_path)
    return {"status": "generating", "message": "Preview generation started. Poll /status for results."}


def _generate_previews(job_id: str, pptx_path: str):
    """Run LibreOffice headless to convert PPTX → images."""
    # Validate path is within output directory to prevent path traversal
    real_pptx = os.path.realpath(pptx_path)
    real_output = os.path.realpath(settings.output_dir)
    if not real_pptx.startswith(real_output + os.sep):
        logger.error("Refusing to process file outside output dir: %s", pptx_path)
        update_job(job_id, preview_urls=[])
        return

    preview_subdir = os.path.join(PREVIEW_DIR, job_id)
    os.makedirs(preview_subdir, exist_ok=True)

    try:
        # Convert PPTX to PDF first
        result = subprocess.run(
            [
                "libreoffice", "--headless", "--convert-to", "pdf",
                "--outdir", preview_subdir, pptx_path
            ],
            capture_output=True, text=True, timeout=60
        )

        if result.returncode != 0:
            logger.error("LibreOffice PDF conversion failed: %s", result.stderr)
            update_job(job_id, preview_urls=[])
            return

        # Find the PDF
        pdf_files = glob.glob(os.path.join(preview_subdir, "*.pdf"))
        if not pdf_files:
            logger.error("No PDF output found after LibreOffice conversion")
            update_job(job_id, preview_urls=[])
            return

        pdf_path = pdf_files[0]

        # Try converting PDF pages to images using pdftoppm (poppler-utils)
        try:
            subprocess.run(
                ["pdftoppm", "-png", "-r", "150", pdf_path,
                 os.path.join(preview_subdir, "slide")],
                capture_output=True, text=True, timeout=60, check=True
            )
            logger.info("[preview] pdftoppm conversion succeeded for job %s", job_id)
        except (FileNotFoundError, subprocess.CalledProcessError) as conv_err:
            logger.warning("[preview] pdftoppm failed (%s), falling back to LibreOffice PNG for job %s", conv_err, job_id)
            # Fallback: try using LibreOffice to convert directly to PNG
            subprocess.run(
                [
                    "libreoffice", "--headless", "--convert-to", "png",
                    "--outdir", preview_subdir, pptx_path
                ],
                capture_output=True, text=True, timeout=60
            )

        # Collect generated image URLs
        image_files = sorted(
            glob.glob(os.path.join(preview_subdir, "*.png")) +
            glob.glob(os.path.join(preview_subdir, "*.jpg"))
        )
        preview_urls = [
            f"/previews/{job_id}/{os.path.basename(f)}" for f in image_files
        ]

        update_job(job_id, preview_urls=preview_urls)
        logger.info("[preview] Generated %d preview images for job %s", len(preview_urls), job_id)

    except subprocess.TimeoutExpired:
        logger.error("Preview generation timed out for job %s", job_id)
        update_job(job_id, preview_urls=[])
    except Exception:
        logger.exception("Preview generation failed for job %s", job_id)
        update_job(job_id, preview_urls=[])


@app.get("/health")
async def health():
    health_data = {"status": "ok", "version": "2.0.0"}

    # Check Redis
    try:
        from services.job_store import _get_redis
        r = _get_redis()
        health_data["redis"] = "connected" if r else "unavailable"
    except Exception:
        health_data["redis"] = "unavailable"

    # Check Celery
    health_data["celery"] = "connected" if _try_celery() else "unavailable"

    return health_data


# ── Visual Rendering Engine endpoints ────────────────────────────────

VISUAL_DIR = os.path.join(settings.output_dir, "visual")
os.makedirs(VISUAL_DIR, exist_ok=True)
app.mount("/visual", StaticFiles(directory=VISUAL_DIR), name="visual")


@app.get("/visual/slides/{job_id}")
async def get_visual_slides(job_id: str):
    """Return list of visual HTML/PNG/PDF paths for a completed job."""
    job = get_job(job_id)
    if not job or job["status"] != "completed":
        raise HTTPException(status_code=404, detail="Job not completed")

    # List available visual assets
    html_files = sorted(glob.glob(os.path.join(VISUAL_DIR, "*.html")))
    png_files = sorted(glob.glob(os.path.join(VISUAL_DIR, "*.png")))
    pdf_files = sorted(glob.glob(os.path.join(VISUAL_DIR, "*.pdf")))

    return {
        "html_slides": [f"/visual/{os.path.basename(f)}" for f in html_files],
        "png_slides": [f"/visual/{os.path.basename(f)}" for f in png_files],
        "pdf": f"/visual/{os.path.basename(pdf_files[0])}" if pdf_files else None,
    }