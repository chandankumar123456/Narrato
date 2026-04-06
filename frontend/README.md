# Narrato Frontend

Real-time React frontend for the Narrato AI presentation engine — handles prompt input, progressive slide rendering via SSE, and an interactive slide editor.

---

## Overview

The frontend is a React 19 SPA that communicates with the FastAPI backend via REST endpoints and Server-Sent Events. It follows a state-driven architecture where all UI transitions are determined by backend job status.

**Three modes of interaction:**
1. **Input** — prompt entry with configuration options
2. **Processing** — real-time progress tracking with live slide preview
3. **Editing** — full-screen interactive editor with AI-assisted regeneration

---

## Architecture

### Application Flow

```
InputPage ──(POST /generate)──► ProcessingPage ──(JOB_COMPLETED)──► EditorPage
    │                                │                                   │
    │                           EventSource                         useEditor
    │                          /stream/{id}                              │
    │                                │                          GET/POST /slides,
    │                           Live preview                    /regenerate,
    │                          (iframe+HTML)                    /restyle, ...
    │                                │
    │                           Auto-redirect
    │                          to /editor/:id
    │
    └───────────────────── ResultPage (legacy, download-only)
```

### Component Structure

```
App.jsx
├── Navbar + Footer (standard pages)
├── Routes
│   ├── /                    → InputPage
│   │   ├── SuggestionChips
│   │   └── OptionsPanel
│   ├── /job/:job_id         → ProcessingPage
│   │   ├── ProgressPanel
│   │   ├── LivePreview (SSE iframes)
│   │   └── ErrorBlock
│   ├── /job/:job_id/result  → ResultPage
│   └── /editor/:job_id     → EditorPage (own layout)
│       ├── EditorNavbar
│       ├── SlidePanel (left sidebar)
│       ├── SlideCanvas (center)
│       ├── ControlPanel (right sidebar)
│       ├── AIAssistant (slide-over panel)
│       ├── EditModal
│       └── ExportModal
```

### State Flow

```
┌──────────────────────────────────────────────────┐
│                    useJob Hook                    │
│                                                  │
│  State: prompt, status, jobId, error, progress,  │
│         stageLabel, previewUrls, options          │
│                                                  │
│  Status Machine:                                 │
│    idle ──► processing ──► done                  │
│                 │                                │
│                 └──► error ──(retry)──► idle      │
│                                                  │
│  Integrates:                                     │
│    useStream (SSE) ─── primary progress source   │
│    Polling fallback ── 2s interval via /status   │
│                                                  │
└──────────────────────────────────────────────────┘
```

---

## Key Hooks

### useJob (`hooks/useJob.js`)

Encapsulates the full job lifecycle. Manages all state transitions and backend communication.

| State | Trigger | Next State |
|-------|---------|------------|
| `idle` | `handleGenerate()` | `processing` |
| `processing` | `stream.isDone` or poll `completed` | `done` |
| `processing` | `stream.error` or poll `failed` | `error` |
| `error` | `handleRetry()` | `idle` |
| `done` | `handleReset()` | `idle` |

**SSE integration**: When `status === "processing"`, `useStream(jobId)` activates. SSE progress/label updates are synced into local state via `useEffect`. Polling runs as a fallback with lower update priority when SSE is connected.

**Preview polling**: After completion, triggers `POST /preview/{job_id}` then polls `/status` every 3s (max 10 attempts) for preview image URLs.

**Direct URL support**: `resumeJob(id)` re-initializes state and starts polling when a user navigates directly to `/job/:id`.

### useStream (`hooks/useStream.js`)

SSE subscription hook. Opens `EventSource("/stream/{jobId}")` and maintains consolidated state.

**State object:**
```javascript
{
  events: [],        // All received events
  progress: 0,       // Latest progress 0–100
  label: "",         // Latest stage label
  stage: "",         // Machine-readable stage name
  slides: {},        // {slide_id: {status, html, slide_id}}
  totalSlides: 0,    // From first event with total_slides
  isDone: false,     // Set on JOB_COMPLETED
  error: null,       // Set on JOB_FAILED
  connected: false,  // EventSource connection state
}
```

