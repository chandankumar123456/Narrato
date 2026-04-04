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
import logging
import os
from typing import Callable, Optional

logger = logging.getLogger(__name__)

async def run_pipeline(prompt: str, options: dict = {},
                       progress_callback: Optional[Callable[[int], None]] = None) -> str:
    def _report(pct: int):
        if progress_callback:
            try:
                progress_callback(pct)
            except Exception:
                pass

    logger.info(f"[pipeline] Starting for prompt: {prompt[:80]}")
    _report(5)

    # Stage 1: Parse prompt signals (used for tone/audience hints)
    signals = await parse_prompt(prompt)
    signals.update({k: v for k, v in options.items() if v is not None})

    # Stage 1b: Attempt to extract a strict user schema
    user_schema = await parse_user_schema(prompt)
    _report(15)

    # Stage 2: Build state (strict or default mode)
    state = build_state(signals, user_schema=user_schema)
    logger.info(
        f"[pipeline] State built: {state.topic} | mode={state.generation_mode} | "
        f"{state.slide_count} slides"
    )
    _report(20)

    if state.generation_mode == "strict":
        # ── STRICT PIPELINE — isolated execution path ─────────────
        logger.info("[pipeline][strict] Using schema-driven pipeline")

        # Deterministic slide plan from schema (no story, no sections)
        state = plan_slides_strict(state)
        logger.info(f"[pipeline][strict] Planned {len(state.slide_plan)} slides")
        _report(40)

        # Per-field constrained generation (field-level regeneration inside)
        state = await generate_strict_content(state)
        _report(55)

        # Non-corrective validation — assert only, hard fail if invalid
        state = validate_content(state)
        logger.info(
            "[pipeline][strict] Validation: %s",
            (state.metadata or {}).get("validation_status", "unknown"),
        )
        _report(60)

    else:
        # ── Default pipeline path ─────────────────────────────────
        state = await complete_state(state)
        _report(25)

        state = await generate_story(state)
        logger.info(f"[pipeline] Story: {state.story.get('key_message')}")
        _report(35)

        state = plan_slides(state)
        state = assign_slide_types(state)
        logger.info(f"[pipeline] Planned {len(state.slide_plan)} slides")
        _report(40)

        # Phase 1-4: Multi-stage content generation with validation,
        # critic loop, and intent enforcement
        state = await generate_multi_stage_content(state)
        logger.info("[pipeline] Multi-stage content generation complete")
        _report(55)

        # Phase 1-6 Evaluator: Hard validation, scoring, strict critic,
        # targeted regeneration, and intent enforcement on generated slides
        state = await evaluate_and_improve_slides(state)
        evals = (state.metadata or {}).get("slide_evaluations", [])
        avg_score = (
            round(sum(e.get("overall_score", 0) for e in evals) / len(evals), 1)
            if len(evals) > 0 else 0
        )
        logger.info(
            "[pipeline] Slide evaluation complete: %d slides, avg score %.1f/5",
            len(evals), avg_score,
        )
        _report(60)

        # Deck-level consistency optimization: tone, depth, terminology,
        # bullet structure alignment across all slides
        state = await optimize_deck_consistency(state)
        consistency = (state.metadata or {}).get("deck_consistency", {})
        logger.info(
            "[pipeline] Deck consistency pass: %d slides rewritten",
            consistency.get("slides_rewritten", 0),
        )
        _report(65)

    # ── Shared tail (both paths) ──────────────────────────────────
    state = await generate_visual_queries(state)
    logger.info(f"[pipeline] Content + images ready")
    _report(75)

    state = await generate_speaker_notes(state)
    logger.info(f"[pipeline] Speaker notes generated for {len(state.speaker_notes or [])} slides")
    _report(85)

    # Phase 5: Generate intelligence report (evaluation README)
    state = await generate_intelligence_report(state)
    if state.intelligence_report:
        _write_intelligence_report(state)
    logger.info("[pipeline] Intelligence report generated")
    _report(90)

    output_path = generate_ppt(state)
    state = state.model_copy(update={"output_path": output_path})
    logger.info(f"[pipeline] PPT generated: {output_path}")
    _report(95)

    return output_path


def _write_intelligence_report(state: PresentationState) -> None:
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