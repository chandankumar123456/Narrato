from pipeline.prompt_understanding import parse_prompt
from pipeline.schema_parser import parse_user_schema
from pipeline.state_builder import build_state
from pipeline.state_completion import complete_state
from pipeline.story_generator import generate_story
from pipeline.slide_planner import plan_slides
from pipeline.slide_type_assigner import assign_slide_types
from pipeline.content_structurer import generate_structured_content
from pipeline.strict_slide_planner import plan_slides_strict
from pipeline.strict_content_structurer import generate_strict_content
from pipeline.content_validator import validate_content
from pipeline.visual_mapper import generate_visual_queries
from pipeline.speaker_notes_generator import generate_speaker_notes
from ppt.generator import generate_ppt
import logging
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
        # ── Default pipeline path (unchanged) ─────────────────────
        state = await complete_state(state)
        _report(25)

        state = await generate_story(state)
        logger.info(f"[pipeline] Story: {state.story.get('key_message')}")
        _report(35)

        state = plan_slides(state)
        state = assign_slide_types(state)
        logger.info(f"[pipeline] Planned {len(state.slide_plan)} slides")
        _report(40)

        state = await generate_structured_content(state)
        _report(60)

    # ── Shared tail (both paths) ──────────────────────────────────
    state = await generate_visual_queries(state)
    logger.info(f"[pipeline] Content + images ready")
    _report(75)

    state = await generate_speaker_notes(state)
    logger.info(f"[pipeline] Speaker notes generated for {len(state.speaker_notes or [])} slides")
    _report(85)

    output_path = generate_ppt(state)
    state = state.model_copy(update={"output_path": output_path})
    logger.info(f"[pipeline] PPT generated: {output_path}")
    _report(95)

    return output_path