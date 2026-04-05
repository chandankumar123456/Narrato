import asyncio
import sys

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    
import uuid, asyncio, os, logging, glob, json, copy, shutil
from fastapi import FastAPI, BackgroundTasks, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from orchestrator import run_pipeline
from config import settings
from services.job_store import set_job, get_job, update_job, append_event, get_events
from services.event_system import PipelineEvent, EventType

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

# Serve visual rendering output (HTML, PNG, PDF)
VISUAL_DIR = os.path.join(settings.output_dir, "visual")
os.makedirs(VISUAL_DIR, exist_ok=True)
app.mount("/visual", StaticFiles(directory=VISUAL_DIR), name="visual")


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
    pdf_path: Optional[str] = None
    image_paths: Optional[list] = None


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

        def _event(evt: PipelineEvent):
            """Store event in the job event log for SSE streaming."""
            append_event(job_id, evt.to_dict())
            update_job(job_id, progress=evt.progress)

        # Inject job_id into options so orchestrator can reference it
        run_options = {**options, "_job_id": job_id}
        result = await run_pipeline(prompt, run_options,
                                    progress_callback=_progress,
                                    event_callback=_event)
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
        for idx, html in enumerate(html_slides or []):
            slide_path = os.path.join(job_output_dir, f"slide_{idx + 1}.html")
            with open(slide_path, "w", encoding="utf-8") as f:
                f.write(html)
            html_slide_paths.append(f"/outputs/{safe_id}/slide_{idx + 1}.html")

        set_job(job_id, status="completed", progress=100,
                html_slides=html_slide_paths, structured_slides=structured_slides,
                pdf_path=pdf_path, image_paths=image_paths)
    except Exception as e:
        logger.exception("[api] Job %s failed", job_id)
        # Emit failure event
        fail_evt = PipelineEvent(
            job_id=job_id,
            type=EventType.JOB_FAILED,
            stage="failed",
            progress=0,
            label="Generation failed",
            data={"error": str(e)},
        )
        append_event(job_id, fail_evt.to_dict())
        set_job(job_id, status="failed", error=str(e), html_slides=[])


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
        resp.html_slides = job.get("html_slides") or []
        resp.pdf_path = job.get("pdf_path")
        resp.image_paths = job.get("image_paths") or []
    if job["status"] == "failed":
        resp.error = job.get("error")
        resp.html_slides = []
        resp.image_paths = []
    return resp


@app.get("/download/{job_id}")
async def download(job_id: str):
    """Download the generated PDF for a completed job."""
    job = get_job(job_id)
    if not job or job["status"] != "completed":
        raise HTTPException(status_code=404, detail="File not ready")

    pdf_path = job.get("pdf_path")
    if pdf_path and os.path.isfile(pdf_path):
        return FileResponse(
            pdf_path,
            media_type="application/pdf",
            filename="narrato.pdf"
        )

    # Fallback: try to find a PDF in the visual output directory
    visual_pdf = os.path.join(VISUAL_DIR, "presentation.pdf")
    if os.path.isfile(visual_pdf):
        return FileResponse(
            visual_pdf,
            media_type="application/pdf",
            filename="narrato.pdf"
        )

    raise HTTPException(status_code=404, detail="PDF not found — rendering engine may not be available")


@app.post("/preview/{job_id}")
async def generate_preview(job_id: str):
    """Return HTML slide URLs as previews for a completed job.

    No external tools needed — slides are already HTML files.
    """
    job = get_job(job_id)
    if not job or job["status"] != "completed":
        raise HTTPException(status_code=404, detail="Job not completed")

    html_slides = job.get("html_slides") or []
    if html_slides:
        return {"preview_urls": html_slides}

    return {"preview_urls": [], "message": "No slides available for preview"}


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


# ── Server-Sent Events (SSE) streaming endpoint ───────────────────


def _make_terminal_sse(event_type: str, stage: str, progress: int, label: str, error: str = "") -> str:
    """Build a terminal SSE data line for completed/failed events."""
    payload = {"type": event_type, "stage": stage, "progress": progress, "label": label}
    if error:
        payload["data"] = {"error": error}
    return f"data: {json.dumps(payload)}\n\n"


