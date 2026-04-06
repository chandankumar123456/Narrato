# Narrato

**AI-powered presentation engine that converts natural language prompts into structured, visually rendered slide decks with real-time streaming feedback.**

---

## Problem

Existing presentation tools (Google Slides, Canva, Gamma) either:

- Require manual layout and design work for every slide
- Generate surface-level AI content without narrative structure
- Lack quality gates — output is generic, repetitive, and shallow
- Provide no real-time feedback during generation
- Offer no post-generation editing with AI assistance

## Solution

Narrato runs a **multi-stage AI pipeline** with built-in quality enforcement:

1. **Prompt understanding** — extracts topic, audience, tone, structure from natural language
2. **Story generation** — builds a narrative arc before any slide exists
3. **Multi-stage content** — generates, validates, critiques, and enforces intent per slide
4. **Slide evaluation** — deterministic + LLM scoring with automatic regeneration
5. **Deck consistency** — cross-slide alignment for tone, terminology, and depth
6. **Visual rendering** — design engine → content-aware layout variants → template engine (embedded CSS) → HTML slides at 1920×1080
7. **Real-time streaming** — SSE events push progress and rendered slides to the UI as they complete

The output is a fully styled HTML slide deck with PPTX export. Slides are **design-driven** (strict visual hierarchy, layout variation, transformed stats/titles) rather than a single repeated template.

---

## Key Features

- **Event-driven pipeline** — every stage emits structured events via SSE
- **Progressive slide rendering** — slides appear in the UI as they are designed and rendered
- **Two generation modes** — default (narrative-driven) and strict (schema-driven)
- **Quality gates** — 14 banned generic phrases, minimum word counts, LLM scoring (4 dimensions, min 4.0/5)
- **Critic loop** — investor-mode evaluation with up to 3 regeneration attempts per slide
- **Deck consistency optimizer** — detects weak slides, terminology drift, bullet structure outliers
- **Intelligence report** — auto-generated evaluation of pipeline behavior per run
- **Interactive editor** — post-generation slide editing, AI-assisted regeneration, theme switching
- **Multi-provider LLM** — OpenAI and Anthropic with retry + backoff
- **Presentation design layer** — per-slide rhythm (airy/standard/dense), layout variants (editorial hero, bento grid, stats spotlight, asymmetric split), and content visual transforms (e.g. mega stat + context line)
- **Stock image queries** — optional Unsplash/Pexels queries for pipeline metadata; slide chrome is HTML + CSS (no slide image dependency)
- **Celery + Redis** for production job queues, in-memory fallback for local dev

---

## System Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                         FRONTEND (React 19)                      │
│                                                                  │
│  InputPage ──► ProcessingPage ──► EditorPage                     │
│     │              │                   │                          │
│  useJob       useStream (SSE)     useEditor                      │
│     │              │                   │                          │
│  POST /generate   EventSource      GET/POST /slides,             │
│  GET /status      /stream/{id}     /regenerate, /restyle         │
└────────┬───────────┬───────────────────┬─────────────────────────┘
         │           │                   │
         ▼           ▼                   ▼
┌──────────────────────────────────────────────────────────────────┐
│                      BACKEND (FastAPI 2.0)                       │
│                                                                  │
│  ┌─────────┐   ┌──────────────┐   ┌─────────────────────────┐   │
│  │ API     │──►│ Job Store    │──►│ SSE Stream Endpoint     │   │
│  │ Layer   │   │ (Redis/mem)  │   │ GET /stream/{job_id}    │   │
│  └────┬────┘   └──────┬───────┘   └─────────────────────────┘   │
│       │               │                                          │
│       ▼               ▼                                          │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │              ORCHESTRATOR (run_pipeline)                  │   │
│  │                                                          │   │
│  │  Parse Prompt ──► Build State ──► Generate Story          │   │
│  │       │                                │                  │   │
│  │       ▼                                ▼                  │   │
│  │  Plan Slides ──► Multi-Stage Content ──► Evaluator        │   │
│  │                                             │             │   │
│  │                                             ▼             │   │
│  │  Deck Consistency ──► Visual Queries ──► Speaker Notes    │   │
│  │                                             │             │   │
│  │                                             ▼             │   │
│  │  Intelligence Report ──► Design + Transform ──► Template     │   │
│  │                                             │             │   │
│  │                                             ▼             │   │
│  │                    Rendering Engine ──► Export ──► PPTX    │   │
│  └──────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────┘
```

---

## Real-time Engine

Narrato uses an **event-driven architecture** for real-time communication:

```
Orchestrator                    Job Store                 SSE Endpoint              Frontend
    │                              │                          │                        │
    │──emit(STAGE_UPDATE)─────────►│                          │                        │
    │                              │──append_event()─────────►│                        │
    │                              │                          │──data: {event}────────►│
    │                              │                          │                        │──update UI
    │──emit(SLIDE_RENDERED)───────►│                          │                        │
    │  (includes HTML content)     │──append_event()─────────►│                        │
    │                              │                          │──data: {html}─────────►│
    │                              │                          │                        │──render iframe
    │──emit(JOB_COMPLETED)────────►│                          │                        │
    │                              │──append_event()─────────►│                        │
    │                              │                          │──data: {done}─────────►│
    │                              │                          │                        │──navigate to editor