**Event handling:**
- `SLIDE_DESIGNED` → sets `slides[id].status = "designed"`
- `SLIDE_RENDERED` → sets `slides[id].status = "rendered"` + stores HTML content
- `JOB_COMPLETED` → sets `isDone = true`, closes connection
- `JOB_FAILED` → sets `error`, closes connection

**Reset pattern**: Uses React-approved "adjust state during render" — when `jobId` changes, state resets to initial values without `useEffect`.

### useEditor (`hooks/useEditor.js`)

Manages the interactive slide editor state and all editing operations.

**State**: `slides`, `activeSlide` (index), `loading`, `slideLoading` (slide_id being processed), `theme`, `error`.

**Operations:**
| Method | API Call | Effect |
|--------|----------|--------|
| `loadSlides()` | `GET /slides/{job_id}` | Populate slide list |
| `handleRegenerate(slideId, instruction)` | `POST /regenerate-slide/{job_id}` | Replace single slide content + HTML |
| `handleRestyle(theme, density)` | `POST /restyle-slides/{job_id}` | Re-render all slides with new theme |
| `handleUpdateSlide(slideId, content)` | `POST /update-slide/{job_id}` | Update content fields, re-render |
| `handleDuplicate(slideId)` | `POST /duplicate-slide/{job_id}` | Insert copy, reload all |
| `handleDelete(slideId)` | `DELETE /delete-slide/{job_id}/{slide_id}` | Remove slide, renumber |

Each slide object carries a `cacheKey` (timestamp) to force iframe refresh on update.

---

## Real-time UI Behavior

### Progressive Rendering

During generation, the ProcessingPage shows slides as they complete:

```
┌─────────────────────────────────────────────┐
│  Generating your presentation...        78% │
│  Designing and rendering slides…            │
│  ████████████████████████░░░░░░░  10 slides │
│                                             │
│  ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐          │
│  │ S01 │ │ S02 │ │ S03 │ │ S04 │  rendered │
│  │(html)│ │(html)│ │(html)│ │(html)│         │
│  └─────┘ └─────┘ └─────┘ └─────┘          │
│  ┌ ─ ─ ┐ ┌ ─ ─ ┐ ┌ ─ ─ ┐ ┌ ─ ─ ┐        │
│  │skel │ │skel │ │skel │ │skel │  pending  │
│  └ ─ ─ ┘ └ ─ ─ ┘ └ ─ ─ ┘ └ ─ ─ ┘        │
└─────────────────────────────────────────────┘
```

**Mechanism:**
1. SSE delivers `SLIDE_RENDERED` events with `data.html` containing the full HTML
2. `useStream.slides[id]` stores the HTML content
3. ProcessingPage renders completed slides as `<iframe srcDoc={html}>` in a 4-column grid
4. Remaining slots show skeleton placeholders (first pending slot is animated)
5. On `JOB_COMPLETED`, auto-navigates to `/editor/{job_id}`

### Slide States

| State | Source | Visual |
|-------|--------|--------|
| Pending | No event yet | Skeleton placeholder |
| Designed | `SLIDE_DESIGNED` event | Skeleton placeholder (no visible change) |
| Rendered | `SLIDE_RENDERED` event | HTML iframe with live content |

---

## UI Structure

### Pages

| Page | Route | Layout | Purpose |
|------|-------|--------|---------|
| InputPage | `/` | Navbar + Footer | Prompt textarea, suggestion chips, options panel, generate button |
| ProcessingPage | `/job/:job_id` | Navbar + Footer | Progress bar, stage indicators, live slide preview grid |
| ResultPage | `/job/:job_id/result` | Navbar + Footer | Preview grid, download button, "Open in Editor" link |
| EditorPage | `/editor/:job_id` | Full-screen (no shared nav) | Three-panel editor layout |

### Editor Layout

