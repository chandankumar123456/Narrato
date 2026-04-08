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
        causal_roles = ["Problem", "Consequence", "Escalation", "BreakingPoint", "Solution", "Proof", "Scale", "Ask"]
        for i, slide in enumerate(state.slide_plan or []):
            state.narrative_arc.append({
    "intent": slide.get("purpose", ""),
    "role_in_story": slide.get("section", "Context"),
    "slide_role": causal_roles[min(i, len(causal_roles) - 1)],
    "key_message": slide.get("purpose", ""),
    "cause_from_previous": "",
    "narrative_delta": "",
    "forward_tension": "",
    "tension_level": 5,
    "cause": "",
    "tension": "",
    "resolution": "",
    "next_trigger": "",
    "emotional_tone": "neutral"
})

    logger.info(f"[content_engine] Generating slide content for {len(state.narrative_arc)} slides")

    presentation_mode = getattr(state, "presentation_mode", "generic")
    arc_json = json.dumps(state.narrative_arc, indent=2)

    mode_instructions = ""
    if presentation_mode == "investor":
        mode_instructions = """
Investor emphasis rules (MANDATORY):
- Each input slide includes an importance field: high or low.
- HIGH importance slides: sharpen claims, emphasize outcomes, impact, value, and scale.
- LOW importance slides: keep concise, minimal, no deep explanations.
- Do not give equal depth or tone to every slide.
- Keep logical flow and avoid repetition.
"""

    user_prompt = f"""Topic: {state.topic}
Type: {state.presentation_type}
Presentation Mode: {presentation_mode}
Audience: {state.audience}

Here is the structure:
{arc_json}

Generate EXACTLY {len(state.narrative_arc)} slides.
Each slide must map 1:1.
{mode_instructions}

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
            
            arc_slide = state.narrative_arc[i] if i < len(state.narrative_arc) else {}

            role = arc_slide.get("role_in_story", "Context")
            behavior = extract_role_behavior(role)
            original_intent = arc_slide.get("intent", "")
            emotional_tone = arc_slide.get("emotional_tone", "neutral")
            slide_role = arc_slide.get("slide_role", role)

            slide["intent"] = original_intent
            slide["role_in_story"] = role
            slide["slide_role"] = slide_role
            slide["emotional_tone"] = emotional_tone
            slide["type"] = "content_slide"
            slide["slide_id"] = i + 1
            slide["why_this_slide"] = arc_slide.get("cause_from_previous", "")
            slide["why_next_slide"] = arc_slide.get("forward_tension", "")
            slide["cause_from_previous"] = arc_slide.get("cause_from_previous", "")
            slide["narrative_delta"] = arc_slide.get("narrative_delta", "")
            slide["forward_tension"] = arc_slide.get("forward_tension", "")
            slide["tension_level"] = arc_slide.get("tension_level", 0)
            slide["tension"] = arc_slide.get("tension", "")
            slide["resolution"] = arc_slide.get("resolution", "")
            
            # ✅ FIX: enforce supporting_elements length
            fixed_support = []
            for elem in slide.get("supporting_elements", []):
                if len(elem.split()) < 3:
                    elem = elem + " to maintain system effectiveness"
                fixed_support.append(elem)

            slide["supporting_elements"] = fixed_support

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