```

**Event types**: `STAGE_UPDATE`, `SLIDE_GENERATED`, `SLIDE_DESIGNED`, `SLIDE_RENDERED`, `JOB_COMPLETED`, `JOB_FAILED`

Each event carries: `job_id`, `type`, `stage`, `progress` (0–100), `label`, optional `slide_id`, `total_slides`, `data`.

---

## Pipeline Overview

### Default Mode (narrative-driven)

```
User Prompt
    │
    ▼
┌─ Parse Prompt (LLM) ──► Extract topic, type, tone, audience, slide count
│
├─ Parse Schema (LLM) ──► Detect strict schema if present
│
├─ Build State ──► PresentationState (Pydantic model, 5–30 slides)
│
├─ Complete State (LLM) ──► Fill gaps in state
│
├─ Generate Story (LLM) ──► Narrative arc: hook, sections_flow, call_to_action
│
├─ Plan Slides ──► Weighted section allocation + slide type assignment
│
├─ Multi-Stage Content (LLM × N)
│   ├─ Phase 1: Content generation (3–4 bullets per slide)
│   ├─ Phase 2: Self-validation (repetition, generic, depth)
│   ├─ Phase 3: Critic loop (investor mode, max 3 attempts)
│   └─ Phase 4: Intent enforcement
│
├─ Slide Evaluator (LLM × N)
│   ├─ Deterministic checks (14 banned phrases, min 6 words/bullet)
│   ├─ LLM scoring (specificity, mechanism, uniqueness, clarity — min 4.0/5)
│   ├─ Strict critic (no-mercy investor mode)
│   └─ Targeted regeneration (max 3 attempts with specific fix instructions)
│
├─ Deck Consistency Optimizer (LLM)
│   ├─ Weak slide detection (score gap ≥ 1.0)
│   ├─ Terminology drift detection
│   ├─ Generic phrase scan
│   ├─ Bullet structure consistency
│   └─ Targeted rewrite
│
├─ Visual Queries (LLM) ──► Optional stock image search queries per slide
│
├─ Speaker Notes (LLM) ──► Presenter notes per slide
│
├─ Intelligence Report (LLM) ──► Pipeline behavior evaluation
│
├─ Design Engine ──► Layout + theme + components + presentation spec per slide
│   Layouts: hero_center, grid_cards, split_left_text_right_visual,
│            step_flow, stats_blocks, timeline_flow
│   Each slide gets a `presentation` dict: rhythm + layout variants so
│   adjacent slides differ in structure (not copy-paste templates).
│
├─ Content Visual Transform ──► Stat splitting, title lines, kickers,
│   split lead/support, dedupe — feeds the template with primary/secondary/tertiary tiers
│
├─ Template Engine ──► Full-screen HTML + embedded `slides.css` at 1920×1080
│   (no Tailwind CDN on slides; deterministic export/editor parity)
│
├─ Rendering Engine ──► Playwright PNG/PDF capture
│
├─ Export Engine ──► HTML files + image-based PPT
│
└─ PPT Generation ──► python-pptx .pptx file
```

### Strict Mode (schema-driven)

Activated when the prompt contains structured schema (e.g., "5 examples of X with fields A, B, C"). Uses `parse_user_schema` → `plan_slides_strict` → `generate_strict_content` → `validate_content`, then joins the shared tail pipeline.

---

## Tech Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| Frontend | React 19, React Router 7, Tailwind CSS 4, Vite 8 | SPA with SSE streaming |
| Backend | FastAPI, Python 3.11+, Pydantic, Uvicorn, uv | API + pipeline orchestration |
| AI | OpenAI (GPT-4o-mini default), Anthropic Claude | Content generation + evaluation |
| Rendering | Embedded `slides.css`, Playwright (optional) | HTML slides at 1920×1080, PNG/PDF |
| Queue | Celery + Redis (optional) | Production async job processing |
| Storage | Redis (jobs/events), in-memory fallback | Job state + event log |
| Images | Unsplash, Pexels | Stock image sourcing |
| Export | python-pptx, HTML, PNG, PDF | Multi-format output |

---

## What Makes This Different

| Aspect | Typical AI Slide Tools | Narrato |
|--------|----------------------|---------|
| Content quality | Single-pass LLM output | Multi-stage: generate → validate → critic → improve |
| Narrative | None — slides are isolated | Story arc drives all slide planning |
| Quality gates | None | Deterministic checks + LLM scoring + investor-mode critic |
| Consistency | Per-slide only | Full-deck consistency optimizer (tone, terminology, depth) |
| Feedback | Spinner → done | Real-time SSE: stage labels, progress %, live slide rendering |
| Post-generation | Download only | Interactive editor with AI regeneration, theme switching, inline editing |
| Slide visuals | One layout repeated | Varied layouts + typography scale + focal rules per slide type |
| Architecture | Monolithic | Event-driven pipeline with decoupled stages |

---

## Demo Flow

1. **Enter prompt** — "12-slide pitch deck for AI startup" on InputPage
2. **Generation starts** — POST /generate returns job_id, navigates to ProcessingPage
3. **Real-time updates** — SSE stream shows: "Understanding your prompt…" → "Building narrative arc…" → "Generating slide content…" → "Designing and rendering slides…"
4. **Progressive preview** — slides appear in a grid as they are rendered (iframe with HTML content)
5. **Completion** — auto-navigates to EditorPage
6. **Interactive editing** — slide panel (left), canvas (center), control panel (right)
7. **AI assist** — click any slide → AI Assistant panel → "Improve this slide" / custom instruction
8. **Theme switching** — Dark / Light / Gradient with 4 density modes
9. **Export** — PowerPoint, PDF, or PNG via Export modal

---

## Folder Structure

```
narrato/
├── main.py                      # Entry point (starts uvicorn)
├── pyproject.toml               # Python project metadata + uv dependencies
├── uv.lock                      # uv lockfile
├── .env.example                 # Environment variable template
│
├── backend/
│   ├── main.py                  # FastAPI app + all endpoints
│   ├── orchestrator.py          # Pipeline controller + event emission
│   ├── worker.py                # Celery worker for async jobs
│   ├── config.py                # Settings (pydantic-settings)
│   │
│   ├── models/
│   │   └── presentation_state.py  # PresentationState (Pydantic)
│   │
│   ├── pipeline/                # All pipeline stages
│   │   ├── prompt_understanding.py
│   │   ├── schema_parser.py
│   │   ├── state_builder.py / state_completion.py
│   │   ├── story_generator.py
│   │   ├── slide_planner.py / strict_slide_planner.py
│   │   ├── slide_type_assigner.py
│   │   ├── multi_stage_content.py / strict_content_structurer.py
│   │   ├── content_validator.py
│   │   ├── slide_evaluator.py
│   │   ├── deck_consistency_optimizer.py
│   │   ├── visual_mapper.py
│   │   ├── speaker_notes_generator.py
│   │   ├── intelligence_report.py
│   │   ├── content_visual_transform.py  # Stat/title/split transforms + presentation spec
│   │   ├── visual_design_engine.py      # Stage 1: Layout + theme + enrichment
│   │   ├── visual_template_engine.py    # Stage 2: HTML + embedded slides.css
│   │   ├── visual_rendering_engine.py   # Stage 3: PNG/PDF
│   │   ├── visual_export_engine.py      # Stage 4: File output
│   │   ├── visual_rendering_pipeline.py # Stages 1–4 orchestrator
│   │   ├── slide_validator.py           # Content + rendered HTML gates
│   │   ├── static/
│   │   │   └── slides.css               # Slide typography, layouts, themes
│   │   └── slide_utils.py               # Shared utilities
│   │
│   ├── services/
│   │   ├── event_system.py      # PipelineEvent + EventType
│   │   ├── job_store.py         # Redis/in-memory job + event store
│   │   ├── llm_client.py        # OpenAI/Anthropic with retry
│   │   └── image_service.py     # Unsplash/Pexels image fetching
│   │
│   ├── ppt/                     # python-pptx generation
│   │   ├── generator.py
│   │   ├── components.py
│   │   ├── design_system.py
│   │   ├── layouts/
│   │   └── themes/
│   │
│   └── tests/                   # pytest test suite
│
└── frontend/
    ├── index.html
    ├── package.json
    ├── vite.config.js           # Dev proxy + Tailwind plugin
    │
    └── src/
        ├── main.jsx             # React entry (BrowserRouter)
        ├── App.jsx              # Routes + layout
        ├── index.css            # Tailwind v4 theme tokens
        │
        ├── api/narrato.js       # All API calls (axios)
        ├── hooks/
        │   ├── useJob.js        # Job lifecycle state machine
        │   ├── useStream.js     # SSE subscription hook
        │   └── useEditor.js     # Editor state + operations
        │
        ├── pages/
        │   ├── InputPage.jsx
        │   ├── ProcessingPage.jsx
        │   ├── ResultPage.jsx
        │   └── EditorPage.jsx
        │
        └── components/
            ├── Navbar.jsx, Footer.jsx
            ├── SuggestionChips.jsx, OptionsPanel.jsx
            ├── ProgressPanel.jsx, LivePreview.jsx, ErrorBlock.jsx
            └── editor/
                ├── SlidePanel.jsx, SlideCanvas.jsx
                ├── ControlPanel.jsx, AIAssistant.jsx
                ├── EditModal.jsx, ExportModal.jsx
                └── EditorNavbar.jsx
