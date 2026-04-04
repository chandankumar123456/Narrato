# Narrato Backend

Deep technical documentation for the Narrato pipeline, API, and infrastructure.

---

## Overview

The backend is a FastAPI application that orchestrates an AI-powered presentation generation pipeline. It accepts natural language prompts, runs them through a multi-stage content and visual pipeline, and produces HTML slides + PPTX files with real-time progress streaming via Server-Sent Events.

**Core components:**
- `main.py` — FastAPI app with all endpoints
- `orchestrator.py` — Pipeline controller with event emission
- `worker.py` — Celery worker for production async execution
- `pipeline/` — 20+ independent pipeline stage modules
- `services/` — LLM client, job store, event system, image service

---

## Core Architecture

```
                    ┌─────────────────────────────┐
                    │        FastAPI App           │
                    │         (main.py)            │
                    └──────┬──────────┬────────────┘
                           │          │
              ┌────────────▼──┐  ┌────▼────────────┐
              │  Background   │  │   Celery Worker  │
              │  Task (dev)   │  │   (production)   │
              └──────┬────────┘  └────┬─────────────┘
                     │                │
                     ▼                ▼
              ┌───────────────────────────────┐
              │        Orchestrator           │
              │      (orchestrator.py)        │
              │                               │
              │  ┌─────────────────────────┐  │
              │  │  event_callback(evt) ───┼──┼──► job_store.append_event()
              │  │  progress_callback(%) ──┼──┼──► job_store.update_job()
              │  └─────────────────────────┘  │
              │                               │
              │  Pipeline Stage 1             │
              │  Pipeline Stage 2             │
              │  ...                          │
              │  Pipeline Stage N             │
              └───────────────────────────────┘
```

**Execution paths:**
1. **Local dev** — `_run_job()` runs pipeline directly in FastAPI's background task executor
2. **Production** — Celery task `generate_presentation_task` runs pipeline in a worker process

Both paths use identical event emission and job store updates.

---

## Orchestrator Design

**File**: `orchestrator.py`

The orchestrator (`run_pipeline`) is the central controller. It:
1. Receives prompt + options
2. Executes pipeline stages in sequence
3. Emits `PipelineEvent` at every meaningful step
4. Computes deterministic progress percentages
5. Returns `{pptx_path, html_slides, structured_slides}`

### Pipeline Stages (Default Mode)

| # | Stage | Module | Event |
|---|-------|--------|-------|
| 1 | Parse prompt | `prompt_understanding.py` | `STAGE_UPDATE` init |
| 2 | Parse schema | `schema_parser.py` | `STAGE_UPDATE` prompt_parsed |
| 3 | Build state | `state_builder.py` | `STAGE_UPDATE` state_built |
| 4 | Complete state | `state_completion.py` | `STAGE_UPDATE` state_complete |
| 5 | Generate story | `story_generator.py` | `STAGE_UPDATE` story |
| 6 | Plan slides + assign types | `slide_planner.py`, `slide_type_assigner.py` | `STAGE_UPDATE` slide_plan |
| 7 | Multi-stage content | `multi_stage_content.py` | `STAGE_UPDATE` content_done |
| 8 | Slide evaluator | `slide_evaluator.py` | `STAGE_UPDATE` evaluated |
| 9 | Deck consistency | `deck_consistency_optimizer.py` | `STAGE_UPDATE` consistency |
| 10 | Visual queries | `visual_mapper.py` | `STAGE_UPDATE` visual_queries |
| 11 | Speaker notes | `speaker_notes_generator.py` | `STAGE_UPDATE` speaker_notes |
| 12 | Intelligence report | `intelligence_report.py` | `STAGE_UPDATE` report |
| 13 | Per-slide design | `visual_design_engine.py` | `SLIDE_DESIGNED` per slide |
| 14 | Per-slide render | `visual_template_engine.py` | `SLIDE_RENDERED` per slide |
| 15 | Full visual pipeline | `visual_rendering_pipeline.py` | — |
| 16 | PPT generation | `ppt/generator.py` | `STAGE_UPDATE` ppt |
| 17 | Completion | — | `JOB_COMPLETED` |