```
┌──────────────────────────────────────────────────────────┐
│  EditorNavbar: [N Narrato] [Editor]           [New][Export] │
├──────────┬──────────────────────────────┬────────────────┤
│          │                              │                │
│  Slide   │       Slide Canvas           │   Control      │
│  Panel   │                              │   Panel        │
│  (w-56)  │   ┌──────────────────────┐   │   (w-64)       │
│          │   │                      │   │                │
│  [01]    │   │   Active Slide       │   │  Theme:        │
│  [02]    │   │   (16:9 iframe)      │   │  🌙 ☀️ 🎨     │
│  [03]●   │   │                      │   │                │
│  [04]    │   │   Hover overlay:     │   │  Style:        │
│  [05]    │   │   [Edit][Regen][Dup] │   │  ○ Visual      │
│          │   │                      │   │  ● Balanced    │
│  thumb   │   └──────────────────────┘   │  ○ Minimal     │
│  iframes │                              │  ○ Data Heavy  │
│  scaled  │   ◄ 3 / 10 ►  [slide type]  │                │
│  at 12%  │                              │  [Apply Theme] │
│          │                              │  [Edit Slide]  │
│          │                              │  [AI Assistant] │
│          │                              │  [Export]       │
└──────────┴──────────────────────────────┴────────────────┘
```

---

## Slide Rendering

### Iframe Strategy

All slide rendering uses `<iframe>` elements:

| Context | Source | Sandbox | Interaction |
|---------|--------|---------|-------------|
| ProcessingPage preview | `srcDoc={html}` from SSE | `allow-same-origin` | `pointer-events-none` |
| SlidePanel thumbnails | `src={html_url}` | `allow-same-origin` | `pointer-events-none`, scaled 12% |
| SlideCanvas (active) | `srcDoc={html}` or `src={html_url}` | `allow-same-origin allow-scripts` | Full interaction |

HTML slides are standalone documents (1920×1080) with **embedded CSS** from the backend (`pipeline/static/slides.css` inlined in each document). They are not styled with Tailwind inside the iframe; the app shell still uses Tailwind v4 separately.

The `cacheKey` query parameter forces iframe refresh after content updates.

### HTML Injection Safety

- Backend HTML-escapes all content via `html.escape()` in `visual_template_engine.py`
- Processing page iframes: `sandbox="allow-same-origin"` + `pointer-events-none`
- Editor canvas: `sandbox="allow-same-origin allow-scripts"` for CSS/animation

---

## Interaction System

### Editing

1. **Inline edit** (EditModal): Opens modal with content fields as inputs/textareas. Supports string fields, bullet arrays, nested objects, and JSON arrays. Save triggers `POST /update-slide` → re-render → iframe refresh.

2. **AI regeneration** (AIAssistant): Slide-over panel with 6 quick actions:
   - Improve this slide
   - Add an example
   - Make more persuasive
   - Simplify content
   - Add data/stats
   - Make more visual

   Plus custom instruction textarea. Triggers `POST /regenerate-slide` with instruction.

3. **Theme switching** (ControlPanel): Select theme (Dark/Light/Gradient) and density (Visual/Minimal/Data Heavy/Balanced). Apply triggers `POST /restyle-slides` → all slides re-rendered.

4. **Slide management**: Duplicate and delete via SlidePanel hover buttons or Canvas overlay. Keyboard navigation: Arrow keys for slide navigation.

### Navigation

- SlidePanel: click to select
- SlideCanvas: Arrow buttons + keyboard arrows (Left/Up = previous, Right/Down = next)
- Navigation disabled when input/textarea focused

---

## Progress System

### ProgressPanel

Displays 5 pipeline stages with visual indicators:

| Stage | Threshold | Icon State |
|-------|-----------|------------|
| Understanding your prompt | 5% | active/done |
| Building narrative | 20% | active/done |
| Generating slide content | 40% | active/done |
| Designing and rendering | 70% | active/done |
| Finalizing presentation | 90% | active/done |

**SSE label takes priority** — when `stageLabel` is provided by SSE, it replaces the threshold-derived label. The thresholds serve as a polling-only fallback.

**Visual states**: `pending` (gray circle), `active` (pulsing indigo circle), `done` (green checkmark).

---

## API Integration

### Endpoints Used

| Function | Method | Endpoint | Hook |
|----------|--------|----------|------|
| `generatePresentation` | POST | `/generate` | useJob |
| `pollStatus` | GET | `/status/{job_id}` | useJob (polling) |
| `requestPreview` | POST | `/preview/{job_id}` | useJob |
| `fetchSlides` | GET | `/slides/{job_id}` | useEditor |
| `regenerateSlide` | POST | `/regenerate-slide/{job_id}` | useEditor |
| `restyleSlides` | POST | `/restyle-slides/{job_id}` | useEditor |
| `updateSlide` | POST | `/update-slide/{job_id}` | useEditor |
| `duplicateSlide` | POST | `/duplicate-slide/{job_id}` | useEditor |
| `deleteSlide` | DELETE | `/delete-slide/{job_id}/{slide_id}` | useEditor |
| SSE stream | GET | `/stream/{job_id}` | useStream |
| Download | URL | `/download/{job_id}` | ExportModal |

