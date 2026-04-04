import uuid, asyncio, os, logging, glob, subprocess, traceback, json, copy, shutil
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

# Serve job-specific output files (HTML slides, etc.)
OUTPUTS_DIR = settings.output_dir
os.makedirs(OUTPUTS_DIR, exist_ok=True)
app.mount("/outputs", StaticFiles(directory=OUTPUTS_DIR), name="outputs")

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
    html_slides: Optional[list] = None
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

        result = await run_pipeline(prompt, options, progress_callback=_progress)
        # Support both old (str) and new (dict) return formats
        if isinstance(result, dict):
            path = result["pptx_path"]
            html_slides = result.get("html_slides", [])
            structured_slides = result.get("structured_slides", [])
        else:
            path = result
            html_slides = []
            structured_slides = []

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

        set_job(job_id, status="completed", path=path, progress=100,
                html_slides=html_slide_paths, structured_slides=structured_slides)
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
        resp.html_slides = job.get("html_slides")
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


# ── Interactive Product Layer endpoints ────────────────────────────────


def _safe_job_dir(job_id: str) -> str:
    """Return a validated job output directory, preventing path traversal."""
    safe_id = os.path.basename(job_id)
    job_dir = os.path.realpath(os.path.join(settings.output_dir, safe_id))
    real_output = os.path.realpath(settings.output_dir)
    if not job_dir.startswith(real_output + os.sep):
        raise HTTPException(status_code=400, detail="Invalid job_id")
    return job_dir


class RegenerateSlideRequest(BaseModel):
    slide_id: int
    instruction: str = ""


class RestyleRequest(BaseModel):
    theme: str = "dark_modern"  # dark_modern, minimal_light, bold_gradient
    density: str = "balanced"  # visual, minimal, data_heavy


class UpdateSlideRequest(BaseModel):
    slide_id: int
    content: dict


class ReorderRequest(BaseModel):
    order: list[int]


class DuplicateSlideRequest(BaseModel):
    slide_id: int


@app.get("/slides/{job_id}")
async def get_slides(job_id: str):
    """Return HTML slides for a completed job."""
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    html_slides = job.get("html_slides", [])
    structured_slides = job.get("structured_slides", [])

    # Build response with slide content
    slides = []
    for idx, path in enumerate(html_slides):
        slide_data = {
            "slide_id": idx + 1,
            "html_url": path,
        }
        # Attach structured content if available
        if idx < len(structured_slides):
            slide_data["content"] = structured_slides[idx].get("content", {})
            slide_data["type"] = structured_slides[idx].get("type", "unknown")
        slides.append(slide_data)

    return {
        "job_id": job_id,
        "slides": slides,
        "status": job["status"],
        "total": len(slides),
    }


@app.post("/regenerate-slide/{job_id}")
async def regenerate_slide(job_id: str, req: RegenerateSlideRequest):
    """Regenerate a single slide with optional instruction."""
    job = get_job(job_id)
    if not job or job["status"] != "completed":
        raise HTTPException(status_code=404, detail="Job not completed")

    structured_slides = job.get("structured_slides", [])
    html_slides = job.get("html_slides", [])

    if req.slide_id < 1 or req.slide_id > len(structured_slides):
        raise HTTPException(status_code=400, detail="Invalid slide_id")

    idx = req.slide_id - 1
    slide = structured_slides[idx]

    try:
        from services.llm_client import call_llm_json
        from pipeline.visual_design_engine import run_design_engine
        from pipeline.visual_template_engine import run_template_engine

        # Use LLM to regenerate slide content based on instruction
        system_prompt = (
            "You are a presentation content expert. Regenerate the slide content based on the instruction. "
            "Return a JSON object with the same structure as the input slide content. "
            "Keep the same slide type and structure. Only modify the content as instructed."
        )
        user_prompt = (
            f"Current slide content:\n{json.dumps(slide.get('content', {}), indent=2)}\n\n"
            f"Slide type: {slide.get('type', 'unknown')}\n\n"
            f"Instruction: {req.instruction or 'Improve this slide - make it more impactful and specific'}"
        )

        new_content = await call_llm_json(system_prompt, user_prompt)

        # Update the structured slide
        structured_slides[idx] = {**slide, "content": new_content}

        # Re-run design + template for just this slide
        designs = run_design_engine([structured_slides[idx]])
        new_html_list = run_template_engine(designs)

        if new_html_list:
            new_html = new_html_list[0]

            # Save the new HTML
            job_output_dir = _safe_job_dir(job_id)
            os.makedirs(job_output_dir, exist_ok=True)
            slide_path = os.path.join(job_output_dir, f"slide_{req.slide_id}.html")
            with open(slide_path, "w", encoding="utf-8") as f:
                f.write(new_html)

            # Update job store
            update_job(job_id, structured_slides=structured_slides)

            return {
                "slide_id": req.slide_id,
                "html_url": f"/outputs/{job_id}/slide_{req.slide_id}.html",
                "html": new_html,
                "content": new_content,
                "status": "regenerated",
            }
    except Exception as e:
        logger.exception("Slide regeneration failed for job %s slide %d", job_id, req.slide_id)
        raise HTTPException(status_code=500, detail=f"Regeneration failed: {str(e)}")

    raise HTTPException(status_code=500, detail="Regeneration produced no output")


