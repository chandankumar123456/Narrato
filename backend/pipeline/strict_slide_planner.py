"""Phase 3: Strict Slide Planner.

Produces a deterministic slide plan driven entirely by the user schema.
No section-weight allocation, no agenda/CTA extras — only:

    title → definition → example × N → summary
"""

from __future__ import annotations

from models.presentation_state import PresentationState


def plan_slides_strict(state: PresentationState) -> PresentationState:
    """Create an exact slide plan from *state.user_schema*.

    Raises ``ValueError`` if the schema is missing or has no examples.
    """

    schema = state.user_schema
    if not schema:
        raise ValueError("plan_slides_strict requires user_schema on state")

    n_examples = schema.get("examples_required", 0)
    if n_examples <= 0:
        raise ValueError("examples_required must be > 0 for strict mode")

    slides: list[dict] = []
    sid = 0

    # 1. Title slide
    slides.append({
        "slide_id": sid,
        "section": "intro",
        "purpose": "Title slide",
        "type": "title_slide",
    })
    sid += 1

    # 2. Definition slide (rendered as feature_slide)
    slides.append({
        "slide_id": sid,
        "section": "intro",
        "purpose": "Definition of topic",
        "type": "feature_slide",
    })
    sid += 1

    # 3. One slide per example
    for i in range(n_examples):
        slides.append({
            "slide_id": sid,
            "section": "examples",
            "purpose": f"Example {i + 1}",
            "type": "example_detail_slide",
        })
        sid += 1

    # 4. Summary slide (rendered as conclusion_slide)
    slides.append({
        "slide_id": sid,
        "section": "conclusion",
        "purpose": "Summary of all examples",
        "type": "conclusion_slide",
    })

    return state.model_copy(update={"slide_plan": slides})
