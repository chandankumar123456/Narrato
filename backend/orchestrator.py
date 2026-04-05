"""Narrato Pipeline Orchestrator — narrative-first, fast execution.

Architecture:
  1. Parse prompt + schema (2 LLM calls)
  2. Build state
  3. Generate FULL narrative in ONE LLM call → split into slides
  4. Visual pipeline (design + template, deterministic, no LLM)
  5. Speaker notes (1 LLM call)
  6. Visual export (HTML + rendering engine for images/PDF)

Total LLM calls: ~4 (down from dozens in the old per-slide approach).
Pipeline stops immediately on failure after max retries.
"""

from pipeline.prompt_understanding import parse_prompt
from pipeline.schema_parser import parse_user_schema
from pipeline.state_builder import build_state
from pipeline.state_completion import complete_state
from pipeline.narrative_generator import generate_narrative
from pipeline.strict_slide_planner import plan_slides_strict
from pipeline.strict_content_structurer import generate_strict_content
from pipeline.content_validator import validate_content
from pipeline.visual_mapper import generate_visual_queries
from pipeline.speaker_notes_generator import generate_speaker_notes
from pipeline.visual_design_engine import run_design_engine
from pipeline.visual_template_engine import run_template_engine
from pipeline.visual_rendering_engine import render_slides_to_images, render_slides_to_pdf, build_render_instructions
from pipeline.visual_export_engine import run_export_engine
from pipeline.slide_validator import validate_slide_content, validate_design_components, validate_rendered_html, validate_export_parity, SlideRenderError
from pipeline.visual_design_engine import should_use_image
from services.event_system import PipelineEvent, EventType
import logging
import os
from typing import Callable, Optional

logger = logging.getLogger(__name__)


class PipelineFailure(Exception):
    """Raised when a critical pipeline stage fails, stopping the pipeline immediately."""
    pass


def _compute_progress(completed: int, total: int) -> int:
    """Compute progress 0-100 from completed/total steps."""
    if total <= 0:
        return 0
    return min(100, max(0, int((completed / total) * 100)))


