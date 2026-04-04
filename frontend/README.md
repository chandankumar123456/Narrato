# Narrato Frontend

State-driven React frontend for Narrato — the AI-powered presentation generation engine.

---

## Tech Stack

| Tool               | Version | Purpose                        |
| ------------------ | ------- | ------------------------------ |
| React              | 19      | UI library                     |
| React Router       | 7       | Client-side routing            |
| Tailwind CSS       | 4       | Utility-first styling          |
| Vite               | 8       | Build tool + dev server        |
| Axios              | 1       | HTTP client                    |

---

## Prerequisites

- **Node.js** ≥ 18
- **npm** ≥ 9
- **Backend API** running on `http://localhost:8000` (see [backend README](../README.md))

---

## Quick Start

```bash
# 1. Install dependencies
cd frontend
npm install

# 2. Start the development server (http://localhost:5173)
npm run dev

# 3. Make sure the backend is running in another terminal
cd ../backend
uv run uvicorn main:app --port 8000
```

Vite proxies all API requests (`/generate`, `/status`, `/download`, `/preview`, `/previews`, `/health`) to `http://localhost:8000` automatically during development.

---

## Available Scripts

| Command           | Description                                |
| ----------------- | ------------------------------------------ |
| `npm run dev`     | Start Vite dev server with HMR (port 5173) |
| `npm run build`   | Production build to `dist/`                |
| `npm run preview` | Serve the production build locally         |
| `npm run lint`    | Run ESLint across all source files         |

---

## Project Structure

```
frontend/
├── index.html                    # HTML shell
├── package.json                  # Dependencies & scripts
├── vite.config.js                # Vite + Tailwind + API proxy
│
└── src/
    ├── main.jsx                  # React entry point (BrowserRouter)
    ├── App.jsx                   # Route definitions + layout shell
    ├── index.css                 # Tailwind v4 theme + global styles
    │
    ├── api/
    │   └── narrato.js            # Axios API client (all backend calls)
    │
    ├── hooks/
    │   └── useJob.js             # Job lifecycle state machine hook
    │
    ├── pages/
    │   ├── InputPage.jsx         # /           → Hero + input + options
    │   ├── ProcessingPage.jsx    # /job/:id    → Progress + live preview
    │   └── ResultPage.jsx        # /job/:id/result → Download + grid
    │
    └── components/
        ├── Navbar.jsx            # Sticky glassmorphism navigation bar
        ├── Footer.jsx            # Copyright + links
        ├── SuggestionChips.jsx   # Preset prompt chips
        ├── OptionsPanel.jsx      # Slide count, tone, style, image toggle
        ├── ProgressPanel.jsx     # Progress bar + pipeline stage indicators
        ├── LivePreview.jsx       # Incremental slide grid with skeletons
        └── ErrorBlock.jsx        # Error state with retry action
```

---

## Architecture

### State Model

The application follows a **state-driven architecture** where all UI transitions are controlled by the backend job lifecycle:

```
idle  ──(POST /generate)──►  processing  ──(completed)──►  done
                                  │                           │
                              (failed)                   (reset)
                                  │                           │
                                  ▼                           ▼
                                error  ────(retry)────►    idle
```

The `useJob` hook in `src/hooks/useJob.js` encapsulates this entire lifecycle:

- **State**: `prompt`, `status`, `jobId`, `error`, `progress`, `previewUrls`, `options`
- **Actions**: `handleGenerate`, `handleReset`, `handleRetry`, `resumeJob`, `setPrompt`, `updateOption`

### Routing

| Route               | Page             | Backend State          |
| -------------------- | ---------------- | ---------------------- |
| `/`                  | InputPage        | idle                   |
| `/job/:job_id`       | ProcessingPage   | queued / processing    |
| `/job/:job_id/result`| ResultPage       | completed              |

Route transitions are **driven by backend status**:

