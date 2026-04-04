from pipeline.prompt_understanding import parse_prompt
from pipeline.schema_parser import parse_user_schema
from pipeline.state_builder import build_state
from pipeline.state_completion import complete_state
from pipeline.story_generator import generate_story
from pipeline.slide_planner import plan_slides
from pipeline.slide_type_assigner import assign_slide_types
from pipeline.content_structurer import generate_structured_content
from pipeline.multi_stage_content import generate_multi_stage_content
from pipeline.slide_evaluator import evaluate_and_improve_slides
from pipeline.deck_consistency_optimizer import optimize_deck_consistency
from pipeline.intelligence_report import generate_intelligence_report
from pipeline.strict_slide_planner import plan_slides_strict
from pipeline.strict_content_structurer import generate_strict_content
from pipeline.content_validator import validate_content
from pipeline.visual_mapper import generate_visual_queries
from pipeline.speaker_notes_generator import generate_speaker_notes
from ppt.generator import generate_ppt
from pipeline.visual_rendering_pipeline import run_visual_pipeline
from pipeline.visual_design_engine import run_design_engine
from pipeline.visual_template_engine import run_template_engine
from services.event_system import PipelineEvent, EventType
import logging
import os
from typing import Callable, Optional

logger = logging.getLogger(__name__)


def _compute_progress(completed: int, total: int) -> int:
    """Compute progress 0-100 from completed/total steps."""
    if total <= 0:
        return 0
    return min(100, max(0, int((completed / total) * 100)))


