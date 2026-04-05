"""Slide content validator — ensures zero empty slides reach the rendering pipeline.

Validates EACH slide before rendering to enforce:
  1. Non-empty title
  2. Non-empty content (items, subtitle, body, stats, etc.)
  3. Content matches expected schema for its layout
  4. No silently dropped fields

STRICT MODE: Raises SlideValidationError on any violation.
No auto-repair. No silent continuation. Pipeline MUST stop on violations.
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


class SlideValidationError(ValueError):
    """Raised when slide content fails strict validation."""

    def __init__(self, violations: list[str]):
        self.violations = violations
        msg = (
            f"Slide validation failed with {len(violations)} violation(s):\n"
            + "\n".join(f"  - {v}" for v in violations)
        )
        super().__init__(msg)


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

    STRICT: Raises SlideValidationError if ANY slide has:
      - missing or empty content dict
      - missing title
      - no content fields beyond title

    Args:
        slides: List of structured slide dicts with {slide_id, type, content}.

    Returns:
        The same list (unmodified) if all slides pass validation.

    Raises:
        SlideValidationError: If any slide fails validation.
    """
    violations: list[str] = []

    for slide in slides:
        slide_id = slide.get("slide_id", "?")
        slide_type = slide.get("type", "unknown")
        content = slide.get("content", {})

        if not isinstance(content, dict) or not content:
            violations.append(
                f"Slide {slide_id} ({slide_type}): content is empty or not a dict"
            )
            continue

        title = content.get("title", "")
        if not title:
            violations.append(f"Slide {slide_id} ({slide_type}): missing title")

        # Check that at least one content field beyond title is non-empty
        content_keys = {k for k, v in content.items() if k != "title" and _is_non_empty(v)}
        if not content_keys:
            violations.append(
                f"Slide {slide_id} ({slide_type}): has title but no content body — "
                f"all fields besides title are empty. Keys: {list(content.keys())}"
            )

    if violations:
        for v in violations:
            logger.error("[slide_validator] VIOLATION: %s", v)
        raise SlideValidationError(violations)

    logger.info("[slide_validator] All %d slides passed strict validation", len(slides))
    return slides


def validate_design_components(designs: list[dict]) -> list[dict]:
    """Validate design specs have non-empty components before template rendering.

    STRICT: Raises SlideValidationError if any critical component is empty.

    Args:
        designs: List of design spec dicts from the design engine.

    Returns:
        The same list (unmodified) if all designs pass validation.

    Raises:
        SlideValidationError: If a critical component is empty.
    """
    violations: list[str] = []

    for design in designs:
        idx = design.get("slide_index", "?")
        layout = design.get("layout", "unknown")
        components = design.get("components", {})
        comp_type = components.get("type", "")

        title = components.get("title", "")
        if not title:
            violations.append(f"Design {idx} ({layout}): empty title")

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
            violations.append(
                f"Design {idx} ({layout}, type={comp_type}): no content in required fields {checks}"
            )

    if violations:
        for v in violations:
            logger.error("[slide_validator] DESIGN VIOLATION: %s", v)
        raise SlideValidationError(violations)

    logger.info("[slide_validator] All %d designs passed strict validation", len(designs))
    return designs


class SlideRenderError(ValueError):
    """Raised when rendered HTML fails content verification."""

    def __init__(self, violations: list[str]):
        self.violations = violations
        msg = (
            f"Slide render validation failed with {len(violations)} violation(s):\n"
            + "\n".join(f"  - {v}" for v in violations)
        )
        super().__init__(msg)


# HTML content markers that indicate real rendered content (beyond just a title)
_CONTENT_MARKERS = (
    "<p ",    # paragraph text
    "<p>",
    "<li ",   # list items
    "<li>",
    "<ul ",   # lists
    "<ul>",
    "text-5xl",   # stat values (large numbers)
    "text-7xl",   # dominant stat values
    "rounded-2xl",  # cards/panels
    "rounded-3xl",  # cards/panels
    "grid-cols",    # grid layouts
)


def validate_rendered_html(html_slides: list[str]) -> list[str]:
    """Validate that rendered HTML contains actual visible content, not just titles.

    STRICT: Raises SlideRenderError if ANY slide renders as title-only
    (missing body text, bullet points, cards, stats, or other content).

    This is the final gate before export — ensures what the user sees
    in the editor is what gets exported.

    Args:
        html_slides: List of complete HTML strings from the template engine.

    Returns:
        The same list (unmodified) if all slides pass validation.

    Raises:
        SlideRenderError: If any slide has only a title and no body content.
    """
    violations: list[str] = []

    for idx, slide_html in enumerate(html_slides):
        slide_num = idx + 1

        if not slide_html or not slide_html.strip():
            violations.append(f"Slide {slide_num}: HTML is empty")
            continue

        # Check for any content marker beyond just the title
        has_content = any(marker in slide_html for marker in _CONTENT_MARKERS)

        if not has_content:
            violations.append(
                f"Slide {slide_num}: rendered HTML contains only title — "
                f"no paragraphs, lists, cards, or structured content found"
            )

    if violations:
        for v in violations:
            logger.error("[slide_validator] RENDER VIOLATION: %s", v)
        raise SlideRenderError(violations)

    logger.info("[slide_validator] All %d rendered slides passed HTML validation",
                len(html_slides))
    return html_slides


def validate_export_parity(editor_html_slides: list[str], export_html_slides: list[str]) -> None:
    """Verify that export uses the EXACT same HTML as the editor.

    HARD RULE: editor HTML == export HTML (byte-level identical per slide).

    Args:
        editor_html_slides: HTML strings used in the editor iframes.
        export_html_slides: HTML strings passed to the export/rendering engine.

    Raises:
        SlideRenderError: If any slide's export HTML differs from its editor HTML.
    """
    violations: list[str] = []

    if len(editor_html_slides) != len(export_html_slides):
        violations.append(
            f"Slide count mismatch: editor has {len(editor_html_slides)}, "
            f"export has {len(export_html_slides)}"
        )
    else:
        for idx, (editor_html, export_html) in enumerate(
            zip(editor_html_slides, export_html_slides)
        ):
            if editor_html != export_html:
                violations.append(
                    f"Slide {idx + 1}: export HTML differs from editor HTML "
                    f"(editor len={len(editor_html)}, export len={len(export_html)})"
                )

    if violations:
        for v in violations:
            logger.error("[slide_validator] EXPORT PARITY VIOLATION: %s", v)
        raise SlideRenderError(violations)

    logger.info("[slide_validator] Export parity verified for %d slides",
                len(editor_html_slides))


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