@app.post("/restyle-slides/{job_id}")
async def restyle_slides(job_id: str, req: RestyleRequest):
    """Re-style all slides with a new theme."""
    job = get_job(job_id)
    if not job or job["status"] != "completed":
        raise HTTPException(status_code=404, detail="Job not completed")

    structured_slides = job.get("structured_slides", [])
    if not structured_slides:
        raise HTTPException(status_code=400, detail="No slides to restyle")

    try:
        from pipeline.visual_design_engine import run_design_engine
        from pipeline.visual_template_engine import run_template_engine

        designs = run_design_engine(structured_slides, state_theme=req.theme)
        html_slides = run_template_engine(designs)

        # Save restyled HTML slides
        job_output_dir = _safe_job_dir(job_id)
        os.makedirs(job_output_dir, exist_ok=True)
        html_slide_paths = []
        for idx, html in enumerate(html_slides):
            slide_path = os.path.join(job_output_dir, f"slide_{idx + 1}.html")
            with open(slide_path, "w", encoding="utf-8") as f:
                f.write(html)
            html_slide_paths.append(f"/outputs/{job_id}/slide_{idx + 1}.html")

        update_job(job_id, html_slides=html_slide_paths)

        return {
            "job_id": job_id,
            "theme": req.theme,
            "slides": [
                {"slide_id": idx + 1, "html_url": path, "html": html}
                for idx, (path, html) in enumerate(zip(html_slide_paths, html_slides))
            ],
            "status": "restyled",
        }
    except Exception as e:
        logger.exception("Restyle failed for job %s", job_id)
        raise HTTPException(status_code=500, detail=f"Restyle failed: {str(e)}")


@app.post("/update-slide/{job_id}")
async def update_slide(job_id: str, req: UpdateSlideRequest):
    """Update a slide's content (from inline editing)."""
    job = get_job(job_id)
    if not job or job["status"] != "completed":
        raise HTTPException(status_code=404, detail="Job not completed")

    structured_slides = job.get("structured_slides", [])
    if req.slide_id < 1 or req.slide_id > len(structured_slides):
        raise HTTPException(status_code=400, detail="Invalid slide_id")

    idx = req.slide_id - 1
    slide = structured_slides[idx]

    try:
        from pipeline.visual_design_engine import run_design_engine
        from pipeline.visual_template_engine import run_template_engine

        # Update the content
        structured_slides[idx] = {**slide, "content": req.content}

        # Re-render just this slide
        designs = run_design_engine([structured_slides[idx]])
        new_html_list = run_template_engine(designs)

        if new_html_list:
            new_html = new_html_list[0]
            job_output_dir = _safe_job_dir(job_id)
            os.makedirs(job_output_dir, exist_ok=True)
            slide_path = os.path.join(job_output_dir, f"slide_{req.slide_id}.html")
            with open(slide_path, "w", encoding="utf-8") as f:
                f.write(new_html)

            update_job(job_id, structured_slides=structured_slides)

            return {
                "slide_id": req.slide_id,
                "html_url": f"/outputs/{job_id}/slide_{req.slide_id}.html",
                "html": new_html,
                "status": "updated",
            }
    except Exception as e:
        logger.exception("Update failed for job %s slide %d", job_id, req.slide_id)
        raise HTTPException(status_code=500, detail=f"Update failed: {str(e)}")

    raise HTTPException(status_code=500, detail="Update produced no output")


