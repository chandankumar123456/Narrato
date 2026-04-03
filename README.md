# Narrato — Complete System Architecture

> **A dynamic, state-driven, storytelling-first, design-aware AI presentation engine.**
> Converts natural language prompts into professionally structured `.pptx` files.

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Tech Stack](#2-tech-stack)
3. [Project Folder Structure](#3-project-folder-structure)
4. [Core Architectural Principle](#4-core-architectural-principle)
5. [Full Pipeline (End-to-End)](#5-full-pipeline-end-to-end)
6. [Prompt Handling Layer](#6-prompt-handling-layer)
7. [State Layer (Pydantic Model)](#7-state-layer-pydantic-model)
8. [Story Generation Layer](#8-story-generation-layer)
9. [Slide Planning Layer](#9-slide-planning-layer)
10. [Slide Type System](#10-slide-type-system)
11. [Content Structuring Layer](#11-content-structuring-layer)
12. [Visual Mapping Layer](#12-visual-mapping-layer)
13. [Design Mapping Layer](#13-design-mapping-layer)
14. [PPT Generation Layer](#14-ppt-generation-layer)
15. [Orchestrator (Pipeline Controller)](#15-orchestrator-pipeline-controller)
16. [Backend Architecture](#16-backend-architecture)
17. [Frontend Architecture](#17-frontend-architecture)
18. [Dynamic Behavior Model](#18-dynamic-behavior-model)
19. [Theme System](#19-theme-system)
20. [Error Handling & Fallback Strategy](#20-error-handling--fallback-strategy)
21. [Environment & Configuration](#21-environment--configuration)
22. [API Request & Response Schema](#22-api-request--response-schema)
23. [Async Strategy & Job Queue](#23-async-strategy--job-queue)
24. [Design Principles](#24-design-principles)
25. [MVP Scope](#25-mvp-scope)
26. [Advanced Extensions (Post-MVP)](#26-advanced-extensions-post-mvp)
27. [Testing Strategy](#27-testing-strategy)
28. [Deployment Notes](#28-deployment-notes)
29. [Technical Documentation](#29-technical-documentation)

---

## 1. Project Overview

**Narrato** is an AI-powered presentation generation system that:

- Accepts a **natural language prompt** (vague or detailed)
- Understands **intent, audience, tone, and structure**
- Builds a **state object** that drives every downstream decision
- Generates a **narrative arc** before creating any slides
- Maps content to **typed slide layouts**
- Produces a downloadable **`.pptx` file** using `python-pptx`

### High-Level System Flow

```
User Prompt (natural language)
        ↓
   FastAPI Backend
        ↓
  Orchestrator (Pipeline Controller)
        ↓
┌────────────────────────────────────┐
│         Core Pipeline              │
│                                    │
│  1.  Prompt Understanding          │
│  2.  Constraint Extraction         │
│  3.  State Builder (Pydantic)      │
│  4.  State Completion (LLM)        │
│  5.  Story Generation              │
│  6.  Slide Planning                │
│  7.  Slide Type Assignment         │
│  8.  Content Structuring           │
│  9.  Visual Mapping                │
│  10. Design Mapping                │
│  11. PPT Generation (python-pptx)  │
└────────────────────────────────────┘
        ↓
  .pptx File → Download Response
```

---

## 2. Tech Stack

| Layer | Technology | Purpose |
|---|---|---|
| **Frontend** | React (Vite) | User interface, prompt input, download trigger |
| **Backend** | FastAPI (Python 3.11+) | API server, pipeline orchestration |
| **LLM** | OpenAI GPT-4o / Claude 3.5 Sonnet (configurable) | Story generation, content structuring, state completion |
| **PPT Generation** | `python-pptx` | Slide creation, layout, text, image insertion |
| **Image Sourcing** | Unsplash API / Pexels API (configurable) | Fetching relevant slide images |
| **State Modeling** | Pydantic v2 | Typed, validated presentation state |
| **Job Queue** | Celery + Redis (production) / `asyncio` (MVP) | Async PPT generation |
| **Storage** | Local filesystem (MVP) / AWS S3 (production) | Storing generated `.pptx` files |
| **Environment** | `python-dotenv` | Managing API keys and config |

---

## 3. Project Folder Structure

```
narrato/
├── backend/
│   ├── main.py                  # FastAPI app entry point
│   ├── orchestrator.py          # Pipeline controller
│   ├── config.py                # Environment config loader
│   │
│   ├── pipeline/
│   │   ├── prompt_understanding.py
│   │   ├── constraint_extraction.py
│   │   ├── state_builder.py
│   │   ├── state_completion.py
│   │   ├── story_generator.py
│   │   ├── slide_planner.py
│   │   ├── slide_type_assigner.py
│   │   ├── content_structurer.py
│   │   ├── visual_mapper.py
│   │   └── design_mapper.py
│   │
│   ├── ppt/
│   │   ├── generator.py         # Main PPT generation entry point
│   │   ├── layouts/             # One file per slide type
│   │   │   ├── title_slide.py
│   │   │   ├── section_header.py
│   │   │   ├── problem_slide.py
│   │   │   ├── stats_slide.py
│   │   │   ├── feature_slide.py
│   │   │   ├── comparison_slide.py
│   │   │   ├── timeline_slide.py
│   │   │   ├── example_slide.py
│   │   │   └── conclusion_slide.py
│   │   └── themes/              # Color palettes and font configs
│   │       ├── modern.py
│   │       ├── corporate.py
│   │       └── minimal.py
│   │
│   ├── models/
│   │   ├── presentation_state.py
│   │   ├── story.py
│   │   └── slide_plan.py
│   │
│   ├── services/
│   │   ├── llm_client.py        # Unified LLM wrapper (OpenAI / Anthropic)
│   │   └── image_service.py     # Image fetching (Unsplash / Pexels)
│   │
│   └── outputs/                 # Generated .pptx files (temp storage)
│
├── frontend/
│   ├── src/
│   │   ├── App.jsx
│   │   ├── components/
│   │   │   ├── PromptInput.jsx
│   │   │   ├── OptionsPanel.jsx
│   │   │   ├── GenerateButton.jsx
│   │   │   ├── Loader.jsx
│   │   │   └── DownloadButton.jsx
│   │   └── api/
│   │       └── narrato.js       # Axios API calls
│   └── package.json
│
├── .env.example
├── requirements.txt
├── README.md
└── docker-compose.yml           # (production)
```

---

## 4. Core Architectural Principle

### State-Driven Execution

All pipeline logic operates on a single structured object — the `PresentationState`. No module reads the raw user prompt after the initial parsing step.

```
Final Output = f(PresentationState)
```

This guarantees:
- **Predictability** — same state always produces same structure
- **Testability** — each module can be tested independently with a mock state
- **Debuggability** — the state can be logged/inspected at any pipeline step

---

## 5. Full Pipeline (End-to-End)

```
Prompt
  │
  ▼
[1] Prompt Understanding
  │  → Extract signals: topic, tone, slide_count, sections, audience
  │
  ▼
[2] Constraint Extraction
  │  → Apply priority: user_input > LLM_inference > default
  │
  ▼
[3] State Builder
  │  → Build PresentationState (Pydantic model) from extracted signals
  │
  ▼
[4] State Completion (LLM)
  │  → Fill missing fields via LLM inference
  │
  ▼
[5] Story Generation (LLM)
  │  → Convert topic → narrative arc with sections_flow
  │
  ▼
[6] Slide Planning
  │  → Convert story → slide distribution (SlidePlan)
  │
  ▼
[7] Slide Type Assignment
  │  → Map each slide to a SlideType (e.g. stats_slide, feature_slide)
  │
  ▼
[8] Content Structuring (LLM)
  │  → Generate structured content per slide (NOT paragraphs)
  │
  ▼
[9] Visual Mapping
  │  → Generate image search queries per slide
  │  → Fetch images from Unsplash / Pexels
  │
  ▼
[10] Design Mapping
  │  → Map SlideType → Layout Template → Content Injection
  │
  ▼
[11] PPT Generation (python-pptx)
  │  → Render slides, position elements, insert images
  │
  ▼
.pptx File → API Response → User Download
```

---

## 6. Prompt Handling Layer

### 6.1 Prompt Understanding

Parses the raw natural language input and extracts intent signals.

**Input:** Raw user prompt string

**Output signals extracted:**

| Signal | Description | Example |
|---|---|---|
| `topic` | Main subject of the presentation | "Generative AI in Healthcare" |
| `slide_count` | Number of slides requested | `12` |
| `sections` | Named sections if specified | `["Intro", "Use Cases", "Future"]` |
| `tone` | Desired tone | `"professional"`, `"casual"`, `"inspiring"` |
| `presentation_type` | Deck purpose | `"pitch"`, `"educational"`, `"report"` |
| `audience` | Target audience | `"investors"`, `"students"`, `"executives"` |
| `examples_count` | How many examples to include | `3` |
| `image_preference` | Whether images are desired | `true` / `false` |
| `language` | Output language | `"en"`, `"hi"`, `"fr"` |

---

### 6.2 Constraint Extraction Logic

Applies a strict priority rule for every field:

```
Final Field Value = user_input  OR  LLM_inference  OR  system_default
```

**Defaults table:**

| Field | Default |
|---|---|
| `slide_count` | `10` |
| `tone` | `"professional"` |
| `visual_style` | `"modern"` |
| `image_preference` | `true` |
| `language` | `"en"` |
| `examples_count` | `2` |

---

## 7. State Layer (Pydantic Model)

### 7.1 PresentationState

The central data object. Every pipeline module reads from and/or writes to this object.

```python
from pydantic import BaseModel
from typing import Optional

class PresentationState(BaseModel):
    # Core identity
    topic: str
    presentation_type: str                  # "pitch" | "educational" | "report" | "general"
    language: str = "en"

    # Slide structure
    slide_count: int = 10
    min_slides: int = 5
    max_slides: int = 30
    sections: Optional[list[str]] = None

    # Tone & audience
    tone: str = "professional"              # "professional" | "casual" | "inspiring" | "academic"
    audience: Optional[str] = None

    # Content settings
    examples_count: Optional[int] = None
    include_stats: bool = True

    # Visuals
    image_preference: bool = True
    visual_style: str = "modern"            # "modern" | "corporate" | "minimal"
    theme: str = "modern"

    # Runtime (filled during pipeline)
    story: Optional[dict] = None
    slide_plan: Optional[list[dict]] = None
    structured_slides: Optional[list[dict]] = None
    image_queries: Optional[list[str]] = None
    output_path: Optional[str] = None
```

> **Note:** `slide_count` is clamped between `min_slides` (5) and `max_slides` (30) at state completion time. Inputs outside this range are adjusted with a warning.

---

### 7.2 State Completion (LLM)

After the state is built from user input, an LLM call fills any `None` or missing fields:

- Infer `sections` from topic if not provided
- Infer `tone` from `presentation_type` and `audience`
- Infer `examples_count` from `presentation_type`
- Infer `include_stats` based on topic and type

**LLM is called once here with a structured JSON response format.**

---

## 8. Story Generation Layer

### Purpose

This is the most critical layer. It converts a dry topic into a **narrative arc** before any slides are created. Slides without a story are just bullet points — slides with a story are a presentation.

### LLM Prompt Strategy

The LLM is asked to produce a structured narrative in JSON format:

```json
{
  "narrative_type": "problem-solution",
  "key_message": "AI is transforming healthcare diagnostics",
  "hook": "What if a doctor never missed a diagnosis again?",
  "sections_flow": [
    {
      "section": "intro",
      "purpose": "Set the stage and hook the audience",
      "emotion": "curiosity"
    },
    {
      "section": "problem",
      "purpose": "Highlight the current diagnostic gap",
      "emotion": "urgency"
    },
    {
      "section": "solution",
      "purpose": "Introduce AI-powered diagnostics",
      "emotion": "hope"
    },
    {
      "section": "benefits",
      "purpose": "Show real-world impact and data",
      "emotion": "confidence"
    },
    {
      "section": "conclusion",
      "purpose": "Call to action — adopt, invest, or explore",
      "emotion": "inspiration"
    }
  ],
  "call_to_action": "Partner with us to pilot this in your hospital"
}
```

### Narrative Types

| Narrative Type | Best For |
|---|---|
| `problem-solution` | Pitch decks, proposals |
| `educational-journey` | Training, explainers |
| `data-driven` | Reports, business reviews |
| `inspiration-arc` | Keynotes, motivational |
| `comparison` | Product comparisons, competitive analysis |

---

## 9. Slide Planning Layer

### Purpose

Converts the story's `sections_flow` into a concrete slide distribution.

### Output: `SlidePlan`

```json
{
  "total_slides": 12,
  "slides": [
    { "slide_id": 1, "section": "intro",      "purpose": "Title slide" },
    { "slide_id": 2, "section": "intro",      "purpose": "Agenda overview" },
    { "slide_id": 3, "section": "problem",    "purpose": "Problem statement" },
    { "slide_id": 4, "section": "problem",    "purpose": "Problem stats" },
    { "slide_id": 5, "section": "solution",   "purpose": "Solution intro" },
    { "slide_id": 6, "section": "solution",   "purpose": "Feature breakdown" },
    { "slide_id": 7, "section": "benefits",   "purpose": "Key benefit 1" },
    { "slide_id": 8, "section": "benefits",   "purpose": "Key benefit 2 + example" },
    { "slide_id": 9, "section": "benefits",   "purpose": "Case study / example" },
    { "slide_id": 10, "section": "conclusion", "purpose": "Summary" },
    { "slide_id": 11, "section": "conclusion", "purpose": "Call to action" },
    { "slide_id": 12, "section": "conclusion", "purpose": "Thank you / contact" }
  ]
}
```

### Slide Distribution Rules

- `intro` → 1–2 slides
- `problem` → 1–3 slides (more if `include_stats: true`)
- `solution` → 2–4 slides
- `benefits` → 2–5 slides (scales with `examples_count`)
- `conclusion` → 1–2 slides
- Section headers are inserted between major sections

---

## 10. Slide Type System

### Available Slide Types

| Slide Type | Description |
|---|---|
| `title_slide` | Opening slide with title + subtitle + presenter name |
| `section_header` | Divider slide between major sections |
| `agenda_slide` | List of topics / table of contents |
| `problem_slide` | 3-card layout showing pain points |
| `stats_slide` | Large-number hero stat with description |
| `feature_slide` | Grid layout of 3–4 features with icons |
| `comparison_slide` | Side-by-side comparison (Before/After, A vs B) |
| `timeline_slide` | Horizontal or vertical timeline |
| `example_slide` | Case study or real-world example |
| `quote_slide` | Full-bleed quote with attribution |
| `image_slide` | Full-bleed image with overlay text |
| `conclusion_slide` | Summary bullets + key takeaway |
| `cta_slide` | Call to action + contact / next steps |
| `thank_you_slide` | Closing slide |

---

### Each Slide Type Defines

```python
class SlideTypeDefinition:
    type_name: str
    layout_structure: str         # "3-card" | "grid" | "large-number" | "two-column" | ...
    content_schema: dict          # Expected content fields
    visual_requirement: str       # "optional" | "recommended" | "required" | "none"
    min_content_items: int
    max_content_items: int
```

---

## 11. Content Structuring Layer

### Goal

Generate **structured data** for each slide — never raw paragraphs. Every field maps directly to a visual element in the layout.

### Content Schemas by Slide Type

**`feature_slide`**
```json
{
  "title": "Why Narrato Stands Out",
  "features": [
    { "icon": "🎯", "label": "Story-First", "description": "Every deck starts with a narrative" },
    { "icon": "⚡", "label": "Fast", "description": "Generate in under 30 seconds" },
    { "icon": "🎨", "label": "Designed", "description": "Professional layouts out of the box" }
  ]
}
```

**`stats_slide`**
```json
{
  "title": "The Diagnostic Gap",
  "stat": "40%",
  "stat_label": "of diagnoses delayed",
  "description": "Delayed diagnoses cost the US healthcare system $750B annually",
  "source": "WHO Report, 2023"
}
```

**`comparison_slide`**
```json
{
  "title": "Before vs After AI",
  "left_label": "Traditional Diagnosis",
  "left_points": ["Manual review", "3–5 days turnaround", "High error rate"],
  "right_label": "AI-Assisted Diagnosis",
  "right_points": ["Automated scan analysis", "Under 2 hours", "94% accuracy"]
}
```

**`timeline_slide`**
```json
{
  "title": "Milestones",
  "events": [
    { "year": "2020", "label": "Research begins" },
    { "year": "2022", "label": "Pilot launched" },
    { "year": "2023", "label": "FDA clearance" },
    { "year": "2024", "label": "Enterprise rollout" }
  ]
}
```

> **Rule:** The LLM is given the `content_schema` as a JSON template and asked to fill it. It must not deviate from the schema structure.

---

## 12. Visual Mapping Layer

### Purpose

Generate targeted image search queries for each slide and fetch relevant images.

### Query Generation

For each slide, the LLM produces an `image_query`:

| Slide | Example Query |
|---|---|
| Problem slide (healthcare) | `"healthcare diagnostics failure doctor stress"` |
| Solution slide (AI) | `"AI medical imaging technology abstract"` |
| Stats slide | `"global health data visualization chart"` |
| Feature slide | `"modern technology product features grid"` |
| Conclusion slide | `"partnership collaboration future handshake"` |

### Image Fetching

```python
# Image sourcing priority
1. Unsplash API (primary — free tier: 50 req/hour)
2. Pexels API (fallback)
3. No image (if both fail — slide renders without image)
```

Images are:
- Fetched at medium resolution (`1200px` wide)
- Cached locally during the session
- Not persisted to disk after the download response is sent

---

## 13. Design Mapping Layer

### Core Logic

```
SlideType → Layout Template → Content Injection → Rendered Slide
```

### Layout → Slide Type Mapping

| Slide Type | Layout | Description |
|---|---|---|
| `title_slide` | Centered full-bleed | Title, subtitle, optional background image |
| `problem_slide` | 3-card horizontal | Three problem cards with icon + text |
| `stats_slide` | Large-number hero | Giant stat centered, description below |
| `feature_slide` | 2×2 or 3×1 grid | Feature cards with icon, label, description |
| `comparison_slide` | Two-column split | Left vs right with colored header |
| `timeline_slide` | Horizontal flow | Dots connected by line, left-to-right |
| `section_header` | Minimal centered | Section name + thin accent line |
| `conclusion_slide` | Bullet list + callout box | Summary + highlighted takeaway |
| `cta_slide` | Bold text + action block | CTA text + button-style element |

### Important Rules

- Layouts are **predefined** — no dynamic layout generation
- All text is **injected**, not generated at render time
- Color and font come from the **theme config**, not hardcoded values
- Image placement is **fixed per layout** (e.g., right 40% of slide for feature slides)

---

## 14. PPT Generation Layer

### Tool: `python-pptx`

### Responsibilities

- Create the `.pptx` file and add slides in order
- Position all elements using EMU (English Metric Units) coordinates
- Apply theme colors and fonts
- Insert text boxes with proper sizing
- Insert images with correct positioning and cropping
- Apply background fills

### Coordinate System

All positions use EMU units:

```
914400 EMU = 1 inch
Standard slide size: 10 inches × 7.5 inches
= 9144000 EMU × 6858000 EMU
```

### Layout Rendering Strategy

Each slide type has a dedicated layout function:

```python
def render_feature_slide(slide, content: dict, theme: ThemeConfig, image_path: str | None):
    place_background(slide, theme)
    place_title(slide, content["title"], theme)
    place_feature_grid(slide, content["features"], theme)
    if image_path:
        place_side_image(slide, image_path)
```

### Output

- File saved to `backend/outputs/{job_id}.pptx`
- Returned as a `FileResponse` via FastAPI
- Deleted after download (configurable retention period)

---

## 15. Orchestrator (Pipeline Controller)

The orchestrator calls each pipeline step in sequence, passing the `PresentationState` through.

```python
async def run_pipeline(prompt: str) -> str:
    # Returns path to generated .pptx

    signals     = await parse_prompt(prompt)
    constraints = extract_constraints(signals)
    state       = build_state(constraints)
    state       = await complete_state(state)          # LLM call 1
    state       = await generate_story(state)          # LLM call 2
    state       = plan_slides(state)
    state       = assign_slide_types(state)
    state       = await generate_structured_content(state)  # LLM call 3
    state       = await generate_visual_queries(state)      # LLM call 4 (optional)
    images      = await fetch_images(state)
    state       = map_to_templates(state)
    output_path = generate_ppt(state, images)

    return output_path
```

### LLM Call Summary

| Step | LLM Call | Purpose |
|---|---|---|
| State Completion | Call 1 | Fill missing state fields |
| Story Generation | Call 2 | Build narrative arc |
| Content Structuring | Call 3 | Generate structured slide content |
| Visual Mapping | Call 4 (optional) | Generate image search queries |

**Total LLM calls per presentation: 3–4**

---

## 16. Backend Architecture

### Framework: FastAPI (Python 3.11+)

### Endpoints

#### `POST /generate`

Starts the pipeline and returns a job ID (async) or the file directly (sync MVP).

**Request body:**
```json
{
  "prompt": "Create a 12-slide pitch deck for an AI diagnostics startup targeting hospital CTOs",
  "options": {
    "slide_count": 12,
    "visual_style": "modern",
    "tone": "professional",
    "image_preference": true
  }
}
```

**Response (async):**
```json
{
  "job_id": "a1b2c3d4",
  "status": "processing",
  "estimated_seconds": 25
}
```

**Response (sync MVP):** Returns `.pptx` file as binary download.

---

#### `GET /status/{job_id}`

Returns current generation status.

```json
{
  "job_id": "a1b2c3d4",
  "status": "completed",
  "download_url": "/download/a1b2c3d4"
}
```

Status values: `queued` | `processing` | `completed` | `failed`

---

#### `GET /download/{job_id}`

Returns the `.pptx` file as a `FileResponse`.

---

#### `GET /health`

Health check endpoint.

```json
{ "status": "ok", "version": "1.0.0" }
```

---

## 17. Frontend Architecture

### Tech: React (Vite) + Axios

### Components

| Component | Role |
|---|---|
| `PromptInput` | Textarea for natural language input |
| `OptionsPanel` | Optional controls: slide count, style, tone |
| `GenerateButton` | Triggers API call, disabled during loading |
| `Loader` | Progress indicator with estimated time |
| `DownloadButton` | Appears on completion, triggers file download |
| `ErrorBanner` | Shows user-friendly error messages |

### State Flow

```
User types prompt
  → PromptInput captures text
  → GenerateButton sends POST /generate
  → Loader shows (polls GET /status/{id} every 2s)
  → On completion: DownloadButton appears
  → User clicks download → GET /download/{id}
```

---

## 18. Dynamic Behavior Model

### Three Input Modes

| Mode | Description | System Behavior |
|---|---|---|
| **Vague Input** | `"make a presentation about climate change"` | System decides everything: sections, tone, slide count, layout |
| **Partial Input** | `"12-slide deck on climate change for investors"` | Hybrid: user sets slide_count and audience; system infers the rest |
| **Strict Input** | Detailed prompt with sections, style, count specified | System fully obeys user constraints; minimal inference |

### Priority Rule (Applied to Every Field)

```
Final Field Value = user_input  OR  LLM_inference  OR  system_default
```

---

## 19. Theme System

Themes control colors, fonts, and visual style across all slides.

### Available Themes

| Theme | Primary Color | Font | Style |
|---|---|---|---|
| `modern` | `#6C63FF` (purple) | Inter | Clean, minimal, contemporary |
| `corporate` | `#1A3C5E` (navy) | Calibri | Formal, trust-inspiring, structured |
| `minimal` | `#2D2D2D` (near-black) | Helvetica Neue | Ultra-clean, whitespace-heavy |

### ThemeConfig Structure

```python
class ThemeConfig(BaseModel):
    name: str
    primary_color: str         # Hex, used for headings and accents
    secondary_color: str       # Hex, used for subheadings and borders
    background_color: str      # Hex, slide background
    text_color: str            # Hex, body text
    font_heading: str          # Font name for titles
    font_body: str             # Font name for body text
    heading_size: int          # In points
    body_size: int             # In points
```

---

## 20. Error Handling & Fallback Strategy

### LLM Failures

| Failure | Fallback |
|---|---|
| State completion LLM fails | Use all system defaults |
| Story generation fails | Use generic 5-section template (intro → problem → solution → benefits → conclusion) |
| Content structuring fails for one slide | Use placeholder content ("Content could not be generated for this slide") |
| All LLM calls fail | Return 500 with user-facing message: "AI generation failed, please try again" |

### Image Failures

| Failure | Fallback |
|---|---|
| Unsplash API fails | Try Pexels API |
| Pexels API fails | Render slide without image |
| Image download times out (>5s) | Skip image, render without |

### PPT Generation Failures

| Failure | Action |
|---|---|
| `python-pptx` exception | Log full traceback, return 500 |
| Missing font | Fall back to system default font |
| Malformed content schema | Skip that slide, log warning |

### General Rules

- All pipeline steps are wrapped in `try/except`
- Errors are logged with `job_id` for traceability
- User always receives a friendly error message, never a raw traceback
- A failed job cleans up any partially generated files

---

## 21. Environment & Configuration

### `.env.example`

```env
# LLM Provider (choose one)
LLM_PROVIDER=openai           # "openai" | "anthropic"
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
LLM_MODEL=gpt-4o              # or "claude-3-5-sonnet-20241022"

# Image APIs
UNSPLASH_ACCESS_KEY=...
PEXELS_API_KEY=...
IMAGE_PROVIDER=unsplash       # "unsplash" | "pexels" | "none"

# Storage
OUTPUT_DIR=./outputs
FILE_RETENTION_SECONDS=3600   # Delete files after 1 hour

# Server
HOST=0.0.0.0
PORT=8000
DEBUG=false

# Redis (production async queue)
REDIS_URL=redis://localhost:6379/0
```

---

## 22. API Request & Response Schema

### Full Request Schema

```typescript
interface GenerateRequest {
  prompt: string;           // Required — natural language prompt
  options?: {
    slide_count?: number;   // 5–30
    visual_style?: "modern" | "corporate" | "minimal";
    tone?: "professional" | "casual" | "inspiring" | "academic";
    image_preference?: boolean;
    language?: string;      // ISO 639-1 code, e.g. "en", "hi"
  };
}
```

### Full Response Schema (async)

```typescript
interface GenerateResponse {
  job_id: string;
  status: "queued" | "processing" | "completed" | "failed";
  estimated_seconds: number;
  download_url?: string;    // Present only when status === "completed"
  error?: string;           // Present only when status === "failed"
}
```

---

## 23. Async Strategy & Job Queue

### Why Async?

PPT generation takes 15–45 seconds (LLM calls + image fetching + `python-pptx` rendering). Blocking the HTTP request for this duration is not acceptable.

### MVP (Development)

```
POST /generate → FastAPI background task (asyncio)
              → Polls GET /status/{id} from frontend every 2s
              → Returns file on completion
```

### Production

```
POST /generate → Enqueue job in Redis via Celery
              → Worker picks up job, runs pipeline
              → Stores result path in Redis
              → Frontend polls GET /status/{id}
              → On completion, GET /download/{id} fetches file
```

---

## 24. Design Principles

| Principle | Meaning |
|---|---|
| **Story First** | Slides always follow a narrative arc — never random content |
| **Structured Content** | LLM outputs JSON schemas, never raw paragraphs |
| **Design Consistency** | All slides share the same theme — fonts, colors, spacing |
| **Separation of Concerns** | Story ≠ Slides ≠ Content ≠ Design (each is a separate pipeline step) |
| **Deterministic Pipeline** | Same state always produces the same structure |
| **Fail Gracefully** | Every step has a fallback — partial output is better than no output |
| **User Intent Priority** | User-specified constraints always override AI inference |

---

## 25. MVP Scope

These features must work for the MVP to ship:

- [x] Prompt input (any natural language)
- [x] State creation from prompt
- [x] LLM-powered story generation
- [x] Slide planning and type assignment
- [x] Structured content generation
- [x] PPT generation with `python-pptx`
- [x] At least 3 working slide types: `title_slide`, `feature_slide`, `conclusion_slide`
- [x] At least 1 working theme: `modern`
- [x] Synchronous download (no job queue required for MVP)
- [x] Basic error handling (no crash on LLM failure)
- [x] Frontend: prompt → loader → download

---

## 26. Advanced Extensions (Post-MVP)

| Feature | Description |
|---|---|
| Multiple themes | `corporate`, `minimal`, `dark`, `vibrant` |
| Editable preview | In-browser slide preview before download |
| Slide regeneration | Regenerate individual slides without rebuilding the whole deck |
| Export to PDF | Convert `.pptx` to PDF on the server |
| AI image generation | Use DALL·E or Stable Diffusion instead of stock photos |
| Custom branding | Upload a logo, set brand colors |
| Language support | Generate decks in Hindi, French, Spanish, etc. |
| Template marketplace | User-selectable pre-built layouts |
| Collaboration | Share and co-edit decks |
| Slide notes | Auto-generate speaker notes per slide |

---

## 27. Testing Strategy

### Unit Tests

- `test_constraint_extraction.py` — test priority rule with various inputs
- `test_state_builder.py` — test Pydantic validation and defaults
- `test_slide_planner.py` — test slide count distribution logic
- `test_content_structurer.py` — test JSON schema compliance of LLM output

### Integration Tests

- `test_pipeline_vague_input.py` — full pipeline with minimal prompt
- `test_pipeline_strict_input.py` — full pipeline with fully specified prompt
- `test_ppt_generation.py` — verify `.pptx` file is valid and non-empty

### Mock Strategy

- LLM calls are mocked in unit tests using fixture JSON files
- Image fetching is mocked to return a local test image

### Manual QA Checklist

- [ ] Generated `.pptx` opens in PowerPoint / LibreOffice without errors
- [ ] Slide count matches requested count (±1)
- [ ] Fonts and colors match selected theme
- [ ] No empty slides
- [ ] Images are relevant and correctly placed
- [ ] Title slide always appears first
- [ ] Conclusion slide always appears last

---

## 28. Deployment Notes

### Development

```bash
# Backend
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000

# Frontend
cd frontend
npm install
npm run dev
```

### Production (Docker)

```yaml
# docker-compose.yml (simplified)
services:
  backend:
    build: ./backend
    ports: ["8000:8000"]
    env_file: .env

  frontend:
    build: ./frontend
    ports: ["3000:3000"]

  redis:
    image: redis:7-alpine

  worker:
    build: ./backend
    command: celery -A tasks worker --loglevel=info
    env_file: .env
```

### Recommended Hosting

| Component | Option |
|---|---|
| Backend | Railway, Render, AWS EC2 |
| Frontend | Vercel, Netlify |
| Redis | Upstash (serverless Redis) |
| File Storage | AWS S3 (replace local `outputs/` folder) |

---

*Last updated: Architecture v3 — Production-grade, fully implemented.*

---

## 29. Technical Documentation

> **Complete developer guide for setting up, running, and understanding the Narrato system.**
> This project uses **uv** as the Python package manager for the backend.

---

### 29.1 Project Structure (Production)

```
narrato/
├── backend/
│   ├── main.py                          # FastAPI app — API endpoints, CORS, job management
│   ├── orchestrator.py                  # Pipeline controller — runs all steps in sequence
│   ├── config.py                        # Pydantic Settings — env-based configuration
│   ├── worker.py                        # Celery worker — async job execution via Redis
│   │
│   ├── models/
│   │   └── presentation_state.py        # PresentationState — Pydantic state model
│   │
│   ├── pipeline/
│   │   ├── prompt_understanding.py      # Step 1: LLM extracts signals from prompt
│   │   ├── state_builder.py             # Step 2: Build PresentationState from signals
│   │   ├── state_completion.py          # Step 3: LLM fills missing state fields
│   │   ├── story_generator.py           # Step 4: LLM creates narrative arc
│   │   ├── slide_planner.py             # Step 5: Distribute slides across sections
│   │   ├── slide_type_assigner.py       # Step 6: Map each slide to a layout type
│   │   ├── content_structurer.py        # Step 7: LLM generates structured JSON per slide
│   │   ├── visual_mapper.py             # Step 8: LLM generates image queries + fetch
│   │   └── speaker_notes_generator.py   # Step 9: LLM generates speaker notes per slide
│   │
│   ├── ppt/
│   │   ├── generator.py                 # PPT engine — renders slides, injects notes
│   │   ├── layouts/                     # 14 slide layout renderers
│   │   │   ├── title_slide.py
│   │   │   ├── section_header.py
│   │   │   ├── agenda_slide.py
│   │   │   ├── problem_slide.py
│   │   │   ├── stats_slide.py
│   │   │   ├── feature_slide.py
│   │   │   ├── comparison_slide.py
│   │   │   ├── timeline_slide.py
│   │   │   ├── example_slide.py
│   │   │   ├── quote_slide.py
│   │   │   ├── image_slide.py
│   │   │   ├── conclusion_slide.py
│   │   │   ├── cta_slide.py
│   │   │   └── thank_you_slide.py
│   │   └── themes/
│   │       └── modern.py                # Theme configs: modern, corporate, minimal
│   │
│   ├── services/
│   │   ├── llm_client.py                # LLM wrapper — retry, rate limit, JSON parsing
│   │   ├── image_service.py             # Image fetching — Unsplash/Pexels with fallback
│   │   └── job_store.py                 # Redis-backed job store (in-memory fallback)
│   │
│   └── requirements.txt
│
├── frontend/
│   ├── src/
│   │   ├── App.jsx                      # Main UI — prompt, options, progress, preview
│   │   ├── main.jsx                     # React entry point
│   │   ├── index.css                    # Global styles
│   │   ├── App.css                      # Component styles
│   │   └── api/
│   │       └── narrato.js               # Axios API client
│   ├── package.json
│   └── vite.config.js
│
├── pyproject.toml                       # uv project config + dependencies
├── uv.lock                             # uv lock file
├── main.py                             # Root entry point (placeholder)
└── README.md
```

---

### 29.2 Prerequisites

| Tool | Version | Purpose |
|---|---|---|
| **Python** | 3.11+ | Backend runtime |
| **uv** | latest | Python package manager (replaces pip) |
| **Node.js** | 18+ | Frontend build tool |
| **Redis** | 7+ | Job queue broker + result store |
| **LibreOffice** | 7+ | Slide preview generation (headless) |
| **poppler-utils** | latest | Optional: PDF → PNG conversion for previews |

---

### 29.3 Setup & Installation

#### Backend (using uv)

```bash
# Install uv (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# From the project root
cd narrato/

# Install all Python dependencies via uv
uv sync

# Create .env file from template
cp .env.example .env
# Edit .env with your API keys (see section 29.4)
```

#### Frontend

```bash
cd frontend/
npm install
```

#### Redis (required for production, optional for dev)

```bash
# macOS
brew install redis && brew services start redis

# Ubuntu/Debian
sudo apt-get install redis-server
sudo systemctl start redis

# Docker
docker run -d --name redis -p 6379:6379 redis:7-alpine
```

#### LibreOffice (for preview generation)

```bash
# macOS
brew install --cask libreoffice

# Ubuntu/Debian
sudo apt-get install libreoffice poppler-utils

# Docker (included in production Dockerfile)
```

---

### 29.4 Environment Configuration

Create a `.env` file in the project root:

```env
# ──── LLM Provider ────
LLM_PROVIDER=openai                     # "openai" | "anthropic"
OPENAI_API_KEY=sk-...                   # Required if LLM_PROVIDER=openai
ANTHROPIC_API_KEY=sk-ant-...            # Required if LLM_PROVIDER=anthropic
LLM_MODEL=gpt-4o-mini                   # or "claude-3-5-sonnet-20241022"

# ──── Image APIs (optional) ────
IMAGE_PROVIDER=unsplash                  # "unsplash" | "pexels" | "none"
UNSPLASH_ACCESS_KEY=...                  # Get from unsplash.com/developers
PEXELS_API_KEY=...                       # Get from pexels.com/api

# ──── Storage ────
OUTPUT_DIR=./outputs                     # Directory for generated files
FILE_RETENTION_SECONDS=3600              # Auto-cleanup after 1 hour

# ──── Redis ────
REDIS_URL=redis://localhost:6379/0       # Redis connection string
```

---

### 29.5 Running the Application

#### Development Mode (no Redis/Celery required)

```bash
# Terminal 1: Backend
cd backend/
uv run uvicorn main:app --reload --port 8000

# Terminal 2: Frontend
cd frontend/
npm run dev
```

The backend will automatically fall back to in-memory job storage and `asyncio` background tasks when Redis/Celery are unavailable.

**Access the app at:** http://localhost:5173

#### Production Mode (Redis + Celery)

```bash
# Terminal 1: Redis
redis-server

# Terminal 2: Celery worker
cd backend/
uv run celery -A worker.celery_app worker --loglevel=info --concurrency=4

# Terminal 3: Backend API
cd backend/
uv run uvicorn main:app --host 0.0.0.0 --port 8000

# Terminal 4: Frontend (or build for production)
cd frontend/
npm run build
npm run preview
```

#### Docker Compose (Full Stack)

```yaml
# docker-compose.yml
services:
  backend:
    build: ./backend
    ports: ["8000:8000"]
    env_file: .env
    depends_on: [redis]
    command: uvicorn main:app --host 0.0.0.0 --port 8000

  worker:
    build: ./backend
    env_file: .env
    depends_on: [redis]
    command: celery -A worker.celery_app worker --loglevel=info --concurrency=4

  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]

  frontend:
    build: ./frontend
    ports: ["3000:3000"]
    depends_on: [backend]
```

---

### 29.6 API Reference

#### `POST /generate`

Start a new presentation generation job.

**Request:**
```json
{
  "prompt": "12-slide pitch deck for an AI diagnostics startup",
  "options": {
    "slide_count": 12,
    "tone": "professional",
    "visual_style": "modern",
    "image_preference": true
  }
}
```

**Response:**
```json
{
  "job_id": "a1b2c3d4e5f6",
  "status": "queued",
  "estimated_seconds": 30
}
```

#### `GET /status/{job_id}`

Poll for job status and progress.

**Response (processing):**
```json
{
  "job_id": "a1b2c3d4e5f6",
  "status": "processing",
  "progress": 40
}
```

**Response (completed):**
```json
{
  "job_id": "a1b2c3d4e5f6",
  "status": "completed",
  "progress": 100,
  "download_url": "/download/a1b2c3d4e5f6",
  "preview_urls": ["/previews/a1b2c3d4e5f6/slide-1.png", "..."]
}
```

**Response (failed):**
```json
{
  "job_id": "a1b2c3d4e5f6",
  "status": "failed",
  "error": "LLM call failed after 3 attempts"
}
```

#### `GET /download/{job_id}`

Download the generated `.pptx` file.

#### `POST /preview/{job_id}`

Trigger slide preview image generation (LibreOffice headless). Preview images are served from `/previews/{job_id}/`.

#### `GET /health`

Health check with dependency status.

```json
{
  "status": "ok",
  "version": "2.0.0",
  "redis": "connected",
  "celery": "connected"
}
```

---

### 29.7 Full Pipeline Architecture

```
User Input
    │
    ▼
[1] Prompt Understanding (LLM)
    │  → Extract: topic, tone, audience, slide_count, sections
    │
    ▼
[2] State Builder
    │  → Create PresentationState (Pydantic model)
    │
    ▼
[3] State Completion (LLM)
    │  → Fill missing fields via inference
    │
    ▼
[4] Story Generation (LLM)
    │  → Create narrative arc: hook, sections_flow, call_to_action
    │
    ▼
[5] Slide Planning
    │  → Weighted distribution across sections
    │
    ▼
[6] Slide Type Assignment
    │  → Map each slide to one of 14 layout types
    │
    ▼
[7] Content Structuring (LLM)
    │  → Generate JSON content per slide matching type schema
    │
    ▼
[8] Visual Mapping (LLM + API)
    │  → Generate image queries → fetch from Unsplash/Pexels
    │
    ▼
[9] Speaker Notes Generation (LLM)
    │  → Generate 3-5 sentence notes per slide
    │
    ▼
[10] PPT Generation (python-pptx)
    │  → Render all slides with themed layouts
    │  → Inject speaker notes into notes pages
    │
    ▼
.pptx File → Download / Preview
```

**Total LLM calls per presentation: 5-6**

| Step | LLM Call | Purpose |
|---|---|---|
| Prompt Understanding | Call 1 | Extract intent signals from prompt |
| State Completion | Call 2 | Fill missing state fields |
| Story Generation | Call 3 | Build narrative arc |
| Content Structuring | Call 4 (per slide) | Generate structured slide content |
| Visual Mapping | Call 5 | Generate image search queries |
| Speaker Notes | Call 6 | Generate speaker notes per slide |

---

### 29.8 Slide Layout System

All 14 implemented slide types:

| # | Slide Type | Layout | Content Schema |
|---|---|---|---|
| 1 | `title_slide` | Centered + accent bars | `{title, subtitle, presenter}` |
| 2 | `section_header` | Centered + thin accent line | `{section_title, tagline}` |
| 3 | `agenda_slide` | Numbered item list | `{title, items[]}` |
| 4 | `problem_slide` | 3-card horizontal | `{title, cards[{icon, label, description}]}` |
| 5 | `stats_slide` | Large hero stat | `{title, stat, stat_label, description, source}` |
| 6 | `feature_slide` | Feature grid | `{title, features[{icon, label, description}]}` |
| 7 | `comparison_slide` | Two-column split | `{title, left_label, left_points[], right_label, right_points[]}` |
| 8 | `timeline_slide` | Horizontal flow + dots | `{title, events[{year, label}]}` |
| 9 | `example_slide` | Case study layout | `{title, example_title, context, result, takeaway}` |
| 10 | `quote_slide` | Full-bleed quote | `{quote, attribution}` |
| 11 | `image_slide` | Full image + overlay | `{title, caption}` |
| 12 | `conclusion_slide` | Bullets + takeaway box | `{title, bullets[], key_takeaway}` |
| 13 | `cta_slide` | Bold CTA + contact | `{title, cta_text, contact}` |
| 14 | `thank_you_slide` | Closing slide | `{title, message, contact}` |

---

### 29.9 Job Processing System

#### Architecture

```
Frontend → POST /generate → FastAPI
                              │
                   ┌──────────┴──────────┐
                   │                     │
              [Celery available]   [No Celery]
                   │                     │
                   ▼                     ▼
            Redis Queue          asyncio BackgroundTask
                   │                     │
                   ▼                     │
            Celery Worker                │
                   │                     │
                   └──────────┬──────────┘
                              │
                        Run Pipeline
                              │
                              ▼
                     Redis Job Store
                     (or in-memory)
                              │
                              ▼
                   Frontend polls /status
```

#### Job Store (Redis)

Jobs are stored in Redis with a 24-hour TTL:

```
Key: narrato:job:{job_id}
Value: {
  "status": "queued|processing|completed|failed",
  "path": "/outputs/abc123.pptx",
  "error": null,
  "progress": 0-100,
  "preview_urls": ["/previews/{id}/slide-1.png", ...]
}
```

When Redis is unavailable, the system falls back to an in-memory dictionary.

#### Celery Configuration

```python
celery_app = Celery("narrato", broker=REDIS_URL, backend=REDIS_URL)
# Task: narrato.generate_presentation
# Retries: 2 (with 10s delay)
# Soft time limit: 120s
# Hard time limit: 180s
```

---

### 29.10 LLM Service

The LLM client (`services/llm_client.py`) provides:

| Feature | Detail |
|---|---|
| **Providers** | OpenAI (GPT-4o, GPT-4o-mini) and Anthropic (Claude 3.5 Sonnet) |
| **Retry** | 3 attempts with exponential backoff (1s, 2s, 4s) |
| **Rate Limiting** | `asyncio.Semaphore(3)` — max 3 concurrent LLM calls |
| **JSON Parsing** | Strips markdown code fences before parsing |
| **Validation** | `call_llm_json()` enforces dict, `call_llm_json_list()` enforces list |

---

### 29.11 Speaker Notes

Speaker notes are generated as a dedicated pipeline step after content structuring.

For each slide, the LLM generates 3–5 sentences that:
- Explain key points shown on the slide
- Add context not visible on the slide itself
- Suggest transition phrases to the next slide
- Match the presentation's tone and audience

Notes are injected into the `.pptx` file via `python-pptx`'s `slide.notes_slide.notes_text_frame`.

---

### 29.12 Preview System

The preview system converts generated `.pptx` files into slide thumbnail images.

**Flow:**
1. `POST /preview/{job_id}` triggers conversion
2. LibreOffice headless converts `.pptx` → PDF
3. `pdftoppm` (poppler-utils) converts PDF → PNG images
4. Images served as static files from `/previews/{job_id}/`
5. URLs stored in job store and returned via `/status/{job_id}`

**Requirements:**
- `libreoffice` must be installed and available in PATH
- `poppler-utils` for PDF → PNG (optional, falls back to LibreOffice PNG export)

---

### 29.13 Theme System

Three built-in themes control colors, fonts, and sizing across all 14 slide layouts:

| Theme | Primary | Secondary | Accent | Font |
|---|---|---|---|---|
| **modern** | `#6C63FF` (purple) | `#A29BFE` | `#FD79A8` (pink) | Calibri |
| **corporate** | `#1A3C5E` (navy) | `#2E75B6` | `#E8A020` (gold) | Calibri |
| **minimal** | `#2D2D2D` (charcoal) | `#888888` | `#000000` | Calibri |

Themes are defined in `backend/ppt/themes/modern.py` as `ThemeConfig` dataclass instances.

---

### 29.14 Frontend

The React (Vite) frontend provides:

| Feature | Description |
|---|---|
| **Prompt Input** | Textarea for natural language description |
| **Options Panel** | Slide count slider, tone selector, visual style, image toggle |
| **Progress Bar** | Real-time progress percentage with animated bar |
| **Preview Thumbnails** | Grid of slide images (when preview system is available) |
| **Download Button** | Direct `.pptx` download |
| **Error Handling** | User-friendly error messages with retry option |
| **Reset** | "Create another presentation" to start over |

---

### 29.15 uv Package Manager Reference

This project uses [**uv**](https://docs.astral.sh/uv/) for Python dependency management.

```bash
# Install dependencies
uv sync

# Add a new dependency
uv add <package-name>

# Remove a dependency
uv remove <package-name>

# Run a command in the virtual environment
uv run <command>

# Run the FastAPI server
uv run uvicorn backend.main:app --reload --port 8000

# Run the Celery worker
uv run celery -A backend.worker.celery_app worker --loglevel=info

# Run tests
uv run pytest

# Update lock file
uv lock
```

**Key files:**
- `pyproject.toml` — Project metadata + dependency declarations
- `uv.lock` — Deterministic lock file (committed to git)
- `.python-version` — Pinned Python version for uv

---

### 29.16 Dependencies

#### Python (via `pyproject.toml`)

| Package | Version | Purpose |
|---|---|---|
| `fastapi` | ≥0.135 | REST API framework |
| `uvicorn[standard]` | ≥0.42 | ASGI server |
| `pydantic` | ≥2.12 | Data validation & state model |
| `pydantic-settings` | ≥2.13 | Environment-based settings |
| `python-pptx` | ≥1.0 | PowerPoint file generation |
| `openai` | ≥2.30 | OpenAI API client |
| `httpx` | ≥0.28 | Async HTTP client |
| `celery` | ≥5.6 | Distributed task queue |
| `redis` | ≥7.4 | Redis client for job store & broker |
| `pillow` | ≥12.2 | Image processing |
| `requests` | ≥2.33 | HTTP requests |
| `python-dotenv` | ≥1.2 | .env file loading |
| `pytest` | ≥9.0 | Testing framework |
| `pytest-asyncio` | ≥1.3 | Async test support |

#### Frontend (via `package.json`)

| Package | Version | Purpose |
|---|---|---|
| `react` | ^19.2 | UI framework |
| `react-dom` | ^19.2 | React DOM renderer |
| `axios` | ^1.14 | HTTP client |
| `vite` | ^8.0 | Build tool & dev server |

---

### 29.17 Troubleshooting

| Issue | Solution |
|---|---|
| `OPENAI_API_KEY not set` | Create `.env` file with your API key |
| Redis connection refused | Start Redis: `redis-server` or use Docker |
| Celery not picking up tasks | Ensure Redis is running; check `REDIS_URL` in `.env` |
| Preview images not generated | Install `libreoffice` and `poppler-utils` |
| Frontend can't reach backend | Check CORS origins in `backend/main.py` |
| LLM returns invalid JSON | The retry system handles this automatically (3 attempts) |
| `uv sync` fails | Ensure Python ≥3.11 and uv is installed |

---

## 30. Production Architecture

### State-Driven Pipeline

Narrato uses a **state-driven pipeline** where a single `PresentationState` Pydantic model flows through every stage. Each stage reads the current state, performs its transformation, and returns an updated copy. This guarantees:

- **Reproducibility** — the same state always produces the same output
- **Testability** — each stage can be tested in isolation
- **Traceability** — you can inspect the state at any point in the pipeline

The full pipeline executes **10 sequential stages**:

```
User Prompt
  → 1. Prompt Understanding  (LLM extracts topic, type, tone, audience)
  → 2. State Builder          (creates PresentationState from signals)
  → 3. State Completion        (LLM fills missing fields)
  → 4. Story Generator         (LLM creates narrative arc + emotional flow)
  → 5. Slide Planner           (distributes slides across sections by weight)
  → 6. Slide Type Assigner     (maps each slide to one of 14 layout types)
  → 7. Content Structurer      (LLM generates typed JSON content per slide)
  → 8. Visual Mapper           (LLM generates image queries, fetches images)
  → 9. Speaker Notes Generator (LLM writes 3–5 sentences per slide)
  → 10. PPT Generator          (python-pptx renders .pptx with themes)
```

Each LLM stage uses retry logic (3 attempts with exponential backoff) and graceful fallbacks to ensure the pipeline never crashes from transient failures.

### Redis + Celery Workflow

Narrato uses **Redis** as both the job store and the Celery message broker. The async workflow operates as follows:

```
Frontend (React)
   │
   ├── POST /generate  ──→  FastAPI creates job in Redis (status: "queued")
   │                         │
   │                         ├── If Celery available: enqueue task to Redis broker
   │                         └── If Celery unavailable: run as FastAPI background task
   │
   ├── GET /status/{id} ──→  Reads job from Redis (progress: 0–100%)
   │
   ├── GET /download/{id} ─→ Returns .pptx file from disk
   │
   └── POST /preview/{id} ─→ Triggers LibreOffice conversion (background)

Redis (Job Store)                    Celery Worker
┌─────────────────────┐             ┌─────────────────────────┐
│ narrato:job:{id}    │             │ generate_presentation   │
│   status: queued    │◄────────────│   1. Update status      │
│   progress: 0       │             │   2. Run full pipeline  │
│   path: null        │             │   3. Update progress    │
│   preview_urls: null│             │   4. Save .pptx path    │
└─────────────────────┘             │   5. Set completed      │
                                    └─────────────────────────┘
```

**Key design decisions:**
- Jobs have a **24-hour TTL** in Redis
- Celery tasks have a **120s soft timeout** and **180s hard timeout**
- Tasks retry up to **2 times** with a 10-second delay
- If Redis is unavailable, the system **gracefully degrades** to an in-memory job store
- If Celery is unavailable, the system **falls back** to FastAPI background tasks

### PPT Generation Flow

The PPT generator (`ppt/generator.py`) takes the completed `PresentationState` and produces a `.pptx` file:

1. **Theme selection** — picks from `modern`, `corporate`, or `minimal` theme configs
2. **Slide rendering** — iterates over `structured_slides`, dispatches each to its type-specific renderer (14 layout types)
3. **Speaker notes injection** — maps `speaker_notes` by `slide_id` and injects into each slide's notes page
4. **Fallback rendering** — if any slide renderer fails, a generic fallback layout is used
5. **File output** — saves to `{OUTPUT_DIR}/{uuid}.pptx` in 16:9 widescreen format

All 14 slide layout types are supported:
`title_slide`, `section_header`, `agenda_slide`, `problem_slide`, `stats_slide`, `feature_slide`, `comparison_slide`, `timeline_slide`, `example_slide`, `quote_slide`, `image_slide`, `conclusion_slide`, `cta_slide`, `thank_you_slide`

### Preview System Flow

The preview system converts completed `.pptx` files into slide thumbnail images:

```
POST /preview/{job_id}
  → Validate job is completed and .pptx exists
  → Background task starts:
      1. LibreOffice headless converts .pptx → PDF
      2. pdftoppm (poppler-utils) converts PDF → PNG images (150 DPI)
      3. If pdftoppm unavailable, falls back to LibreOffice PNG conversion
  → Preview images stored in outputs/previews/{job_id}/
  → URLs saved to Redis job entry
  → Frontend polls /status and receives preview_urls
  → Images served via /previews/ static file mount
```

**System dependencies for previews:**
- `libreoffice` (headless mode for PPTX → PDF conversion)
- `poppler-utils` (provides `pdftoppm` for PDF → PNG conversion)

---

## 31. Setup (UV)

### Prerequisites

- **Python** ≥ 3.11
- **Node.js** ≥ 18 (for frontend)
- **Redis** server (for job store and Celery broker)
- **LibreOffice** and **poppler-utils** (for slide preview generation)

### Install uv (Python package manager)

```bash
# Install uv (recommended)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Or via pip
pip install uv
```

### Install system dependencies

```bash
# Ubuntu/Debian
sudo apt-get install redis-server libreoffice-impress poppler-utils

# macOS
brew install redis libreoffice poppler
```

### Install Python dependencies

```bash
# From the project root
uv sync
```

This reads `pyproject.toml` and `uv.lock` to install all Python dependencies into a virtual environment.

### Configure environment

```bash
# Copy the example env file
cp .env.example .env

# Edit .env and add your API keys:
#   OPENAI_API_KEY=sk-your-key-here
#   UNSPLASH_ACCESS_KEY=your-unsplash-key  (optional, for images)
```

### Run the backend (FastAPI)

```bash
cd backend
uv run uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

The API will be available at `http://localhost:8000`. API docs at `http://localhost:8000/docs`.

### Run the Celery worker

```bash
# In a separate terminal
cd backend
uv run celery -A worker.celery_app worker --loglevel=info
```

The worker connects to Redis and processes presentation generation jobs asynchronously.

### Run the frontend

```bash
cd frontend
npm install
npm run dev
```

The frontend will be available at `http://localhost:5173`.

### Start Redis

```bash
# Start Redis server
redis-server

# Or as a daemon
redis-server --daemonize yes

# Verify it's running
redis-cli ping
# → PONG
```

### Verify the system

```bash
# Check that all services are running
curl http://localhost:8000/health
# → {"status":"ok","version":"2.0.0","redis":"connected","celery":"connected"}
```

### Full startup sequence (all terminals)

```bash
# Terminal 1: Redis
redis-server

# Terminal 2: Celery worker
cd backend && uv run celery -A worker.celery_app worker --loglevel=info

# Terminal 3: FastAPI backend
cd backend && uv run uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# Terminal 4: Frontend
cd frontend && npm install && npm run dev
```

Then open `http://localhost:5173` in your browser to use Narrato.

---