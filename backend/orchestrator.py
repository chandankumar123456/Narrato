from pipeline.prompt_understanding import parse_prompt
from pipeline.state_builder import build_state
from pipeline.state_completion import complete_state
from pipeline.story_generator import generate_story
from pipeline.slide_planner import plan_slides
from pipeline.slide_type_assigner import assign_slide_types
from pipeline.content_structurer import generate_structured_content
from pipeline.visual_mapper import generate_visual_queries
from ppt.generator import generate_ppt
import logging

logger = logging.getLogger(__name__)

async def run_pipeline(prompt: str, options: dict = {}) -> str:
    logger.info(f"[pipeline] Starting for prompt: {prompt[:80]}")

    signals  = await parse_prompt(prompt)
    signals.update({k: v for k, v in options.items() if v is not None})

    state = build_state(signals)
    logger.info(f"[pipeline] State built: {state.topic} | {state.slide_count} slides")

    state = await complete_state(state)
    state = await generate_story(state)
    logger.info(f"[pipeline] Story: {state.story.get('key_message')}")

    state = plan_slides(state)
    state = assign_slide_types(state)
    logger.info(f"[pipeline] Planned {len(state.slide_plan)} slides")

    state = await generate_structured_content(state)
    state = await generate_visual_queries(state)
    logger.info(f"[pipeline] Content + images ready")

    output_path = generate_ppt(state)
    logger.info(f"[pipeline] PPT generated: {output_path}")

    return output_path