from models.presentation_state import PresentationState

def build_state(signals: dict) -> PresentationState:
    return PresentationState(
        topic=signals.get("topic", "Unknown Topic"),
        presentation_type=signals.get("presentation_type", "general"),
        slide_count=signals.get("slide_count") or 10,
        sections=signals.get("sections"),
        tone=signals.get("tone") or "professional",
        audience=signals.get("audience"),
        examples_count=signals.get("examples_count") or 2,
        image_preference=signals.get("image_preference", True),
        language=signals.get("language", "en"),
    )