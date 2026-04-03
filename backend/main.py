import uuid, asyncio, os
from fastapi import FastAPI, BackgroundTasks
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from orchestrator import run_pipeline
from config import settings

app = FastAPI(title="Narrato API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory job store (replace with Redis in production)
jobs: dict = {}

class GenerateRequest(BaseModel):
    prompt: str
    options: dict = {}

@app.post("/generate")
async def generate(req: GenerateRequest, background_tasks: BackgroundTasks):
    job_id = uuid.uuid4().hex
    jobs[job_id] = {"status": "processing", "path": None, "error": None}
    background_tasks.add_task(_run_job, job_id, req.prompt, req.options)
    return {"job_id": job_id, "status": "processing", "estimated_seconds": 30}

async def _run_job(job_id: str, prompt: str, options: dict):
    try:
        path = await run_pipeline(prompt, options)
        jobs[job_id] = {"status": "completed", "path": path, "error": None}
    except Exception as e:
        jobs[job_id] = {"status": "failed", "path": None, "error": str(e)}

@app.get("/status/{job_id}")
async def status(job_id: str):
    job = jobs.get(job_id)
    if not job:
        return {"status": "not_found"}
    resp = {"job_id": job_id, "status": job["status"]}
    if job["status"] == "completed":
        resp["download_url"] = f"/download/{job_id}"
    if job["status"] == "failed":
        resp["error"] = job["error"]
    return resp

@app.get("/download/{job_id}")
async def download(job_id: str):
    job = jobs.get(job_id)
    if not job or job["status"] != "completed":
        return {"error": "Not ready"}
    return FileResponse(
        job["path"],
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        filename="narrato.pptx"
    )

@app.get("/health")
async def health():
    return {"status": "ok", "version": "1.0.0"}