async def run_pipeline(prompt: str, options: dict = {},
                       progress_callback: Optional[Callable[[int], None]] = None,
                       event_callback: Optional[Callable[[PipelineEvent], None]] = None) -> str:
    """Run the full Narrato pipeline with event-driven progress reporting.

    The event_callback receives PipelineEvent instances at every meaningful
    pipeline step. The older progress_callback still works for backward compat.
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

    logger.info(f"[pipeline] Starting for prompt: {prompt[:80]}")
    _emit(EventType.STAGE_UPDATE, "init", "Understanding your prompt…", 3)

    # ── Global steps before per-slide work ────────────────────────
    # Stage 1: Parse prompt signals
    signals = await parse_prompt(prompt)
    signals.update({k: v for k, v in options.items() if v is not None and not k.startswith("_")})

    # Stage 1b: Extract strict user schema
    user_schema = await parse_user_schema(prompt)
    _emit(EventType.STAGE_UPDATE, "prompt_parsed", "Analyzing requirements…", 8)

    # Stage 2: Build state
    state = build_state(signals, user_schema=user_schema)
    total_slides = state.slide_count
    logger.info(
        f"[pipeline] State built: {state.topic} | mode={state.generation_mode} | "
        f"{state.slide_count} slides"
    )
    _emit(EventType.STAGE_UPDATE, "state_built", "Planning presentation structure…", 10,
          total_slides=total_slides)

    # ── Progress math ────────────────────────────────────────────
    # Global steps: parse(1) + schema(1) + state(1) + story(1) + plan(1)
    #   + evaluator(1) + consistency(1) + visuals(1) + notes(1) + report(1) + ppt(1) = 11
    # Per-slide steps: content(1) + design(1) + render(1) = 3
    GLOBAL_STEPS = 11
    per_slide_steps = 3
    total_steps = GLOBAL_STEPS + (total_slides * per_slide_steps)
    completed_steps = 3  # parse + schema + state

    if state.generation_mode == "strict":
        # ── STRICT PIPELINE ─────────────────────────────────────
        logger.info("[pipeline][strict] Using schema-driven pipeline")

        state = plan_slides_strict(state)
        total_slides = len(state.slide_plan)
        total_steps = GLOBAL_STEPS + (total_slides * per_slide_steps)
        completed_steps += 1
        logger.info(f"[pipeline][strict] Planned {len(state.slide_plan)} slides")
        _emit(EventType.STAGE_UPDATE, "slide_plan", "Slide structure planned…",
              _compute_progress(completed_steps, total_steps),
              total_slides=total_slides)

        # Per-field content generation
        state = await generate_strict_content(state)
        completed_steps += 1
        _emit(EventType.STAGE_UPDATE, "content_done", "Content generation complete…",
              _compute_progress(completed_steps, total_steps),
              total_slides=total_slides)

        state = validate_content(state)
        completed_steps += 1
        logger.info(
            "[pipeline][strict] Validation: %s",
            (state.metadata or {}).get("validation_status", "unknown"),
        )
        _emit(EventType.STAGE_UPDATE, "validated", "Content validated…",
              _compute_progress(completed_steps, total_steps),
              total_slides=total_slides)

    else:
        # ── DEFAULT PIPELINE ────────────────────────────────────
        state = await complete_state(state)
        completed_steps += 1
        _emit(EventType.STAGE_UPDATE, "state_complete", "Building narrative arc…",
              _compute_progress(completed_steps, total_steps))

        state = await generate_story(state)
        completed_steps += 1
        logger.info(f"[pipeline] Story: {state.story.get('key_message')}")
        _emit(EventType.STAGE_UPDATE, "story", "Story framework created…",
              _compute_progress(completed_steps, total_steps))

        state = plan_slides(state)
        state = assign_slide_types(state)
        total_slides = len(state.slide_plan)
        total_steps = GLOBAL_STEPS + (total_slides * per_slide_steps)
        completed_steps += 1
        logger.info(f"[pipeline] Planned {len(state.slide_plan)} slides")
        _emit(EventType.STAGE_UPDATE, "slide_plan",
              f"Planning {total_slides} slides…",
              _compute_progress(completed_steps, total_steps),
              total_slides=total_slides)

        # Multi-stage content generation
        state = await generate_multi_stage_content(state)
        completed_steps += 1
        logger.info("[pipeline] Multi-stage content generation complete")
        _emit(EventType.STAGE_UPDATE, "content_done", "Slide content generated…",
              _compute_progress(completed_steps, total_steps),
              total_slides=total_slides)

        # Evaluator
        state = await evaluate_and_improve_slides(state)
        evals = (state.metadata or {}).get("slide_evaluations", [])
        avg_score = (
            round(sum(e.get("overall_score", 0) for e in evals) / len(evals), 1)
            if len(evals) > 0 else 0
        )
        completed_steps += 1
        logger.info(
            "[pipeline] Slide evaluation complete: %d slides, avg score %.1f/5",
            len(evals), avg_score,
        )
        _emit(EventType.STAGE_UPDATE, "evaluated", "Slides evaluated and improved…",
              _compute_progress(completed_steps, total_steps),
              total_slides=total_slides)

        # Deck consistency
        state = await optimize_deck_consistency(state)
        consistency = (state.metadata or {}).get("deck_consistency", {})
        completed_steps += 1
        logger.info(
            "[pipeline] Deck consistency pass: %d slides rewritten",
            consistency.get("slides_rewritten", 0),
        )
        _emit(EventType.STAGE_UPDATE, "consistency", "Deck consistency optimized…",
              _compute_progress(completed_steps, total_steps),
              total_slides=total_slides)

    # ── Shared tail (both paths) ──────────────────────────────────
    state = await generate_visual_queries(state)
    completed_steps += 1
    logger.info(f"[pipeline] Content + images ready")
    _emit(EventType.STAGE_UPDATE, "visual_queries", "Preparing visual elements…",
          _compute_progress(completed_steps, total_steps),
          total_slides=total_slides)

    state = await generate_speaker_notes(state)
    completed_steps += 1
    logger.info(f"[pipeline] Speaker notes generated for {len(state.speaker_notes or [])} slides")
    _emit(EventType.STAGE_UPDATE, "speaker_notes", "Speaker notes written…",
          _compute_progress(completed_steps, total_steps),
          total_slides=total_slides)

    # Intelligence report
    state = await generate_intelligence_report(state)
    if state.intelligence_report:
        _write_intelligence_report(state)
    completed_steps += 1
    logger.info("[pipeline] Intelligence report generated")
    _emit(EventType.STAGE_UPDATE, "report", "Intelligence report generated…",
          _compute_progress(completed_steps, total_steps),
          total_slides=total_slides)

    # ── Per-slide visual pipeline (design + template) ─────────────
    slides = state.structured_slides or []
    theme = getattr(state, "theme", "modern")
    all_html_slides = []

    _emit(EventType.STAGE_UPDATE, "visual_start",
          "Designing and rendering slides…",
          _compute_progress(completed_steps, total_steps),
          total_slides=total_slides)

    for idx, slide in enumerate(slides):
        slide_num = idx + 1

        # Design this slide
        designs = run_design_engine([slide], state_theme=theme)
        completed_steps += 1
        _emit(EventType.SLIDE_DESIGNED, "design",
              f"Designing slide {slide_num} of {total_slides}…",
              _compute_progress(completed_steps, total_steps),
              slide_id=slide_num, total_slides=total_slides)

        # Render HTML for this slide
        html_list = run_template_engine(designs)
        html_content = html_list[0] if html_list else ""
        all_html_slides.append(html_content)
        completed_steps += 1
        _emit(EventType.SLIDE_RENDERED, "render",
              f"Rendered slide {slide_num} of {total_slides}…",
              _compute_progress(completed_steps, total_steps),
              slide_id=slide_num, total_slides=total_slides,
              data={"html": html_content})

    # ── Full visual pipeline for export artifacts (PNG/PDF) ───────
    logger.info("[pipeline] Running visual rendering pipeline for export")
    visual_output = await run_visual_pipeline(state)
    state = state.model_copy(update={"visual_render_output": visual_output})
    logger.info(
        "[pipeline] Visual pipeline: %d HTML slides, %d images",
        len(visual_output.get("html_slides", [])),
        len(visual_output.get("image_paths", [])),
    )

    # PPT generation
    output_path = generate_ppt(state)
    state = state.model_copy(update={"output_path": output_path})
    completed_steps += 1
    logger.info(f"[pipeline] PPT generated: {output_path}")
    _emit(EventType.STAGE_UPDATE, "ppt", "PowerPoint generated…",
          _compute_progress(completed_steps, total_steps),
          total_slides=total_slides)

    # ── Emit completion ────────────────────────────────────────────
    _emit(EventType.JOB_COMPLETED, "completed", "Presentation ready!",
          100, total_slides=total_slides)

    return {
        "pptx_path": output_path,
        "html_slides": all_html_slides if all_html_slides else visual_output.get("html_slides", []),
        "structured_slides": [s for s in (state.structured_slides or [])],
    }


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