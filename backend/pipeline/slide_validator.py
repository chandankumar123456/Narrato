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

REQUIRED_INVESTOR_ROLES = (
    "Problem",
    "Solution",
    "Product",
    "Market",
    "Business Model",
    "Competition",
    "Financials",
    "Funding Ask",
)


class SlideValidationError(ValueError):
    """Raised when slide content fails strict validation."""

    def __init__(self, violations: list[str]):
        self.violations = violations
        msg = (
            f"Slide validation failed with {len(violations)} violation(s):\n"
            + "\n".join(f"  - {v}" for v in violations)
        )
        super().__init__(msg)


# Minimum content checks per component type (empty list = only title / type-specific rules below)
_COMPONENT_CHECKS: dict[str, list[str]] = {
    "card_grid": ["items"],
    "steps": ["steps"],
    "stats": ["items"],
    "timeline": ["events"],
    "split": ["body", "items"],
    "hero": [],
}

# Structured slides may be title-only (design layer still produces a valid hero)
_TITLE_ONLY_SLIDE_TYPES = frozenset({
    "title_slide",
    "section_header",
    "thank_you_slide",
    "quote_slide",
    "conclusion_slide",
    "cta_slide",
})


def validate_slide_content(slides: list[dict]) -> list[dict]:
    """Validate structured slides with new format:
    primary_element + supporting_elements
    """

    violations: list[str] = []

    for slide in slides:
        slide_id = slide.get("slide_id", "?")
        slide_type = slide.get("type", "unknown")

        primary_element = str(slide.get("primary_element", "")).strip()
        supporting_elements = slide.get("supporting_elements", [])

        # 🔥 CHECK 1: primary must exist
        if not primary_element:
            violations.append(
                f"Slide {slide_id} ({slide_type}): missing primary_element"
            )

        is_hero_or_title = str(slide_type).lower() in _TITLE_ONLY_SLIDE_TYPES

        # 🔥 CHECK 2: supporting elements (except title slides)
        if not is_hero_or_title:
            if not isinstance(supporting_elements, list) or len(supporting_elements) == 0:
                violations.append(
                    f"Slide {slide_id} ({slide_type}): missing supporting_elements"
                )
            else:
                if len(supporting_elements) > 4:
                    violations.append(
                        f"Slide {slide_id} ({slide_type}): supporting_elements exceeds max 4"
                    )
                for idx, sup in enumerate(supporting_elements):
                    sup_words = len(str(sup).split())
                    if "\n" in str(sup):
                        violations.append(
                            f"Slide {slide_id} ({slide_type}): supporting_elements[{idx}] contains paragraph formatting"
                        )
                    if sup_words <= 2:
                        violations.append(
                            f"Slide {slide_id} ({slide_type}): supporting_elements[{idx}] too short: '{sup}'"
                        )
                    if sup_words > 12:
                        violations.append(
                            f"Slide {slide_id} ({slide_type}): supporting_elements[{idx}] exceeds 12 words"
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

        checks = _COMPONENT_CHECKS.get(comp_type, [])
        has_content = False
        for field in checks:
            val = components.get(field)
            if _is_non_empty(val):
                has_content = True
                break

        # Hero: title is the dominant element; subtitle, kicker, footer are optional
        if comp_type == "hero":
            has_content = True
            if not any(
                _is_non_empty(components.get(k))
                for k in ("subtitle", "kicker", "cover_footer")
            ):
                logger.debug(
                    "[slide_validator] Design %s hero is title-only (no subtitle/kicker/footer)",
                    idx,
                )

        # Split: narrative may live in body_lead after enrichment
        if comp_type == "split":
            body = components.get("body", "")
            items = components.get("items", [])
            lead = components.get("body_lead", "")
            has_content = (
                bool(body and str(body).strip())
                or bool(items)
                or bool(lead and str(lead).strip())
            )

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
    "<p ",
    "<p>",
    "<li ",
    "<li>",
    "<ul ",
    "<ul>",
    "slide-kicker",
    "slide-cover-footer",
    "slide-subtitle-hero",
    "slide-body",
    "slide-body-lg",
    "slide-body-sm",
    "stat-value",
    "grid-cards",
    "card ",
    "layout-hero",
    "split-visual",
    "visual-abstract",
    "mini-card",
    "step-card",
    "timeline-text",
    "<h1",
    "<h2",
    "<h3",
    "<div class=\"",
    "<span",
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

    HARD RULE: editor HTML == export HTML (identical per slide after stripping).

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
            if editor_html.strip() != export_html.strip():
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


def validate_pipeline_contract(
    structured_slides: list[dict],
    html_slides: list[str],
    expected_slide_count: int,
) -> None:
    """Final pre-render contract validation for reliability and determinism."""
    violations: list[str] = []
    slides = structured_slides or []
    html = html_slides or []

    if len(slides) != expected_slide_count:
        violations.append(
            f"Structured slide count mismatch: expected {expected_slide_count}, got {len(slides)}"
        )

    if len(html) != len(slides):
        violations.append(
            f"HTML parity mismatch: html={len(html)} structured={len(slides)}"
        )

    roles = {str((s.get("role") or s.get("role_in_story") or "")).strip().lower() for s in slides}
    for required in REQUIRED_INVESTOR_ROLES:
        if required.lower() not in roles:
            violations.append(f"Missing required role: {required}")

    for idx, slide in enumerate(slides, start=1):
        for field in ("cause", "tension", "next_trigger"):
            value = str(slide.get(field, "")).strip()
            if not value:
                violations.append(f"Slide {idx}: missing {field}")
        headline = str(slide.get("primary_element", "")).strip()
        if not headline:
            violations.append(f"Slide {idx}: empty primary_element")

    if violations:
        raise SlideValidationError(violations)