### Pipeline Stages (Strict Mode)

Activated when `parse_user_schema` detects a structured schema in the prompt. Uses:
- `strict_slide_planner.py` instead of `slide_planner.py`
- `strict_content_structurer.py` instead of `multi_stage_content.py`
- `content_validator.py` for schema compliance validation
- Skips story generation, evaluator, and consistency optimizer
- Joins the shared tail at stage 10 (visual queries)

### Event Emission Points

Every `_emit()` call sends a `PipelineEvent` to:
1. `event_callback` → `job_store.append_event()` (for SSE)
2. `progress_callback` → `job_store.update_job()` (for polling fallback)

---

## Event System

**File**: `services/event_system.py`

### EventType Enum

```python
STAGE_UPDATE    # Pipeline stage progress
SLIDE_GENERATED # Slide content created (unused currently)
SLIDE_DESIGNED  # Slide design spec computed
SLIDE_RENDERED  # Slide HTML generated (includes HTML in data.html)
JOB_COMPLETED   # Terminal: pipeline finished
JOB_FAILED      # Terminal: pipeline errored
```

### PipelineEvent Structure

```python
@dataclass
class PipelineEvent:
    job_id: str
    type: str              # EventType value
    stage: str             # Machine-readable stage identifier
    progress: int          # 0–100
    label: str             # Human-readable status message
    slide_id: int | None   # Set for per-slide events
    total_slides: int | None
    data: dict | None      # Arbitrary payload (e.g., {"html": "..."})
    timestamp: float       # time.time()
```

### Event Flow

```
orchestrator._emit()
    │
    ▼
PipelineEvent(job_id, type, stage, progress, label, ...)
    │
    ▼
event_callback(evt)      # Provided by main.py or worker.py
    │
    ▼
job_store.append_event(job_id, evt.to_dict())
    │
    ├──► Redis: RPUSH narrato:events:{job_id} (JSON)
    └──► Fallback: _event_store[job_id].append(dict)
```

---

## Real-time Streaming (SSE)

**Endpoint**: `GET /stream/{job_id}`

### Behavior

1. Client opens `EventSource("/stream/{job_id}")`
2. Server polls `get_events(job_id, after=cursor)` every 500ms
3. New events are sent as `data: {JSON}\n\n`
4. Stream terminates on `JOB_COMPLETED` or `JOB_FAILED`
5. Safety net: checks `get_job()` status for terminal state even if no terminal event in log

### SSE Wire Format

```
data: {"job_id":"abc","type":"STAGE_UPDATE","stage":"story","progress":20,"label":"Story framework created…","timestamp":1234567890.0}

data: {"job_id":"abc","type":"SLIDE_RENDERED","stage":"render","progress":75,"label":"Rendered slide 3 of 10…","slide_id":3,"total_slides":10,"data":{"html":"<!DOCTYPE html>..."}}

data: {"job_id":"abc","type":"JOB_COMPLETED","stage":"completed","progress":100,"label":"Presentation ready!"}
```

### Headers

```
Content-Type: text/event-stream
Cache-Control: no-cache
Connection: keep-alive
X-Accel-Buffering: no
```

---

## Job System

**File**: `services/job_store.py`

### Job Lifecycle

```
queued ──► processing ──► completed
                │
                └──► failed
```

### Storage

- **Primary**: Redis with 24-hour TTL (`narrato:job:{job_id}`)
- **Fallback**: In-memory dict when Redis is unavailable
- **Detection**: Lazy connection on first access; logs warning on fallback

### Job Data Schema

```python
{
    "status": "queued" | "processing" | "completed" | "failed",
    "path": str | None,          # PPTX file path
    "error": str | None,         # Error message if failed
    "progress": int | None,      # 0–100
    "preview_urls": list | None, # Preview image URLs
    "html_slides": list | None,  # HTML slide URL paths
    "structured_slides": list | None,  # Structured slide data
}
```

### Event Log

