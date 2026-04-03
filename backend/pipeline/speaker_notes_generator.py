import json
import logging

from models.presentation_state import PresentationState
from services.llm_client import call_llm_json

logger = logging.getLogger(__name__)


async def generate_speaker_notes(state: PresentationState) -> PresentationState:
    """Generate speaker notes for each slide in the presentation."""
    if not state.structured_slides:
        logger.warning("No structured slides found — skipping speaker notes generation")
        return state

    slides_summary = json.dumps(
        [
            {
                "slide_id": s["slide_id"],
                "type": s["type"],
                "content": s.get("content", {}),
            }
            for s in state.structured_slides
        ],
        indent=2,
    )

    total = len(state.structured_slides)

    system_prompt = (
        "You are an expert presentation coach. "
        "Generate detailed speaker notes for each slide in a presentation. "
        "Return ONLY a valid JSON object with a single key 'notes' whose value is "
        "a list of objects, each with 'slide_id' (int) and 'notes' (str)."
    )

    user_prompt = f"""Presentation topic: {state.topic}
Tone: {state.tone}
Audience: {state.audience or "general"}
Number of slides: {total}

Here are the slides:
{slides_summary}

For EACH slide, write 3-5 sentences of speaker notes that:
1. Explain the key points shown on the slide
2. Add context or background not visible on the slide itself
3. Suggest a transition phrase leading into the next slide
4. Match the {state.tone} tone appropriate for {state.audience or "a general audience"}

Return a JSON object: {{"notes": [{{"slide_id": 1, "notes": "..."}}, ...]}}
"""

    try:
        result = await call_llm_json(system_prompt, user_prompt)
        notes = result.get("notes", [])
    except (ValueError, KeyError):
        logger.exception("Failed to generate speaker notes")
        notes = [
            {"slide_id": s["slide_id"], "notes": ""}
            for s in state.structured_slides
        ]

    return state.model_copy(update={"speaker_notes": notes})
