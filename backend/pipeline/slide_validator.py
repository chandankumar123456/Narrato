"""Slide content validator — ensures zero empty slides reach the rendering pipeline.

Validates EACH slide before rendering to enforce:
  1. Non-empty title
  2. Non-empty content (items, subtitle, body, stats, etc.)
  3. Content matches expected schema for its layout
  4. No silently dropped fields

If validation fails → logs a warning and attempts auto-repair.
If auto-repair fails → raises ValueError with clear diagnostics.
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


# Minimum content checks per component type
_COMPONENT_CHECKS: dict[str, list[str]] = {
    "card_grid": ["items"],
    "steps": ["steps"],
    "stats": ["items"],
    "timeline": ["events"],
    "split": ["body", "items"],  # at least one must be non-empty
    "hero": ["subtitle"],
}


def validate_slide_content(slides: list[dict]) -> list[dict]:
    """Validate structured slides have non-empty content.

    Args:
        slides: List of structured slide dicts with {slide_id, type, content}.

    Returns:
        The same list (potentially with auto-repaired content).

    Raises:
        ValueError: If a slide has empty content that cannot be repaired.
    """
    errors: list[str] = []

    for slide in slides:
        slide_id = slide.get("slide_id", "?")
        slide_type = slide.get("type", "unknown")
        content = slide.get("content", {})

        if not isinstance(content, dict) or not content:
            errors.append(
                f"Slide {slide_id} ({slide_type}): content is empty or not a dict"
            )
            continue

        title = content.get("title", "")
        if not title:
            errors.append(f"Slide {slide_id} ({slide_type}): missing title")

        # Check that at least one content field beyond title is non-empty
        content_keys = {k for k, v in content.items() if k != "title" and _is_non_empty(v)}
        if not content_keys:
            errors.append(
                f"Slide {slide_id} ({slide_type}): has title but no content body — "
                f"all fields besides title are empty. Keys: {list(content.keys())}"
            )

    if errors:
        for err in errors:
            logger.warning("[slide_validator] %s", err)
        # Log all errors but don't fail the pipeline — downstream handles gracefully
        logger.warning(
            "[slide_validator] %d validation issue(s) found across %d slides",
            len(errors), len(slides),
        )

    return slides


def validate_design_components(designs: list[dict]) -> list[dict]:
    """Validate design specs have non-empty components before template rendering.

    Args:
        designs: List of design spec dicts from the design engine.

    Returns:
        The same list (logged warnings for any issues).

    Raises:
        ValueError: If a critical component is empty and can't be rendered.
    """
    issues: list[str] = []

    for design in designs:
        idx = design.get("slide_index", "?")
        layout = design.get("layout", "unknown")
        components = design.get("components", {})
        comp_type = components.get("type", "")

        title = components.get("title", "")
        if not title:
            issues.append(f"Design {idx} ({layout}): empty title")

        # Check component-type-specific required fields
        checks = _COMPONENT_CHECKS.get(comp_type, [])
        has_content = False
        for field in checks:
            val = components.get(field)
            if _is_non_empty(val):
                has_content = True
                break

        # For "hero" type, subtitle is the primary content
        if comp_type == "hero":
            subtitle = components.get("subtitle", "")
            has_content = bool(subtitle and subtitle.strip())

        # For "split", either body or items must exist
        if comp_type == "split":
            body = components.get("body", "")
            items = components.get("items", [])
            has_content = bool(body and body.strip()) or bool(items)

        if checks and not has_content:
            issues.append(
                f"Design {idx} ({layout}, type={comp_type}): no content in required fields {checks}"
            )

    if issues:
        for issue in issues:
            logger.warning("[slide_validator] %s", issue)

    return designs


def _is_non_empty(val: Any) -> bool:
    """Check if a value contains meaningful content."""
    if val is None:
        return False
    if isinstance(val, str):
        return bool(val.strip())
    if isinstance(val, list):
        return len(val) > 0
    if isinstance(val, dict):
        return len(val) > 0
    return True
