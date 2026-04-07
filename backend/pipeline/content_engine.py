import logging
import json
from models.presentation_state import PresentationState
from services.llm_client import call_llm_json

logger = logging.getLogger(__name__)

CONTENT_ENGINE_SYSTEM_PROMPT = """You are a Presentation Meaning Structurer.

Return STRICT JSON.

FORMAT:
{
  "structured_slides": [
    {
      "slide_id": 1,
      "intent": "...",
      "primary_element": "...",
      "supporting_elements": ["...", "..."]
    }
  ]
}

RULES:
- Each slide MUST have:
    - 1 strong primary_element
    - 2–4 supporting_elements
- Each element under 12 words
- No paragraphs
- DO NOT use title/points
"""

def extract_role_behavior(role: str) -> str:
    behaviors = {
        "Context": "scopive, baseline, minimal",
        "Hook": "minimal, bold, dominant",
        "Problem": "heavy, contrast",
        "Tension": "fragmented",
        "Insight": "reveal",
        "Solution": "structured clarity, organized",
        "Impact": "stat",
        "Closure": "bold, centered"
    }
    return behaviors.get(role, "minimal, balanced")


async def run_content_engine(state: PresentationState) -> PresentationState:
    """Generate slide content (works for both narrative + structured pipelines)."""

    # ✅ FIX: Remove hard dependency on narrative_arc
    if not state.narrative_arc:
        logger.warning("[content_engine] No narrative_arc found — generating from slide_plan")

        state.narrative_arc = []
        for slide in (state.slide_plan or []):
            state.narrative_arc.append({
                "intent": slide.get("purpose", ""),
                "role_in_story": slide.get("section", "general").capitalize(),
                "key_message": slide.get("purpose", ""),
                "transition_reason": "Structured flow",
                "emotional_tone": "neutral"
            })

    logger.info(f"[content_engine] Generating slide content for {len(state.narrative_arc)} slides")

    # ✅ Use arc only if narrative mode
    if getattr(state, "deck_mode", "general") == "investor":
        arc_json = "Use structured sections (problem, solution, market, etc.)"
    else:
        arc_json = json.dumps(state.narrative_arc, indent=2)

    user_prompt = f"""Topic: {state.topic}
Type: {state.presentation_type}
Deck Mode: {getattr(state, "deck_mode", "general")}
Audience: {state.audience}

Here is the structure:
{arc_json}

Generate EXACTLY {len(state.narrative_arc)} slides.
Each slide must map 1:1.

Return structured_slides with same length.
"""

    try:
        result = await call_llm_json(CONTENT_ENGINE_SYSTEM_PROMPT, user_prompt)
        structured_slides = result.get("structured_slides", [])

        # ✅ FIX: HARD fallback if model fails
        if not structured_slides:
            logger.warning("[content_engine] Empty response — using fallback content")

            structured_slides = []
            for i, arc in enumerate(state.narrative_arc):
                structured_slides.append({
                    "slide_id": i + 1,
                    "intent": arc.get("intent", ""),
                    "primary_element": arc.get("key_message", "Slide"),
                    "supporting_elements": ["Content unavailable"]
                })

        # ✅ Ensure proper structure for ALL slides
        for i, slide in enumerate(structured_slides):
            # fallback content if missing
            if not isinstance(slide.get("content"), dict):
                slide["content"] = {
                    "title": f"Slide {i+1}",
                    "points": ["Content missing"]
                }

            arc_slide = state.narrative_arc[i] if i < len(state.narrative_arc) else {}

            role = arc_slide.get("role_in_story", "Context")
            behavior = extract_role_behavior(role)
            original_intent = arc_slide.get("intent", "")
            emotional_tone = arc_slide.get("emotional_tone", "neutral")

            slide["intent"] = original_intent
            slide["role_in_story"] = role
            slide["emotional_tone"] = emotional_tone
            slide["type"] = "content_slide"
            slide["slide_id"] = i + 1
            slide["why_this_slide"] = arc_slide.get("intent", "")
            slide["why_next_slide"] = arc_slide.get("transition_reason", "")

        # rebuild slide_plan
        slide_plan = []
        for i, slide in enumerate(structured_slides):
            arc = state.narrative_arc[i] if i < len(state.narrative_arc) else {}

            slide_plan.append({
                "slide_id": slide.get("slide_id", i+1),
                "section": arc.get("role_in_story", "general").lower(),
                "purpose": arc.get("key_message", "Slide point"),
                "type": "content_slide"
            })

        return state.model_copy(update={
            "structured_slides": structured_slides,
            "slide_plan": slide_plan
        })

    except Exception as e:
        logger.error(f"[content_engine] Content generation failed: {e}")
        raise e