### Data Flow

```
User Action
    │
    ▼
API Call (axios)
    │
    ▼
Backend Processing
    │
    ▼
Response Data
    │
    ▼
Hook State Update (setState)
    │
    ▼
React Re-render
    │
    ▼
UI Update (iframe refresh, progress bar, etc.)
```

### Proxy Configuration

Vite dev server proxies all API paths to `http://localhost:8000`:
- `/generate`, `/status`, `/download`, `/preview`, `/previews`, `/health`
- `/stream`, `/slides`, `/regenerate-slide`, `/restyle-slides`
- `/update-slide`, `/reorder-slides`, `/duplicate-slide`, `/delete-slide`, `/outputs`

---

## State Management

No external state library (Redux, Zustand). All state lives in custom hooks:

| Hook | Scope | State |
|------|-------|-------|
| `useJob` | Global (App.jsx) | Job lifecycle, prompt, options, progress |
| `useStream` | Activated by useJob | SSE events, slide data, connection |
| `useEditor` | EditorPage only | Slides, active selection, loading, theme |

State is passed via props from App → Pages → Components. The editor page manages its own state independently via `useEditor(job_id)`.

---

## UX Principles

1. **Progressive disclosure** — skeleton placeholders → rendered content → interactive editor
2. **Real-time feedback** — SSE progress labels replace static spinners
3. **Non-blocking interactions** — slide regeneration shows loading state per-slide, not globally
4. **Direct manipulation** — hover overlays on canvas for edit/regenerate/duplicate
5. **Keyboard-first navigation** — arrow keys for slide traversal
6. **Graceful degradation** — polling fallback when SSE unavailable, skeleton grid when no previews
7. **No hard borders** — surface color hierarchy (background → surface-low → surface-lowest) instead of borders
8. **Dual typography** — Manrope for headings (geometric, bold), Inter for body (neutral, readable)

---

## Local Setup

### Prerequisites

- Node.js ≥ 20
- npm ≥ 9
- Backend running on `http://localhost:8000` (see [backend README](../backend/README.md))

### Quick Start

```bash
cd frontend
npm install
npm run dev
# → http://localhost:5173
```

### Available Scripts

| Command | Description |
|---------|-------------|
| `npm run dev` | Vite dev server with HMR (port 5173) |
| `npm run build` | Production build to `dist/` |
| `npm run preview` | Serve production build locally |
| `npm run lint` | ESLint across all source files |

---

## Build & Deployment

### Production Build

```bash
npm run build
# → dist/
```

Outputs optimized static files. Serve with any static server (nginx, Vercel, Netlify).

### Production Configuration

In production, configure a reverse proxy to forward API paths to the backend:

```nginx
location /generate    { proxy_pass http://backend:8000; }
location /status      { proxy_pass http://backend:8000; }
location /download    { proxy_pass http://backend:8000; }
location /stream      { proxy_pass http://backend:8000; proxy_buffering off; }
location /slides      { proxy_pass http://backend:8000; }
location /outputs     { proxy_pass http://backend:8000; }
# ... all other API paths
```

For SSE (`/stream`), ensure `proxy_buffering off` is set to prevent nginx from buffering the event stream.

### Design System Tokens

The **application UI** design system is defined in `src/index.css` via Tailwind v4 `@theme` directive:

| Token | Value | Use |
|-------|-------|-----|
| `--color-primary` | `#4f46e5` | Buttons, active states |
| `--color-background` | `#f9f9ff` | Page background |
| `--color-surface-low` | `#f1f3ff` | Input backgrounds |
| `--color-surface-lowest` | `#ffffff` | Elevated cards |
| `--color-on-surface` | `#141b2b` | Primary text |
| `--font-heading` | Manrope | Headlines, section headers |
| `--font-body` | Inter | Body text, labels |

**Slide decks** inside iframes use the backend’s `slides.css` (themes, slide typography, layout variants). Changing slide appearance is done in the backend repo under `backend/pipeline/static/slides.css`, not in the frontend Tailwind theme.