@app.get("/stream/{job_id}")
async def stream_events(job_id: str, request: Request):
    """Stream pipeline events via SSE.

    The client opens an EventSource connection. We poll the event log
    and push new events as they arrive. The stream closes on
    JOB_COMPLETED or JOB_FAILED.
    """
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    async def event_generator():
        cursor = 0
        max_idle_iterations = 600  # 5 minutes at 0.5s per iteration
        idle_count = 0
        while True:
            # Check if client disconnected
            if await request.is_disconnected():
                break

            new_events = get_events(job_id, after=cursor)
            if new_events:
                idle_count = 0  # Reset idle counter on new events
            else:
                idle_count += 1

            for evt in new_events:
                yield f"data: {json.dumps(evt)}\n\n"
                cursor += 1

                # Stop streaming after terminal events
                if evt.get("type") in (EventType.JOB_COMPLETED, EventType.JOB_FAILED):
                    return

            # Also check job status for terminal state (safety net)
            current_job = get_job(job_id)
            if current_job and current_job.get("status") in ("completed", "failed"):
                # If job is done but we already sent a terminal event, stop
                if any(e.get("type") in (EventType.JOB_COMPLETED, EventType.JOB_FAILED)
                       for e in new_events):
                    return
                # If no terminal event in log yet but job is done, synthesize one
                if current_job["status"] == "completed":
                    yield _make_terminal_sse(EventType.JOB_COMPLETED, "completed", 100, "Presentation ready!")
                else:
                    yield _make_terminal_sse(EventType.JOB_FAILED, "failed", 0, "Generation failed", current_job.get("error", ""))
                return

            # Prevent infinite polling — terminate after max idle time
            if idle_count >= max_idle_iterations:
                logger.warning("[stream] Terminating SSE stream for job %s after %d idle iterations", job_id, idle_count)
                yield _make_terminal_sse(EventType.JOB_FAILED, "timeout", 0, "Stream timed out")
                return

            await asyncio.sleep(0.5)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ── Interactive Product Layer endpoints ────────────────────────────────


