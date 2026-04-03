from models.presentation_state import PresentationState


def build_state(signals: dict, user_schema=None) -> PresentationState:
    """Build the initial ``PresentationState`` from parsed signals.

    When *user_schema* is provided the state is put into strict mode and
    structural parameters are derived from the schema instead of signals.
    """

    if user_schema is not None:
        schema_dict = user_schema if isinstance(user_schema, dict) else user_schema.model_dump()
        n_examples = schema_dict.get("examples_required", 0)
        # title + definition + N examples + summary
        strict_slide_count = max(5, 2 + n_examples + 1)
        return PresentationState(
            topic=schema_dict.get("topic") or signals.get("topic", "Unknown Topic"),
            presentation_type=signals.get("presentation_type", "educational"),
            slide_count=strict_slide_count,
            sections=None,
            tone=signals.get("tone") or "professional",
            audience=signals.get("audience"),
            examples_count=n_examples,
            image_preference=signals.get("image_preference", True),
            language=signals.get("language", "en"),
            user_schema=schema_dict,
            generation_mode="strict",
        )

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
        generation_mode="default",
    )