- **Redis**: `RPUSH narrato:events:{job_id}` (JSON-serialized events), 24h TTL
- **Fallback**: `_event_store[job_id]` (in-memory list)
- **Retrieval**: `get_events(job_id, after=cursor)` returns events from index `after` onward
- Cursor-based: SSE endpoint tracks its own cursor for efficient incremental reads

---

## Pipeline Breakdown

### 1. Prompt Understanding (`prompt_understanding.py`)

LLM extracts structured signals from the natural language prompt:
- `topic`, `presentation_type` (pitch/educational/report/general)
- `slide_count`, `sections`, `tone`, `audience`
- `examples_count`, `image_preference`, `language`

### 2. Schema Parser (`schema_parser.py`)

Detects if the prompt contains a structured schema (strict mode trigger). Extracts:
- `topic`, `examples_required`, `fields_required`

### 3. State Builder (`state_builder.py`)

Constructs `PresentationState` (Pydantic model) from parsed signals. In strict mode, structural parameters are derived only from the schema. Slide count is clamped to 5–30 in default mode; exact count in strict mode.

### 4. Story Generator (`story_generator.py`)

Maps `presentation_type` to narrative archetype:
- `pitch` → problem-solution
- `educational` → educational-journey
- `report` → data-driven
- `general` → problem-solution

Outputs: `narrative_type`, `key_message`, `hook`, `sections_flow` (section/purpose/emotion), `call_to_action`.

### 5. Slide Planner (`slide_planner.py`)

Allocates slides across sections using weighted distribution:
- intro: 10%, problem: 20%, solution: 25%, benefits: 30%, conclusion: 15%
- Section headers inserted between sections
- Each slide gets: `slide_id`, `section`, `purpose`, `type`

### 6. Multi-Stage Content (`multi_stage_content.py`)

Per-slide content generation with 4-phase quality loop:

| Phase | Purpose | Mechanism |
|-------|---------|-----------|
| 1 | Generation | 3–4 mechanism-driven bullets per slide |
| 2 | Self-validation | Checks for repetition, generic phrases, shallow depth |
| 3 | Critic loop | Investor-mode evaluation, max 3 regeneration attempts |
| 4 | Intent enforcement | Ensures slide matches its declared purpose |

Previous slide contents are passed to prevent cross-slide repetition.

### 7. Slide Evaluator (`slide_evaluator.py`)

Post-generation quality gate with 6 phases:

1. **Hard validation** — 14 deterministic banned phrases, minimum 6 words per bullet
2. **LLM scoring** — 4 dimensions (specificity, mechanism, uniqueness, clarity), minimum 4.0/5
3. **Strict critic** — No-mercy investor-mode evaluation
4. **Targeted regeneration** — Specific fix instructions, max 3 attempts
5. **Intent enforcement** — Ensures slide matches declared intent
6. **Final output** — Improved slide + evaluation report

Results stored in `state.metadata["slide_evaluations"]`.

### 8. Deck Consistency Optimizer (`deck_consistency_optimizer.py`)

Full-deck alignment pass (runs after per-slide evaluation):

1. **Weak slide detection** — Flags slides with score gap ≥ 1.0 below deck's best
2. **Terminology drift** — LLM detects inconsistent term usage across deck
3. **Generic phrase scan** — Deterministic check for 14 banned phrases
4. **Bullet structure consistency** — Flags word-length outliers across bullets
5. **Targeted rewrite** — LLM rewrites flagged slides, max 2 attempts

Results stored in `state.metadata["deck_consistency"]`.

### 9. Visual Design Engine (`visual_design_engine.py`)

**Stage 1** of the visual rendering pipeline. Determines per-slide:
- **Layout**: `hero_center`, `grid_cards`, `split_left_text_right_visual`, `step_flow`, `stats_blocks`, `timeline_flow`
- **Theme**: `dark_modern` (default), `minimal_light`, `bold_gradient`
- **Components**: extracted from slide content (title, subtitle, bullets, stats, steps, etc.)

Layout is mapped from slide type/intent via `INTENT_LAYOUT_MAP`. Each theme defines 14+ visual tokens (backgrounds, text colors, card styles, accent gradients, shadows).

