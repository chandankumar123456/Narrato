"""Phase 5: Content Validator — NON-CORRECTIVE ASSERTION ONLY.

Validates that generated output matches the user schema EXACTLY.
Does NOT modify, truncate, or fix content.  If invalid → HARD ERROR.

This is the final safety net.  All constraint enforcement happens during
generation (strict_content_structurer).  The validator only ASSERTS.
"""

from __future__ import annotations

import logging

from models.presentation_state import PresentationState, MAX_WORDS_PER_FIELD

logger = logging.getLogger(__name__)


class ValidationError(RuntimeError):
    """Raised when strict-mode output fails validation checks."""


# ── Public entry point ────────────────────────────────────────────────

def validate_content(state: PresentationState) -> PresentationState:
    """Assert that *state.structured_slides* complies with *state.user_schema*.

    Returns the state with ``validation_status: "passed"`` in metadata when
    all checks pass.  Raises ``ValidationError`` on any violation — the
    validator NEVER modifies content.
    """
    schema = state.user_schema
    if not schema:
        return state

    errors = _run_checks(state)

    if errors:
        for err in errors:
            logger.error("VALIDATION FAILURE: %s", err)
        raise ValidationError(
            f"Strict validation failed with {len(errors)} error(s): "
            + "; ".join(errors)
        )

    return _set_validation_status(state, "passed")


# ── Validation checks ────────────────────────────────────────────────

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

    # 1. Slide count check — EXACT match required
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

    # 3. Field completeness check — every required field must be present and non-empty
    for s in example_slides:
        content = s.get("content", {})
        sid = s.get("slide_id", "?")
        for field in fields_required:
            val = content.get(field)
            if not val or (isinstance(val, str) and not val.strip()):
                errors.append(f"Slide {sid}: missing required field '{field}'")

    # 4. No extra keys in example slides (only 'name' + fields_required)
    allowed_keys = {"name"} | set(fields_required)
    for s in example_slides:
        content = s.get("content", {})
        sid = s.get("slide_id", "?")
        extra = set(content.keys()) - allowed_keys
        if extra:
            errors.append(f"Slide {sid}: unexpected extra keys {extra}")

    # 5. Forbidden content check — substring scan
    forbidden_lower = [f.lower() for f in forbidden]
    for s in slides:
        content = s.get("content", {})
        sid = s.get("slide_id", "?")
        text_blob = _content_to_text(content).lower()
        for term in forbidden_lower:
            if term in text_blob:
                errors.append(f"Slide {sid}: contains forbidden content '{term}'")

    # 6. Word count check on example fields
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


# ── Helpers ───────────────────────────────────────────────────────────

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
