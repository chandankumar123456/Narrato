from models.presentation_state import PresentationState


class StrictSchemaError(ValueError):
    """Raised when a strict-mode schema is missing required fields."""


def build_state(signals: dict, user_schema=None) -> PresentationState:
    """Build the initial ``PresentationState`` from parsed signals.

    When *user_schema* is provided the state is put into strict mode and
    structural parameters are derived ONLY from the schema — no signals
    fallback.  Missing required schema fields cause a hard failure.
    """

    if user_schema is not None:
        schema_dict = user_schema if isinstance(user_schema, dict) else user_schema.model_dump()

        # ── Hard schema authority: fail fast if required fields are missing ──
        topic = schema_dict.get("topic")
        if not topic:
            raise StrictSchemaError("Strict mode requires 'topic' in user_schema")

        n_examples = schema_dict.get("examples_required", 0)
        if n_examples <= 0:
            raise StrictSchemaError("Strict mode requires examples_required > 0")

        fields_required = schema_dict.get("fields_required", [])
        if not fields_required:
            raise StrictSchemaError("Strict mode requires at least one field in fields_required")

        # EXACT slide count — no min/max guards
        exact_slide_count = 2 + n_examples + 1  # title + definition + N examples + summary

        return PresentationState(
            topic=topic,
            presentation_type="educational",
            slide_count=exact_slide_count,
            sections=None,
            presentation_mode=signals.get("presentation_mode", "academic"),
            tone=signals.get("tone") or "professional",
            audience=signals.get("audience"),
            examples_count=n_examples,
            language=signals.get("language", "en"),
            user_schema=schema_dict,
            generation_mode="strict",
        )

    return PresentationState(
        topic=signals.get("topic", "Unknown Topic"),
        presentation_type=signals.get("presentation_type", "general"),
        slide_count=signals.get("slide_count") or 10,
        sections=signals.get("sections"),
        presentation_mode=signals.get("presentation_mode", "generic"),
        tone=signals.get("tone") or "professional",
        audience=signals.get("audience"),
        examples_count=signals.get("examples_count") or 2,
        language=signals.get("language", "en"),
        generation_mode="default",
    )