### 10. Visual Template Engine (`visual_template_engine.py`)

**Stage 2**: Converts design specs into standalone HTML slides using Tailwind CSS CDN.

Each slide is a complete HTML document rendered at 1920×1080 with:
- Visual hierarchy (title dominance, supporting elements recede)
- Focal point design (one dominant element per slide)
- Asymmetric spacing rhythm (top-heavy breathing, dense middle, open bottom)
- Premium card styles (glass morphism, shadows, layering)
- Typography scale (8xl / 6xl / 3xl / lg / sm)
- HTML-escaped content to prevent XSS

### 11. Visual Rendering Engine (`visual_rendering_engine.py`)

**Stage 3**: Renders HTML slides to PNG images and combined PDF using Playwright at 1920×1080. Falls back to instruction-only mode when Playwright is not installed.

### 12. Visual Export Engine (`visual_export_engine.py`)

**Stage 4**: Produces final export artifacts:
- HTML files (one per slide)
- PNG images (from rendering engine)
- PDF (combined document)
- Image-based PPT (slides as full-bleed images via python-pptx)

---

## Progress Calculation

Progress is computed deterministically:

```
GLOBAL_STEPS = 11   # parse + schema + state + story + plan + evaluator +
                     # consistency + visuals + notes + report + ppt

per_slide_steps = 3  # content(1) + design(1) + render(1)

total_steps = GLOBAL_STEPS + (total_slides × per_slide_steps)

progress = min(100, (completed_steps / total_steps) × 100)
```

For a 10-slide presentation: `total_steps = 11 + 30 = 41`.

`total_slides` is recalculated after slide planning (actual planned count may differ from initial estimate).

---

## File Storage

```
outputs/
├── {job_id}/                 # Per-job output directory
│   ├── slide_1.html          # Rendered HTML slides
│   ├── slide_2.html
│   └── ...
├── previews/
│   └── {job_id}/             # LibreOffice-generated preview images
│       ├── slide-01.png
│       └── ...
├── visual/                   # Visual pipeline output
│   ├── slide_1.html
│   ├── slide_1.png
│   └── combined.pdf
├── narrato.pptx              # Generated PPTX
└── INTELLIGENCE_REPORT.md    # Pipeline behavior evaluation
```

---

## API Endpoints

### Generation & Status

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/generate` | Start presentation generation. Body: `{prompt, options}`. Returns `{job_id, status, estimated_seconds}` |
| `GET` | `/status/{job_id}` | Poll job status. Returns `{job_id, status, progress, download_url, preview_urls, html_slides, error}` |
| `GET` | `/download/{job_id}` | Download completed PPTX file |
| `POST` | `/preview/{job_id}` | Trigger LibreOffice preview image generation |
| `GET` | `/stream/{job_id}` | SSE stream of pipeline events |
| `GET` | `/health` | Health check (Redis + Celery status) |

### Interactive Editor

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/slides/{job_id}` | Get all slides with HTML URLs and structured content |
| `POST` | `/regenerate-slide/{job_id}` | Regenerate single slide. Body: `{slide_id, instruction}` |
| `POST` | `/restyle-slides/{job_id}` | Restyle all slides. Body: `{theme, density}` |
| `POST` | `/update-slide/{job_id}` | Update slide content. Body: `{slide_id, content}` |
| `POST` | `/reorder-slides/{job_id}` | Reorder slides. Body: `{order: [3,1,2,...]}` |
| `POST` | `/duplicate-slide/{job_id}` | Duplicate a slide. Body: `{slide_id}` |
| `DELETE` | `/delete-slide/{job_id}/{slide_id}` | Delete a slide |

