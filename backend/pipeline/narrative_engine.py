import logging
import json
from models.presentation_state import PresentationState
from services.llm_client import call_llm_json

logger = logging.getLogger(__name__)

class NarrativeEngineError(Exception):
    pass

NARRATIVE_ROLES = [
    "Context", "Problem", "Tension", "Insight", "Solution", "Impact", "Closure"
]

NARRATIVE_ENGINE_SYSTEM_PROMPT = f"""You are a master Narrative Architect for presentations.
Your task is to design a complete story arc that emotionally and logically hooks the audience, taking them from the initial context all the way to a powerful closure.

You must design EXACTLY {{slide_count}} slides.
You must use the following Narrative Progression in order: {NARRATIVE_ROLES}. 
Since to total slide count may be different from 7, you must expand or contract the time spent in each phase naturally without breaking the sequential flow.

HARD CONSTRAINTS:
1. OUTPUT: Return a JSON object with a single key "slides", which is a list of exactly {{slide_count}} objects.
2. SLIDE INTENT DEFINITION: Each slide object MUST contain exactly these keys:
   - "intent": What layout or behavioral intent this slide serves (e.g. hook, problem_reveal, stark_contrast, solution_intro, data_proof).
   - "role_in_story": Must be one of the stages: Context, Problem, Tension, Insight, Solution, Impact, Closure.
   - "key_message": The single main idea of the slide (must be just ONE idea, not compounded).
   - "transition_reason": WHY this slide comes immediately after the previous one (For slide 1, just write "Start"). It MUST justify its existence logically.
   - "emotional_tone": The emotional weight of the slide (e.g. calm, urgent, grim, lightbulb, confident).
3. PACING: One idea per slide. Progressive reveal of information. Do not info-dump.
4. TRANSITION STRENGTH: The reasoning connecting slide N to N-1 must be unbreakable.

Output MUST be valid JSON only, without markdown wrapping or backticks.
"""

def validate_narrative_arc(slides: list, target_count: int) -> list:
    """Validate the strict rules of the narrative arc."""
    if len(slides) != target_count:
        logger.warning(f"Narrative arc mismatch: expected {target_count} slides, got {len(slides)}")
        # If length mismatches, we can pad or truncate, or raise to retry. For robustness, let LLM decide or just enforce it.
        # But failing hard means we might retry. Let's return False to retry at the caller level.
        raise NarrativeEngineError("Slide count mismatch")

    roles_seen = []
    for i, slide in enumerate(slides):
        required_keys = {"intent", "role_in_story", "key_message", "transition_reason", "emotional_tone"}
        if not required_keys.issubset(set(slide.keys())):
            raise NarrativeEngineError(f"Slide {i+1} is missing required keys.")
        roles_seen.append(slide.get("role_in_story", ""))

        # Check for meaningful transitions
        transition = slide.get("transition_reason", "")
        if i > 0 and len(str(transition).split()) < 3:
            # Reject weak reasoning or missing transitions
            raise NarrativeEngineError(f"Slide {i+1} has weak or missing transition reasoning: '{transition}'")

    # Justify ordering
    role_order_map = {r: i for i, r in enumerate(NARRATIVE_ROLES)}
    last_role_idx = -1
    for i, role in enumerate(roles_seen):
        if role in role_order_map:
            current_idx = role_order_map[role]
            if current_idx < last_role_idx:
                raise NarrativeEngineError(f"Narrative flow went backward at Slide {i+1}: from {NARRATIVE_ROLES[last_role_idx]} to {role}")
            last_role_idx = current_idx
            
    return slides


async def run_narrative_engine(state: PresentationState) -> PresentationState:
    """Generate the presentation's narrative arc mapping out slide intents."""
    # ── Skip narrative for investor mode ─────────────────────
    if getattr(state, "deck_mode", "general") == "investor":
        return state
    logger.info(f"[narrative_engine] Building story arc for {state.slide_count} slides...")

    system_prompt = NARRATIVE_ENGINE_SYSTEM_PROMPT.format(slide_count=state.slide_count)
    user_prompt = f"""Topic: {state.topic}
Type: {state.presentation_type}
Audience: {state.audience}
Tone: {state.tone}

Remember to design exactly {state.slide_count} slides following the narrative progression context -> closure.
Output strictly JSON.
"""

    max_retries = 2
    for attempt in range(max_retries):
        try:
            result = await call_llm_json(system_prompt, user_prompt)
            slides = result.get("slides", [])
            valid_slides = validate_narrative_arc(slides, state.slide_count)
            
            # Map valid slides to the state
            return state.model_copy(update={"narrative_arc": valid_slides})
            
        except NarrativeEngineError as e:
            logger.warning(f"[narrative_engine] Validation failed on attempt {attempt+1}: {e}")
        except Exception as e:
            logger.error(f"[narrative_engine] LLM generation failed: {e}")

    # Fallback if engine fails completely
    logger.error("[narrative_engine] Failed to generate a valid narrative arc. Falling back to simple linear arc.")
    fallback_arc = []
    for i in range(state.slide_count):
        role_idx = min(i * len(NARRATIVE_ROLES) // state.slide_count, len(NARRATIVE_ROLES) - 1)
        fallback_arc.append({
            "intent": "general",
            "role_in_story": NARRATIVE_ROLES[role_idx],
            "key_message": f"Core point {i+1} for {state.topic}",
            "transition_reason": "Moving to next point" if i > 0 else "Start",
            "emotional_tone": "neutral"
        })
    return state.model_copy(update={"narrative_arc": fallback_arc})