```

---

## Setup

### Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) (Python package manager)
- Node.js ≥ 20
- Redis (optional — falls back to in-memory)

### Quick Start

```bash
# 1. Clone and configure
cp .env.example .env
# Edit .env: set OPENAI_API_KEY (required)

# 2. Install Python dependencies (from project root)
uv sync

# 3. Start backend
cd backend
uv run uvicorn main:app --port 8000 --reload

# 4. Frontend (separate terminal)
cd frontend
npm install
npm run dev
# → http://localhost:5173
```

### With Celery (production async)

```bash
# Terminal 1: Redis
redis-server

# Terminal 2: Celery worker
cd backend && uv run celery -A worker.celery_app worker --loglevel=info

# Terminal 3: API server
cd backend && uv run uvicorn main:app --port 8000

# Terminal 4: Frontend
cd frontend && npm run dev
```

---

## Production

- **Frontend**: `npm run build` → static files in `dist/` → serve via nginx/CDN
- **Backend**: Uvicorn behind nginx reverse proxy, Celery workers for async pipeline execution
- **Scaling**: Celery workers scale horizontally; Redis handles job state + event streaming; stateless API servers behind load balancer
- **File output**: `./outputs/` directory with job-specific subdirectories for HTML slides, previews, and PPTX files

---

## Slide design system

Slides are generated as standalone HTML documents with **embedded** [`backend/pipeline/static/slides.css`](backend/pipeline/static/slides.css). The pipeline aims for premium-deck behavior: one clear focal element per slide (hero title, mega stat, or dominant card), secondary and tertiary tiers, and **layout variation** across the deck so outputs do not read as the same template repeated.

- **`content_visual_transform.py`** — Parses and splits copy (e.g. leading percentages and multipliers like `2.3x`, `Actor` / `Action` kickers, split body lead vs support) before templating.
- **`visual_design_engine.py`** — Maps content to layout/theme/components and attaches a per-slide `presentation` spec (rhythm + variants). **Pitch-style patterns** include: slide 1 **cover** hero; **problem** grids with a pulled-out mega stat plus intro body and three pillars; **market** slides with three dollar-denominated stats as a **TAM/SAM/SOM funnel**; optional **deck index** (`01`, `02`, …) in the corner.
- **`visual_template_engine.py`** — Emits semantic markup (`data-rhythm`, bento grids, stats spotlight/funnel, editorial/cover hero, etc.) consumed by the CSS.

Put **eyebrow + tagline** on the title slide by using a newline in `subtitle` (first line → kicker, rest → tagline). Set **`footer_note`** / **`deck_footer`** / **`confidential_note`** for a confidential line under the cover. For **problem** slides, supply **`body`** (narrative paragraph) and either structured **`stat`** + **`stat_label`** or a first bullet like `68% of students fall behind…` to drive the mega-stat row.

Editor and export use the same HTML for parity. There is **no Tailwind CDN** inside slide documents.

---

## Contributing

See [backend/README.md](backend/README.md) for deep technical architecture. See [frontend/README.md](frontend/README.md) for UI architecture.

Run tests:
```bash
cd backend && uv run python -m pytest tests/ -v --ignore=tests/test_api.py
```

The pipeline is modular — each stage in `backend/pipeline/` is an independent function that takes and returns `PresentationState`. Add new stages by inserting them in `orchestrator.py`.