def _safe_job_dir(job_id: str) -> tuple[str, str]:
    """Return a validated (job_output_dir, safe_id) tuple, preventing path traversal.

    Validates safe_id contains no path separators and resolves within output_dir.
    """
    safe_id = os.path.basename(job_id)
    # Reject any remaining path separators or traversal attempts
    if not safe_id or "/" in safe_id or "\\" in safe_id or ".." in safe_id:
        raise HTTPException(status_code=400, detail="Invalid job_id: path traversal rejected")
    job_dir = os.path.realpath(os.path.join(settings.output_dir, safe_id))
    real_output = os.path.realpath(settings.output_dir)
    try:
        common = os.path.commonpath([job_dir, real_output])
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid job_id: path traversal rejected")
    if common != real_output:
        raise HTTPException(status_code=400, detail="Invalid job_id: path traversal rejected")
    return job_dir, safe_id


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

    html_slides = job.get("html_slides") or []
    structured_slides = job.get("structured_slides") or []

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

    structured_slides = job.get("structured_slides") or []
    html_slides = job.get("html_slides") or []

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
            job_output_dir, safe_id = _safe_job_dir(job_id)
            os.makedirs(job_output_dir, exist_ok=True)
            slide_path = os.path.join(job_output_dir, f"slide_{req.slide_id}.html")
            with open(slide_path, "w", encoding="utf-8") as f:
                f.write(new_html)

            # Update job store
            update_job(job_id, structured_slides=structured_slides)

            return {
                "slide_id": req.slide_id,
                "html_url": f"/outputs/{safe_id}/slide_{req.slide_id}.html",
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

    structured_slides = job.get("structured_slides") or []
    if not structured_slides:
        raise HTTPException(status_code=400, detail="No slides to restyle")

    try:
        from pipeline.visual_design_engine import run_design_engine
        from pipeline.visual_template_engine import run_template_engine

        designs = run_design_engine(structured_slides, state_theme=req.theme)
        html_slides = run_template_engine(designs)

        # Save restyled HTML slides
        job_output_dir, safe_id = _safe_job_dir(job_id)
        os.makedirs(job_output_dir, exist_ok=True)
        html_slide_paths = []
        for idx, html in enumerate(html_slides or []):
            slide_path = os.path.join(job_output_dir, f"slide_{idx + 1}.html")
            with open(slide_path, "w", encoding="utf-8") as f:
                f.write(html)
            html_slide_paths.append(f"/outputs/{safe_id}/slide_{idx + 1}.html")

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

    structured_slides = job.get("structured_slides") or []
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
            job_output_dir, safe_id = _safe_job_dir(job_id)
            os.makedirs(job_output_dir, exist_ok=True)
            slide_path = os.path.join(job_output_dir, f"slide_{req.slide_id}.html")
            with open(slide_path, "w", encoding="utf-8") as f:
                f.write(new_html)

            update_job(job_id, structured_slides=structured_slides)

            return {
                "slide_id": req.slide_id,
                "html_url": f"/outputs/{safe_id}/slide_{req.slide_id}.html",
                "html": new_html,
                "status": "updated",
            }
    except Exception as e:
        logger.exception("Update failed for job %s slide %d", job_id, req.slide_id)
        raise HTTPException(status_code=500, detail=f"Update failed: {str(e)}")

    raise HTTPException(status_code=500, detail="Update produced no output")


def _renumber_html_slides(job_id: str, html_slides: list[str]) -> list[str]:
    """Re-save and renumber HTML slide files to ensure contiguous numbering.

    Reads existing HTML content from old paths, writes to new sequential paths,
    and cleans up stale files. Returns the updated list of html_slide paths.

    Security: validates every resolved filepath is within job_output_dir.
    Uses a temp directory to avoid partial state on failure.
    """
    job_output_dir, safe_id = _safe_job_dir(job_id)
    os.makedirs(job_output_dir, exist_ok=True)
    real_job_dir = os.path.realpath(job_output_dir)

    # Read all existing HTML content — validate each path is within job dir
    contents = []
    for path_url in html_slides:
        # path_url is like /outputs/{safe_id}/slide_N.html — extract basename
        filename = os.path.basename(path_url)
        # Reject filenames containing path separators or suspicious chars
        if "/" in filename or "\\" in filename or ".." in filename:
            contents.append("")
            continue
        filepath = os.path.realpath(os.path.join(job_output_dir, filename))
        # Ensure resolved path is within the job output directory
        try:
            if os.path.commonpath([filepath, real_job_dir]) != real_job_dir:
                contents.append("")
                continue
        except ValueError:
            contents.append("")
            continue
        content = ""
        if os.path.isfile(filepath):
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
        contents.append(content)

    # Write new files to a temp directory first (atomic swap)
    import tempfile
    tmp_dir = tempfile.mkdtemp(dir=job_output_dir)
    new_paths = []
    try:
        for idx, content in enumerate(contents):
            new_num = idx + 1
            tmp_file = os.path.join(tmp_dir, f"slide_{new_num}.html")
            with open(tmp_file, "w", encoding="utf-8") as f:
                f.write(content)
            new_paths.append(f"/outputs/{safe_id}/slide_{new_num}.html")

        # Remove old slide files
        for existing in glob.glob(os.path.join(job_output_dir, "slide_*.html")):
            os.remove(existing)

        # Move new files into place
        for fname in os.listdir(tmp_dir):
            shutil.move(os.path.join(tmp_dir, fname),
                        os.path.join(job_output_dir, fname))
    finally:
        # Clean up temp directory
        if os.path.isdir(tmp_dir):
            shutil.rmtree(tmp_dir, ignore_errors=True)

    return new_paths


@app.post("/reorder-slides/{job_id}")
async def reorder_slides(job_id: str, req: ReorderRequest):
    """Reorder slides for a job."""
    job = get_job(job_id)
    if not job or job["status"] != "completed":
        raise HTTPException(status_code=404, detail="Job not completed")

    structured_slides = job.get("structured_slides") or []
    html_slides = job.get("html_slides") or []

    # Validate all indices
    expected = set(range(1, len(structured_slides) + 1))
    if set(req.order) != expected:
        raise HTTPException(status_code=400, detail="Invalid slide order")

    # Reorder in memory
    new_structured = [structured_slides[i - 1] for i in req.order]
    new_html = [html_slides[i - 1] for i in req.order]

    # Renumber files on disk
    new_html = _renumber_html_slides(job_id, new_html)

    update_job(job_id, structured_slides=new_structured, html_slides=new_html)

    return {"job_id": job_id, "order": req.order, "status": "reordered"}


@app.post("/duplicate-slide/{job_id}")
async def duplicate_slide(job_id: str, req: DuplicateSlideRequest):
    """Duplicate a slide."""
    job = get_job(job_id)
    if not job or job["status"] != "completed":
        raise HTTPException(status_code=404, detail="Job not completed")

    structured_slides = job.get("structured_slides") or []
    html_slides = job.get("html_slides") or []

    if req.slide_id < 1 or req.slide_id > len(structured_slides):
        raise HTTPException(status_code=400, detail="Invalid slide_id")

    idx = req.slide_id - 1

    # Insert copy after the original
    new_slide = copy.deepcopy(structured_slides[idx])
    structured_slides.insert(idx + 1, new_slide)

    # Duplicate the html path reference (temporary — will be renumbered)
    dup_path = html_slides[idx] if idx < len(html_slides) else ""
    html_slides.insert(idx + 1, dup_path)

    # Renumber all files on disk to maintain consistency
    html_slides = _renumber_html_slides(job_id, html_slides)

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

    structured_slides = job.get("structured_slides") or []
    html_slides = job.get("html_slides") or []

    if slide_id < 1 or slide_id > len(structured_slides):
        raise HTTPException(status_code=400, detail="Invalid slide_id")

    if len(structured_slides) <= 1:
        raise HTTPException(status_code=400, detail="Cannot delete the last slide")

    idx = slide_id - 1
    structured_slides.pop(idx)
    if idx < len(html_slides):
        html_slides.pop(idx)

    # Renumber remaining files on disk
    html_slides = _renumber_html_slides(job_id, html_slides)

    update_job(job_id, structured_slides=structured_slides, html_slides=html_slides)

    return {"job_id": job_id, "deleted": slide_id, "total": len(structured_slides), "status": "deleted"}


# ── Visual Rendering Engine endpoints ────────────────────────────────


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