@app.post("/reorder-slides/{job_id}")
async def reorder_slides(job_id: str, req: ReorderRequest):
    """Reorder slides for a job."""
    job = get_job(job_id)
    if not job or job["status"] != "completed":
        raise HTTPException(status_code=404, detail="Job not completed")

    structured_slides = job.get("structured_slides", [])
    html_slides = job.get("html_slides", [])

    # Validate all indices
    expected = set(range(1, len(structured_slides) + 1))
    if set(req.order) != expected:
        raise HTTPException(status_code=400, detail="Invalid slide order")

    # Reorder
    new_structured = [structured_slides[i - 1] for i in req.order]
    new_html = [html_slides[i - 1] for i in req.order]

    update_job(job_id, structured_slides=new_structured, html_slides=new_html)

    return {"job_id": job_id, "order": req.order, "status": "reordered"}


@app.post("/duplicate-slide/{job_id}")
async def duplicate_slide(job_id: str, req: DuplicateSlideRequest):
    """Duplicate a slide."""
    job = get_job(job_id)
    if not job or job["status"] != "completed":
        raise HTTPException(status_code=404, detail="Job not completed")

    structured_slides = job.get("structured_slides", [])
    html_slides = job.get("html_slides", [])

    if req.slide_id < 1 or req.slide_id > len(structured_slides):
        raise HTTPException(status_code=400, detail="Invalid slide_id")

    idx = req.slide_id - 1

    # Insert copy after the original
    new_slide = copy.deepcopy(structured_slides[idx])
    structured_slides.insert(idx + 1, new_slide)

    # Copy the HTML file on disk for the duplicated slide
    if idx < len(html_slides):
        original_html_path = html_slides[idx]
        job_output_dir = _safe_job_dir(job_id)
        original_file = os.path.join(job_output_dir, f"slide_{req.slide_id}.html")
        new_id = req.slide_id + 1
        new_file = os.path.join(job_output_dir, f"slide_{new_id}.html")
        if os.path.isfile(original_file):
            shutil.copy2(original_file, new_file)
        new_html_path = f"/outputs/{os.path.basename(job_id)}/slide_{new_id}.html"
    else:
        logger.warning("No HTML path found for slide %d in job %s", req.slide_id, job_id)
        new_html_path = ""
    html_slides.insert(idx + 1, new_html_path)

    update_job(job_id, structured_slides=structured_slides, html_slides=html_slides)

    return {
        "job_id": job_id,
        "new_slide_id": req.slide_id + 1,
        "total": len(structured_slides),
        "status": "duplicated",
    }


@app.delete("/delete-slide/{job_id}/{slide_id}")
async def delete_slide(job_id: str, slide_id: int):
    """Delete a slide."""
    job = get_job(job_id)
    if not job or job["status"] != "completed":
        raise HTTPException(status_code=404, detail="Job not completed")

    structured_slides = job.get("structured_slides", [])
    html_slides = job.get("html_slides", [])

    if slide_id < 1 or slide_id > len(structured_slides):
        raise HTTPException(status_code=400, detail="Invalid slide_id")

    if len(structured_slides) <= 1:
        raise HTTPException(status_code=400, detail="Cannot delete the last slide")

    idx = slide_id - 1

    # Remove the HTML file from disk
    if idx < len(html_slides):
        job_output_dir = _safe_job_dir(job_id)
        slide_file = os.path.join(job_output_dir, f"slide_{slide_id}.html")
        if os.path.isfile(slide_file):
            os.remove(slide_file)
        html_slides.pop(idx)

    structured_slides.pop(idx)

    update_job(job_id, structured_slides=structured_slides, html_slides=html_slides)

    return {"job_id": job_id, "deleted": slide_id, "total": len(structured_slides), "status": "deleted"}


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