### Visual Assets

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/visual/slides/{job_id}` | Get visual pipeline output paths (HTML, PNG, PDF) |
| Static | `/outputs/{job_id}/...` | Serve per-job HTML slide files |
| Static | `/previews/{job_id}/...` | Serve preview images |
| Static | `/visual/...` | Serve visual pipeline assets |

### Input Validation

- Prompt: non-empty, max 5000 characters
- Slide ID: 1-based, within bounds of existing slides
- Cannot delete the last remaining slide
- Reorder: must contain all slide IDs exactly once

---

## Error Handling

### Pipeline Errors

- Each pipeline stage is called sequentially; unhandled exceptions propagate to `_run_job()`
- On failure: `JOB_FAILED` event is emitted, job status set to `failed` with error message
- Celery tasks retry up to 2 times with 10-second delay

### LLM Errors

- `llm_client.py` retries 3 times with exponential backoff (1s, 2s, 4s)
- Concurrent calls limited to 3 via `asyncio.Semaphore(3)`
- JSON parsing failures raise `ValueError` with raw LLM output for debugging
- Markdown code fences are stripped before JSON parsing

### API Errors

- Global exception handler returns `{"error": "Internal server error", "detail": ...}`
- 404 for missing jobs, 400 for invalid inputs
- CORS configured for `localhost:5173` (Vite) and `localhost:3000`

---

## Security

### Path Traversal Protection

- `_safe_job_dir(job_id)` validates job IDs: rejects path separators, `..`, and paths resolving outside `output_dir`
- Uses `os.path.commonpath()` to verify resolved paths
- Preview generation validates PPTX path is within output directory
- `_renumber_html_slides()` validates every file path resolves within the job directory
- Uses temp directory for atomic file renumbering to prevent partial state

### Content Safety

- `visual_template_engine.py` HTML-escapes all slide content via `html.escape()` before rendering
- `EditModal.jsx` guards against prototype pollution: blocks `__proto__`, `constructor`, `prototype` keys in nested paths
- Iframe sandbox: `allow-same-origin` for rendering, `allow-scripts` only in editor canvas
- Processing page iframes use `allow-same-origin` only with `pointer-events-none`

---

## Local Setup

```bash
# 1. Prerequisites
# Python 3.11+, uv (https://docs.astral.sh/uv/)

# 2. Install dependencies (from project root)
uv sync

# 3. Configure environment
cp ../.env.example ../.env
# Edit .env:
#   OPENAI_API_KEY=sk-...       (required)
#   LLM_PROVIDER=openai          (or anthropic)
#   LLM_MODEL=gpt-4o-mini        (default)
#   REDIS_URL=redis://localhost:6379/0  (optional)

# 4. Start the API server
uv run uvicorn main:app --port 8000 --reload
# API docs: http://localhost:8000/docs

# 5. Run tests
uv run python -m pytest tests/ -v --ignore=tests/test_api.py
```

### Redis (optional)

```bash
# Without Redis: uses in-memory job store (fine for local dev)
# With Redis:
redis-server
# Set REDIS_URL in .env
```

### Celery (optional, for production-like async)

```bash
uv run celery -A worker.celery_app worker --loglevel=info
```

---

## Production Setup

### Deployment

```
                    ┌─────────────────┐
                    │     nginx       │
                    │  reverse proxy  │
                    └──┬──────────┬───┘
                       │          │
              ┌────────▼──┐  ┌───▼──────────┐
              │  Frontend  │  │  FastAPI      │
              │  (static)  │  │  (uvicorn)   │
              └────────────┘  └──────┬───────┘
                                     │
                            ┌────────▼────────┐
                            │     Redis        │
                            └──┬──────────┬────┘
                               │          │
                      ┌────────▼──┐  ┌────▼────────┐
                      │  Celery   │  │  Celery      │
                      │  Worker 1 │  │  Worker N    │
                      └───────────┘  └──────────────┘
```

### Scaling Notes

- **API servers**: Stateless, scale horizontally behind load balancer
- **Celery workers**: Scale independently; each worker handles one pipeline at a time (`worker_prefetch_multiplier=1`)
- **Redis**: Single instance sufficient for moderate load; Redis Cluster for high availability
- **File storage**: Local `./outputs/` in dev; replace with S3/GCS in production
- **Task limits**: `task_soft_time_limit=120s`, `task_time_limit=180s`
- **LLM concurrency**: Semaphore limits to 3 concurrent LLM calls per process
