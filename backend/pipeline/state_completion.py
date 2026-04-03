from models.presentation_state import PresentationState
from services.llm_client import call_llm_json

async def complete_state(state: PresentationState) -> PresentationState:
    system = "You complete missing fields in a presentation config. Return only JSON."
    user = f"""
Topic: {state.topic}
Type: {state.presentation_type}
Audience: {state.audience or "unknown"}
Tone: {state.tone}

Fill in any missing values and return JSON with:
- sections: list of 4-6 section names
- tone: refined tone
- include_stats: bool
- examples_count: int
- visual_style: "modern" | "corporate" | "minimal"
- theme: same as visual_style
"""
    try:
        result = await call_llm_json(system, user)
        return state.model_copy(update=result)
    except Exception:
        return state  # fallback: use state as-is