- `InputPage` → navigates to `/job/:id` after `POST /generate`
- `ProcessingPage` → auto-redirects to `/job/:id/result` when backend reports `completed`
- `ProcessingPage` → renders `ErrorBlock` inline when backend reports `failed`
- `ResultPage` → redirects to `/job/:id` if job is still processing
- Direct URL navigation (e.g. browser refresh) resumes polling via `resumeJob()`

### Backend Integration

All API calls are in `src/api/narrato.js`:

| Function                | Method          | Endpoint             |
| ----------------------- | --------------- | -------------------- |
| `generatePresentation`  | `POST`          | `/generate`          |
| `pollStatus`            | `GET`           | `/status/:job_id`    |
| `requestPreview`        | `POST`          | `/preview/:job_id`   |
| `downloadUrl`           | URL constructor | `/download/:job_id`  |
| `previewImageUrl`       | URL constructor | `/previews/...`      |

**Polling strategy:**

- Job status: every **2 seconds** during `processing`
- Preview images: every **3 seconds** after completion (max 10 attempts / 30 seconds)
- Polling intervals are cleaned up on component unmount

### Live Preview

The `LivePreview` component progressively renders slide thumbnails:

1. During processing (progress > 20%): shows skeleton placeholder grid
2. When `preview_urls` arrive from backend: replaces skeletons one-by-one with real images
3. Remaining slots show skeleton/placeholder indicators until all slides render

---

## Design System

The design system is implemented via Tailwind CSS v4 custom theme tokens in `src/index.css`.

### Surface Hierarchy (No-Border Rule)

Boundaries between sections use **background color shifts**, not borders:

| Token             | Color     | Use                          |
| ----------------- | --------- | ---------------------------- |
| `background`      | `#f9f9ff` | Base page background         |
| `surface-low`     | `#f1f3ff` | Input backgrounds, cards     |
| `surface-lowest`  | `#ffffff` | Active cards, elevated areas |
| `surface-high`    | `#e8eaff` | Slider tracks, highlights    |

### Typography (Dual-Font)

| Level      | Font    | Weight | Use Case                   |
| ---------- | ------- | ------ | -------------------------- |
| Display    | Manrope | 700    | Hero headline (3.5rem)     |
| Headline   | Manrope | 600    | Section headers (1.75rem)  |
| Body       | Inter   | 400    | General UI text (0.875rem) |
| Label      | Inter   | 500    | Metadata, chips (0.75rem)  |

### Color Tokens

| Token                | Value                  | Use                    |
| -------------------- | ---------------------- | ---------------------- |
| `primary`            | `#4f46e5`              | Buttons, active states |
| `primary-hover`      | `#4338ca`              | Button hover           |
| `on-surface`         | `#141b2b`              | Primary text           |
| `on-surface-variant` | `#64748b`              | Secondary text         |
| `on-surface-dim`     | `#94a3b8`              | Placeholder, metadata  |
| `success`            | `#16a34a`              | Completion states      |
| `error`              | `#dc2626`              | Error states           |

### Custom Animations

- **AI Pulse** (`.ai-pulse`): Breathing opacity effect for active pipeline stages
- **Progress Shine** (`.progress-bar-animated`): Animated gradient on progress bar
- **Skeleton Shimmer** (`.skeleton`): Loading placeholder animation
- **Toggle Switch** (`.toggle-switch`): Custom boolean toggle component

---

## Configuration

### Vite Dev Proxy (`vite.config.js`)

All API paths are proxied to the backend:

```js
server: {
  proxy: {
    '/generate': 'http://localhost:8000',
    '/status':   'http://localhost:8000',
    '/download': 'http://localhost:8000',
    '/preview':  'http://localhost:8000',
    '/previews': 'http://localhost:8000',
    '/health':   'http://localhost:8000',
  },
}
```

### CORS (Backend)

The backend allows requests from `http://localhost:5173` (Vite dev) and `http://localhost:3000`.

---

## Production Build

```bash
npm run build
```

Outputs optimized static files to `dist/`. Serve with any static file server. For production, configure the backend URL via environment variables or a reverse proxy (e.g. nginx) that forwards `/generate`, `/status`, `/download`, `/preview`, and `/previews` to the backend.

