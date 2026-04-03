from pipeline.prompt_understanding import parse_prompt
from pipeline.state_builder import build_state
from pipeline.state_completion import complete_state
from pipeline.story_generator import generate_story
from pipeline.slide_planner import plan_slides
from pipeline.slide_type_assigner import assign_slide_types
from pipeline.content_structurer import generate_structured_content
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

    signals  = await parse_prompt(prompt)
    signals.update({k: v for k, v in options.items() if v is not None})
    _report(15)

    state = build_state(signals)
    logger.info(f"[pipeline] State built: {state.topic} | {state.slide_count} slides")
    _report(20)

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