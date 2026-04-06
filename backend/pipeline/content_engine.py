import logging
import json
from models.presentation_state import PresentationState
from services.llm_client import call_llm_json

logger = logging.getLogger(__name__)

CONTENT_ENGINE_SYSTEM_PROMPT = """You are a Master Content Composer for presentations. Needs no fluff, no corporate speak.
Your task is to take a complete narrative arc (a sequence of slide intents) and generate the *actual text* for each slide.

NARRATIVE COMPRESSION RULES (CRITICAL):
1. Write in punchlines, contrast statements, and short impactful phrases. NO paragraphs. No bullet vomit.
2. A slide must communicate ONE single defining idea perfectly.
3. Replace generic language (e.g. "We optimize clinical workflows") with hard reality ("Fragmented ownership breaks the workflow").
4. MAINTAIN NARRATIVE CONTINUITY: Reuse key phrases or entities precisely from one slide to the next to build a logical mental ladder. 

STORY-ROLE TO LAYOUT MAPPING:
Design behavior is driven by the role of the slide:
- Hook -> minimal, bold, dominant
- Problem -> sharp, high contrast
- Tension -> fragmented, pressure
- Insight -> reveal-focused
- Solution -> structured clarity
- Impact -> stats-driven
- Closure -> strong, conclusive, visually resting.

OUTPUT FORMAT (STRICT JSON):
Return a JSON object with a key 'structured_slides', containing a list where each element matches the input array length.
Each element MUST contain:
- 'slide_id': integer (1 for the first slide, and so on)
- 'intent': A string that combines the original intent AND the mapped design behavior (e.g. "role: Problem, design behavior: sharp, high contrast, intent: stark_contrast")
- 'content': A dictionary containing the actual text. Use keys like "title", "punchline", "subtext", "metrics". These will be fed to a separate visual composition engine.

Do NOT output markdown. Output raw JSON only.
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
    """Generate the actual slide content based on the narrative arc."""
    if not state.narrative_arc:
        logger.error("[content_engine] No narrative_arc found in state. Run narrative_engine first.")
        raise ValueError("narrative_arc is missing.")

    logger.info(f"[content_engine] Generating slide content based on arc of length {len(state.narrative_arc)}")

    arc_json = json.dumps(state.narrative_arc, indent=2)

    user_prompt = f"""Topic: {state.topic}
Type: {state.presentation_type}
Audience: {state.audience}

Here is the approved Narrative Arc (Intents & Flow):
{arc_json}

Follow the Compression rules. Guarantee continuity from slide N to N+1 based on the 'transition_reason'.
Output the 'structured_slides' array EXACTLY matching the {len(state.narrative_arc)} slides described.
"""

    try:
        result = await call_llm_json(CONTENT_ENGINE_SYSTEM_PROMPT, user_prompt)
        structured_slides = result.get("structured_slides", [])
        
        if len(structured_slides) != len(state.narrative_arc):
            logger.warning("[content_engine] Slide count mismatch between arc and generated content! Recovering best-effort.")

        # Ensure intents are thoroughly set for dynamic composition engine
        for i, slide in enumerate(structured_slides):
            if i < len(state.narrative_arc):
                arc_slide = state.narrative_arc[i]
                role = arc_slide.get("role_in_story", "Context")
                behavior = extract_role_behavior(role)
                original_intent = arc_slide.get("intent", "")
                emotional_tone = arc_slide.get("emotional_tone", "neutral")
                
                # We package the story role, behavior, and intent into the "intent" field
                # because `dynamic_composition_engine.py` reads `slide_data.get("intent")` directly.
                combined_intent = f"Role: {role} | Behavior: {behavior} | Direct Intent: {original_intent}"
                slide["intent"] = combined_intent
                slide["role_in_story"] = role
                slide["emotional_tone"] = emotional_tone
                slide["type"] = "content_slide"
                
                # Also inject slide_id if missing
                slide["slide_id"] = i + 1

        # We must keep "slide_plan" for speaker notes and UI
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
        # Fallback missing for brevity, would want retry logic in production
        raise e
