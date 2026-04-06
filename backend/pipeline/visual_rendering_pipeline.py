"""
Visual Rendering Pipeline — Orchestrates Stages 1–4

Executes in strict sequential order:
  1. Design Engine   → layout, components, theme
  2. Template Engine  → HTML/Tailwind CSS
  3. Rendering Engine → Playwright PNG/PDF (sync)
  4. Export Engine    → HTML files

This module is called from the main orchestrator after content is
finalized.
"""

import logging
import os
from typing import Optional

from pipeline.dynamic_composition_engine import run_dynamic_composition_engine
from pipeline.visual_rendering_engine import run_rendering_engine
from pipeline.visual_export_engine import run_export_engine

logger = logging.getLogger(__name__)


async def run_visual_pipeline(state) -> dict:
    """
    Execute the full 4-stage visual rendering pipeline.

    If Playwright is NOT installed, Stage 3 (rendering) is SKIPPED entirely —
    no subprocess is called, no rendering is attempted.

    Args:
        state: PresentationState with structured_slides populated.

    Returns:
        Dictionary containing all visual output:
        {
            "designs": [...],          # per-slide design specs
            "html_slides": [...],       # per-slide HTML strings
            "render_instructions": {…}, # viewport, export targets
            "html_paths": [...],        # saved HTML file paths
            "image_paths": [...],       # PNG paths (if rendered)
            "pdf_path": str | None,     # PDF path (if rendered)
        }
    """
    slides = state.structured_slides or []
    if not slides:
        logger.warning("[visual_pipeline] No structured slides — skipping")
        return _empty_result()

    theme = getattr(state, "theme", "modern")
    output_dir = _resolve_output_dir(state)

    # ── Stage 1 & 2: Dynamic Composition Engine ──────────────────────────────────
    logger.info("[visual_pipeline] Stage 1 & 2: Dynamic Composition Engine (%d slides)", len(slides))
    designs, html_slides = await run_dynamic_composition_engine(
        slides,
        state_theme=theme
    )

    # ── Stage 3: Rendering Engine (async, graceful degradation) ──
    logger.info("[visual_pipeline] Stage 3: Rendering Engine")
    try:
        render_result = await run_rendering_engine(html_slides, output_dir)
    except Exception as exc:
        logger.warning("[visual_pipeline] Rendering failed: %s — continuing without images", exc)
        render_result = _empty_render_result(len(html_slides))

    # ── Stage 4: Export Engine ──────────────────────────────────
    logger.info("[visual_pipeline] Stage 4: Export Engine")
    export_result = run_export_engine(
        html_slides=html_slides,
        image_paths=render_result["image_paths"],
        pdf_path=render_result["pdf_path"],
        output_dir=output_dir,
    )

    # ── Combine all results ─────────────────────────────────────
    result = {
        "designs": designs,
        "html_slides": html_slides,
        "render_instructions": render_result["render_instructions"],
        "html_paths": export_result["html_paths"],
        "image_paths": export_result["image_paths"],
        "pdf_path": export_result["pdf_path"],
    }

    logger.info(
        "[visual_pipeline] Complete: %d designs, %d HTML, %d images, pdf=%s",
        len(designs),
        len(html_slides),
        len(result["image_paths"]),
        bool(result["pdf_path"]),
    )

    return result


def _empty_render_result(slide_count: int) -> dict:
    """Return an empty render result when rendering is skipped."""
    from pipeline.visual_rendering_engine import build_render_instructions
    return {
        "render_instructions": build_render_instructions(slide_count),
        "image_paths": [],
        "pdf_path": None,
    }


def _resolve_output_dir(state) -> str:
    """Determine the output directory for visual assets."""
    base = os.environ.get("NARRATO_OUTPUT_DIR", "./outputs")
    visual_dir = os.path.join(base, "visual")
    os.makedirs(visual_dir, exist_ok=True)
    return visual_dir


def _empty_result() -> dict:
    return {
        "designs": [],
        "html_slides": [],
        "render_instructions": {},
        "html_paths": [],
        "image_paths": [],
        "pdf_path": None,
    }