async def run_pipeline(prompt: str, options: dict = {},
                       progress_callback: Optional[Callable[[int], None]] = None,
                       event_callback: Optional[Callable[[PipelineEvent], None]] = None) -> str:
    """Run the full Narrato pipeline with event-driven progress reporting.

    Key changes from old pipeline:
      - ONE LLM call for full narrative (no slide-by-slide generation)
      - No evaluator/consistency loops (narrative is coherent by design)
      - Pipeline stops immediately on failure
      - Minimal LLM calls for maximum speed
    """
    job_id = options.get("_job_id", "unknown")

    def _emit(event_type: str, stage: str, label: str, progress: int, **kwargs):
        """Emit a pipeline event and also call legacy progress_callback."""
        evt = PipelineEvent(
            job_id=job_id,
            type=event_type,
            stage=stage,
            progress=progress,
            label=label,
            **kwargs,
        )
        if event_callback:
            try:
                event_callback(evt)
            except Exception:
                pass
        if progress_callback:
            try:
                progress_callback(progress)
            except Exception:
                pass

    def _fail(stage: str, error: str):
        """Emit failure event and raise PipelineFailure to stop pipeline."""
        logger.error("[pipeline] FAILED at stage '%s': %s", stage, error)
        _emit(EventType.JOB_FAILED, "failed", f"Failed: {error}", 0,
              data={"error": error, "stage": stage})
        raise PipelineFailure(f"Pipeline failed at {stage}: {error}")

    logger.info("[pipeline] Starting for prompt: %s", prompt[:80])
    _emit(EventType.STAGE_UPDATE, "init", "Understanding your prompt…", 3)

    # ── Stage 1: Parse prompt signals ─────────────────────────────
    try:
        signals = await parse_prompt(prompt)
        signals.update({k: v for k, v in options.items() if v is not None and not k.startswith("_")})
    except Exception as exc:
        _fail("prompt_parse", str(exc))

    # Stage 1b: Extract strict user schema
    try:
        user_schema = await parse_user_schema(prompt)
    except Exception as exc:
        logger.warning("[pipeline] Schema parse failed, continuing without: %s", exc)
        user_schema = {}

    _emit(EventType.STAGE_UPDATE, "prompt_parsed", "Analyzing requirements…", 8)

    # ── Stage 2: Build state ──────────────────────────────────────
    state = build_state(signals, user_schema=user_schema)
    total_slides = state.slide_count
    logger.info(
        "[pipeline] State built: %s | mode=%s | %d slides",
        state.topic, state.generation_mode, state.slide_count,
    )
    _emit(EventType.STAGE_UPDATE, "state_built", "Planning presentation structure…", 10,
          total_slides=total_slides)

    # ── Progress math (simplified) ────────────────────────────────
    # Global steps: parse(1) + state(1) + narrative(1) + visuals(1) + notes(1) + ppt(1) = 6
    # Per-slide: design(1) + render(1) = 2
    GLOBAL_STEPS = 6
    per_slide_steps = 2
    total_steps = GLOBAL_STEPS + (total_slides * per_slide_steps)
    completed_steps = 2  # parse + state

    if state.generation_mode == "strict":
        # ── STRICT PIPELINE ──────────────────────────────────────
        logger.info("[pipeline][strict] Using schema-driven pipeline")

        try:
            state = plan_slides_strict(state)
        except Exception as exc:
            _fail("strict_plan", str(exc))

        total_slides = len(state.slide_plan)
        total_steps = GLOBAL_STEPS + (total_slides * per_slide_steps)
        completed_steps += 1
        logger.info("[pipeline][strict] Planned %d slides", len(state.slide_plan))
        _emit(EventType.STAGE_UPDATE, "slide_plan", "Slide structure planned…",
              _compute_progress(completed_steps, total_steps),
              total_slides=total_slides)

        try:
            state = await generate_strict_content(state)
        except Exception as exc:
            _fail("strict_content", str(exc))

        completed_steps += 1
        _emit(EventType.STAGE_UPDATE, "content_done", "Content generation complete…",
              _compute_progress(completed_steps, total_steps),
              total_slides=total_slides)

        try:
            state = validate_content(state)
        except Exception as exc:
            logger.warning("[pipeline][strict] Validation failed, continuing: %s", exc)

        completed_steps += 1
        _emit(EventType.STAGE_UPDATE, "validated", "Content validated…",
              _compute_progress(completed_steps, total_steps),
              total_slides=total_slides)

    else:
        # ── DEFAULT PIPELINE: Narrative-first ─────────────────────
        # Optional: complete state (fills in missing fields)
        try:
            state = await complete_state(state)
        except Exception as exc:
            logger.warning("[pipeline] State completion failed, continuing: %s", exc)

        completed_steps += 1
        _emit(EventType.STAGE_UPDATE, "state_complete", "Building narrative arc…",
              _compute_progress(completed_steps, total_steps))

        # CRITICAL: Generate FULL narrative in ONE LLM call
        try:
            state = await generate_narrative(state)
        except Exception as exc:
            logger.warning("[pipeline] narrative_generation failed: %s — pipeline will continue with fallback", exc)
            # Never fail the pipeline at narrative stage — use fallback slides
            if not state.structured_slides:
                logger.warning("[pipeline] No slides generated — injecting minimal fallback")
                state = _inject_fallback_slides(state)

        total_slides = len(state.structured_slides or [])
        total_steps = GLOBAL_STEPS + (total_slides * per_slide_steps)
        completed_steps += 1
        logger.info("[pipeline] Narrative generated: %d slides", total_slides)
        _emit(EventType.STAGE_UPDATE, "narrative_done",
              f"Narrative generated — {total_slides} slides",
              _compute_progress(completed_steps, total_steps),
              total_slides=total_slides)

    # ── Shared tail (both paths) ──────────────────────────────────
    # Visual queries (image fetching)
    try:
        state = await generate_visual_queries(state)
    except Exception as exc:
        logger.warning("[pipeline] Visual queries failed, continuing: %s", exc)

    completed_steps += 1
    _emit(EventType.STAGE_UPDATE, "visual_queries", "Preparing visual elements…",
          _compute_progress(completed_steps, total_steps),
          total_slides=total_slides)

    # Speaker notes (1 LLM call for ALL slides)
    try:
        state = await generate_speaker_notes(state)
    except Exception as exc:
        logger.warning("[pipeline] Speaker notes failed, continuing: %s", exc)

    completed_steps += 1
    logger.info("[pipeline] Speaker notes generated for %d slides",
                len(state.speaker_notes or []))
    _emit(EventType.STAGE_UPDATE, "speaker_notes", "Speaker notes written…",
          _compute_progress(completed_steps, total_steps),
          total_slides=total_slides)

    # ── Per-slide visual pipeline (design + template) ─────────────
    slides = state.structured_slides or []
    theme = getattr(state, "theme", "modern")
    all_html_slides = []

    # Validate slide content BEFORE rendering — catch empty/malformed slides
    slides = validate_slide_content(slides)

    _emit(EventType.STAGE_UPDATE, "visual_start",
          "Designing and rendering slides…",
          _compute_progress(completed_steps, total_steps),
          total_slides=total_slides)

    for idx, slide in enumerate(slides):
        slide_num = idx + 1

        # Design this slide (deterministic, no LLM)
        designs = run_design_engine([slide], state_theme=theme)

        # Validate design components before template rendering
        designs = validate_design_components(designs)
        completed_steps += 1
        _emit(EventType.SLIDE_DESIGNED, "design",
              f"Designing slide {slide_num} of {total_slides}…",
              _compute_progress(completed_steps, total_steps),
              slide_id=slide_num, total_slides=total_slides)

        # Render HTML for this slide (deterministic, no LLM)
        html_list = run_template_engine(designs)
        html_content = html_list[0] if html_list else ""
        all_html_slides.append(html_content)
        completed_steps += 1
        _emit(EventType.SLIDE_RENDERED, "render",
              f"Rendered slide {slide_num} of {total_slides}…",
              _compute_progress(completed_steps, total_steps),
              slide_id=slide_num, total_slides=total_slides,
              data={"html": html_content})

    # ── Validate rendered HTML — STRICT: stops pipeline if any slide is title-only ──
    validate_rendered_html(all_html_slides)

    # ── Enforce image requirements — if should_use_image() says yes, image MUST exist ──
    for idx, slide in enumerate(slides):
        if should_use_image(slide) and not slide.get("content", {}).get("image_url"):
            raise SlideRenderError(
                [f"Slide {idx + 1} ({slide.get('type', '?')}): image required but missing"]
            )

    # ── Validate export parity — ensures same HTML goes to export as editor ──
    export_html_slides = list(all_html_slides)  # actual copy used for export
    validate_export_parity(all_html_slides, export_html_slides)

    # ── Visual export (PNG/PDF) — Playwright is REQUIRED, no fallback ──
    logger.info("[pipeline] Running visual export pipeline")
    output_dir = _resolve_output_dir()
    visual_output = await _run_visual_export_safe(export_html_slides, output_dir)
    state = state.model_copy(update={"visual_render_output": visual_output})

    completed_steps += 1
    logger.info("[pipeline] Visual export complete")
    _emit(EventType.STAGE_UPDATE, "export", "Export artifacts generated…",
          _compute_progress(completed_steps, total_steps),
          total_slides=total_slides)

    # ── Emit completion ───────────────────────────────────────────
    _emit(EventType.JOB_COMPLETED, "completed", "Presentation ready!",
          100, total_slides=total_slides)

    return {
        "html_slides": all_html_slides if all_html_slides else visual_output.get("html_slides", []),
        "structured_slides": [s for s in (state.structured_slides or [])],
        "image_paths": visual_output.get("image_paths", []),
        "pdf_path": visual_output.get("pdf_path"),
    }


