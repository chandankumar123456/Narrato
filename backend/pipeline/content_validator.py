"""Phase 5: Content Validator.

Post-generation validation loop that checks output against the user schema
and triggers selective regeneration on failure (up to MAX_RETRIES times).
"""

from __future__ import annotations

import logging

from models.presentation_state import PresentationState

logger = logging.getLogger(__name__)

MAX_RETRIES = 2
MAX_WORDS_PER_FIELD = 12


async def validate_content(state: PresentationState) -> PresentationState:
    """Validate structured_slides against user_schema.

    Returns the state unchanged when all checks pass.  When failures are
    detected the failing example slides are regenerated up to MAX_RETRIES
    times.  After exhausting retries the best-effort output is returned
    with a validation_status flag in metadata.
    """
    schema = state.user_schema
    if not schema:
        return state

    errors = _run_checks(state)

    if not errors:
        return _set_validation_status(state, "passed")

    for attempt in range(1, MAX_RETRIES + 1):
        logger.warning(
            "Validation attempt %d/%d - %d error(s): %s",
            attempt, MAX_RETRIES, len(errors),
            "; ".join(errors),
        )
        state = await _regenerate_failing_slides(state, errors)
        errors = _run_checks(state)
        if not errors:
            return _set_validation_status(state, "passed")

    logger.error("Validation failed after %d retries: %s", MAX_RETRIES, errors)
    return _set_validation_status(state, "partial", errors)


def _run_checks(state: PresentationState) -> list[str]:
    """Return a list of human-readable error strings (empty means pass)."""
    errors: list[str] = []
    schema = state.user_schema
    if not schema:
        return errors

    slides = state.structured_slides or []
    n_examples = schema.get("examples_required", 0)
    fields_required: list[str] = schema.get("fields_required", [])
    forbidden: list[str] = schema.get("forbidden_content", [])

    # 1. Slide count check
    expected_count = 2 + n_examples + 1
    if len(slides) != expected_count:
        errors.append(
            f"Slide count mismatch: expected {expected_count}, got {len(slides)}"
        )

    # 2. Example count check
    example_slides = [s for s in slides if s.get("type") == "example_detail_slide"]
    if len(example_slides) != n_examples:
        errors.append(
            f"Example count mismatch: expected {n_examples}, got {len(example_slides)}"
        )

    # 3. Field completeness check
    for s in example_slides:
        content = s.get("content", {})
        sid = s.get("slide_id", "?")
        for field in fields_required:
            val = content.get(field)
            if not val or (isinstance(val, str) and not val.strip()):
                errors.append(f"Slide {sid}: missing required field '{field}'")

    # 4. Forbidden content check
    forbidden_lower = [f.lower() for f in forbidden]
    for s in slides:
        content = s.get("content", {})
        sid = s.get("slide_id", "?")
        text_blob = _content_to_text(content).lower()
        for term in forbidden_lower:
            if term in text_blob:
                errors.append(f"Slide {sid}: contains forbidden content '{term}'")

    # 5. Word count check on example fields
    for s in example_slides:
        content = s.get("content", {})
        sid = s.get("slide_id", "?")
        for field in fields_required:
            val = content.get(field, "")
            if isinstance(val, str) and len(val.split()) > MAX_WORDS_PER_FIELD:
                errors.append(
                    f"Slide {sid}: field '{field}' exceeds {MAX_WORDS_PER_FIELD} words"
                )

    return errors


def _content_to_text(content: dict) -> str:
    """Flatten a slide content dict into a single string for scanning."""
    parts: list[str] = []
    for v in content.values():
        if isinstance(v, str):
            parts.append(v)
        elif isinstance(v, list):
            for item in v:
                if isinstance(item, str):
                    parts.append(item)
                elif isinstance(item, dict):
                    parts.extend(str(iv) for iv in item.values())
        elif isinstance(v, dict):
            parts.extend(str(iv) for iv in v.values())
    return " ".join(parts)


async def _regenerate_failing_slides(
    state: PresentationState, errors: list[str]
) -> PresentationState:
    """Re-generate only the example slides that have validation errors."""
    from pipeline.strict_content_structurer import _generate_example

    schema = state.user_schema or {}
    fields_required = schema.get("fields_required", [])
    forbidden = schema.get("forbidden_content", [])
    topic = schema.get("topic", state.topic)
    n_examples = schema.get("examples_required", 0)

    forbidden_clause = ""
    if forbidden:
        forbidden_clause = (
            "\n\nFORBIDDEN - you MUST NOT include ANY of the following: "
            + ", ".join(forbidden) + "."
        )

    # Identify failing slide IDs from error messages
    failing_ids: set[int] = set()
    for err in errors:
        if err.startswith("Slide "):
            try:
                sid = int(err.split(":")[0].replace("Slide ", ""))
                failing_ids.add(sid)
            except (ValueError, IndexError):
                pass

    if not failing_ids:
        return state

    updated_slides = list(state.structured_slides or [])
    for i, slide in enumerate(updated_slides):
        if slide.get("slide_id") not in failing_ids:
            continue
        if slide.get("type") != "example_detail_slide":
            continue

        # Determine example number from slide plan
        example_num = 1
        count = 0
        for s in (state.slide_plan or []):
            if s.get("type") == "example_detail_slide":
                count += 1
                if s.get("slide_id") == slide.get("slide_id"):
                    example_num = count
                    break

        new_content = await _generate_example(
            topic, example_num, n_examples, fields_required,
            state.tone, forbidden_clause,
        )
        # Enforce word-count truncation at this layer too
        for field in fields_required:
            val = new_content.get(field, "")
            if isinstance(val, str):
                words = val.split()
                if len(words) > MAX_WORDS_PER_FIELD:
                    new_content[field] = " ".join(words[:MAX_WORDS_PER_FIELD])

        updated_slides[i] = {**slide, "content": new_content}

    return state.model_copy(update={"structured_slides": updated_slides})


def _set_validation_status(
    state: PresentationState,
    status: str,
    errors: list[str] | None = None,
) -> PresentationState:
    """Attach validation metadata to the state."""
    meta = dict(state.metadata or {})
    meta["validation_status"] = status
    if errors:
        meta["validation_errors"] = errors
    return state.model_copy(update={"metadata": meta})
