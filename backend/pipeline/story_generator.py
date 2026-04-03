from models.presentation_state import PresentationState
from services.llm_client import call_llm_json

NARRATIVE_TYPES = {
    "pitch": "problem-solution",
    "educational": "educational-journey",
    "report": "data-driven",
    "general": "problem-solution",
}

async def generate_story(state: PresentationState) -> PresentationState:
    narrative_type = NARRATIVE_TYPES.get(state.presentation_type, "problem-solution")

    system = "You are a master storyteller for presentations. Return only JSON."
    user = f"""
Create a narrative arc for a {state.presentation_type} presentation.
Topic: {state.topic}
Audience: {state.audience}
Tone: {state.tone}
Narrative type: {narrative_type}

Return JSON:
{{
  "narrative_type": "...",
  "key_message": "...",
  "hook": "...",
  "sections_flow": [
    {{"section": "intro", "purpose": "...", "emotion": "..."}}
  ],
  "call_to_action": "..."
}}
Sections must match: {state.sections or ["intro","problem","solution","benefits","conclusion"]}
"""
    try:
        story = await call_llm_json(system, user)
    except Exception:
        story = _default_story(state)

    return state.model_copy(update={"story": story})

def _default_story(state: PresentationState) -> dict:
    return {
        "narrative_type": "problem-solution",
        "key_message": f"Understanding {state.topic}",
        "hook": f"What do you know about {state.topic}?",
        "sections_flow": [
            {"section": s, "purpose": s.capitalize(), "emotion": "neutral"}
            for s in ["intro", "problem", "solution", "benefits", "conclusion"]
        ],
        "call_to_action": "Learn more"
    }