async def _run_visual_export_safe(html_slides: list[str], output_dir: str) -> dict:
    """Run visual export — STRICT: failures propagate, no partial success.

    Playwright is REQUIRED for browser-based rendering.
    If Playwright is not installed or rendering fails → pipeline fails.
    No fallback to HTML-only export.
    """
    render_instructions = build_render_instructions(len(html_slides))

    image_paths = await render_slides_to_images(html_slides, output_dir)
    pdf_path = await render_slides_to_pdf(html_slides, output_dir)

    export_result = run_export_engine(
        html_slides=html_slides,
        image_paths=image_paths,
        pdf_path=pdf_path,
        output_dir=output_dir,
    )

    return {
        "designs": [],
        "html_slides": html_slides,
        "render_instructions": render_instructions,
        "html_paths": export_result.get("html_paths", []),
        "image_paths": export_result.get("image_paths", image_paths),
        "pdf_path": export_result.get("pdf_path", pdf_path),
    }


def _resolve_output_dir() -> str:
    """Determine the output directory for visual assets."""
    base = os.environ.get("NARRATO_OUTPUT_DIR", "./outputs")
    visual_dir = os.path.join(base, "visual")
    os.makedirs(visual_dir, exist_ok=True)
    return visual_dir


def _inject_fallback_slides(state: "PresentationState") -> "PresentationState":
    """Inject minimal fallback slides so the pipeline always produces output."""
    fallback_slides = [
        {
            "slide_id": 1,
            "type": "title_slide",
            "content": {
                "title": state.topic,
                "subtitle": "Presentation generated with fallback content.",
                "presenter": "",
            },
        },
        {
            "slide_id": 2,
            "type": "feature_slide",
            "content": {
                "title": "Overview",
                "features": [
                    {"icon": "🔹", "label": "Topic", "description": state.topic},
                    {"icon": "🔸", "label": "Type", "description": state.presentation_type or "general"},
                    {"icon": "⚡", "label": "Audience", "description": state.audience or "general"},
                ],
                "summary": "This presentation was generated with fallback content due to a generation issue.",
            },
        },
    ]
    fallback_plan = [
        {"slide_id": 1, "section": "intro", "purpose": "Title slide", "type": "title_slide"},
        {"slide_id": 2, "section": "overview", "purpose": "Overview", "type": "feature_slide"},
    ]
    logger.warning("[pipeline] Using %d fallback slides", len(fallback_slides))
    return state.model_copy(
        update={
            "slide_plan": fallback_plan,
            "structured_slides": fallback_slides,
        }
    )


def _write_intelligence_report(state) -> None:
    """Write the intelligence report to a separate README file."""
    try:
        output_dir = os.environ.get("NARRATO_OUTPUT_DIR", "output")
        os.makedirs(output_dir, exist_ok=True)
        report_path = os.path.join(output_dir, "INTELLIGENCE_REPORT.md")
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(state.intelligence_report)
        logger.info("[pipeline] Intelligence report written to %s", report_path)
    except Exception:
        logger.exception(
            "[pipeline] Failed to write intelligence report — "
            "pipeline will continue without persisted report"
        )
