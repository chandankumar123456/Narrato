"""Shared utilities for slide content analysis.

Common helpers used across slide_evaluator.py and deck_consistency_optimizer.py.
"""

from __future__ import annotations

import html
import re

from models.presentation_state import PresentationState

MAX_KICKER_LINES = 2
MAX_SUPPORT_CARDS = 3
SAFE_FRAME_ATTR_KEYS = {
    "data-rhythm",
    "data-slide-intent",
    "data-layout",
    "data-slide-role",
    "data-hero-emphasis",
    "data-grid-layout",
    "data-stats-layout",
    "data-variant",
}
TITLE_SEPARATORS = (": ", " — ", " - ")
METRIC_PATTERN = r"(\$?\d[\d,.]*(?:\.\d+)?\s?(?:%|x|X|k|K|m|M|b|B|mo|yr|yrs|years?)?)"


def flatten_content(content: dict) -> str:
    """Flatten a slide content dict into a human-readable string."""
    parts: list[str] = []
    for key, val in content.items():
        if isinstance(val, str):
            parts.append(f"{key}: {val}")
        elif isinstance(val, list):
            for item in val:
                if isinstance(item, str):
                    parts.append(f"- {item}")
                elif isinstance(item, dict):
                    parts.append(
                        "- " + ", ".join(f"{k}: {v}" for k, v in item.items())
                    )
        elif isinstance(val, dict):
            parts.append(
                f"{key}: " + ", ".join(f"{k}: {v}" for k, v in val.items())
            )
    return "\n".join(parts)


def extract_bullets(content: dict) -> list[str]:
    """Extract descriptive text items from slide content for quality checks.

    Only extracts descriptions and body-like text — NOT short label/heading fields
    which are expected to be concise.
    """
    bullets: list[str] = []
    for key, val in content.items():
        if key in ("title", "section_title", "presenter", "contact", "attribution",
                    "icon", "stat", "stat_label", "source", "year", "cta_text",
                    "label", "left_label", "right_label"):
            continue  # Skip non-bullet / heading fields
        if isinstance(val, str) and key in ("body", "subtitle", "description",
                                             "tagline", "context", "result",
                                             "takeaway", "key_takeaway", "message",
                                             "quote", "caption"):
            if val.strip():
                bullets.append(val)
        elif isinstance(val, list):
            for item in val:
                if isinstance(item, str):
                    if item.strip():
                        bullets.append(item)
                elif isinstance(item, dict):
                    # Only extract description fields from list items —
                    # labels are short headings, not descriptive bullets
                    desc = item.get("description", "")
                    if desc and desc.strip():
                        bullets.append(desc)
    return bullets


def find_plan_entry(state: PresentationState, slide_id: int) -> dict:
    """Find the slide plan entry matching a slide_id."""
    if state.slide_plan:
        for entry in state.slide_plan:
            if entry.get("slide_id") == slide_id:
                return entry
    return {"section": "unknown", "purpose": "unknown", "type": "unknown", "slide_id": slide_id}


def _esc(text: str) -> str:
    return html.escape(str(text)) if text is not None else ""


def _clean_lines(items: list[str] | None) -> list[str]:
    if not isinstance(items, list):
        return []
    return [str(x).strip() for x in items if str(x).strip()]


def _split_title(primary: str) -> tuple[str, str]:
    text = (primary or "").strip()
    if not text:
        return "Untitled", ""
    for sep in TITLE_SEPARATORS:
        if sep in text:
            a, b = text.split(sep, 1)
            return a.strip(), b.strip()
    words = text.split()
    if len(words) <= 7:
        return text, ""
    pivot = max(4, len(words) // 2)
    return " ".join(words[:pivot]), " ".join(words[pivot:])


def _render_title_display(primary: str, extra_class: str = "") -> str:
    line_1, line_2 = _split_title(primary)
    cls = f"slide-title-display {extra_class}".strip()
    if line_2:
        return (
            f'<h1 class="{cls}">'
            f'<span class="title-line title-line--primary">{_esc(line_1)}</span>'
            f'<span class="title-line title-line--secondary">{_esc(line_2)}</span>'
            f"</h1>"
        )
    return (
        f'<h1 class="{cls}">'
        f'<span class="title-line title-line--primary">{_esc(line_1)}</span>'
        "</h1>"
    )


def _parse_metric(text: str) -> tuple[str, str, str]:
    raw = (text or "").strip()
    if not raw:
        return "", "", ""
    # Pattern parts:
    #   \$?                    → optional currency symbol
    #   \d[\d,.]*(?:\.\d+)?    → numeric core with separators/optional decimal
    #   \s?(%|x|k|m|b|...)     → optional investor-style unit suffix
    match = re.search(METRIC_PATTERN, raw)
    if not match:
        return "", raw, ""
    value = match.group(1).strip()
    left = raw[:match.start()].strip()
    right = raw[match.end():].strip()
    label = f"{left} {right}".strip(" :,-")
    if not label:
        label = "Key metric"
    return value, label, raw


def _word_count(text: str) -> int:
    return len((text or "").split())


def _is_long_text(text: str, word_limit: int = 12, char_limit: int = 88) -> bool:
    return _word_count(text) >= word_limit or len((text or "").strip()) >= char_limit


def _metric_count(lines: list[str]) -> int:
    return sum(1 for line in lines if _parse_metric(line)[0])


def _has_metrics(lines: list[str]) -> bool:
    return _metric_count(lines) > 0


def _support_text(supporting: list[str], index: int, fallback: str = "") -> str:
    if 0 <= index < len(supporting):
        return supporting[index]
    return fallback


def _card_support_text(supporting: list[str], title: str) -> str:
    return _support_text(supporting, 1, _support_text(supporting, 0, title))


def _dominant_primary_metric(primary: str, supporting: list[str]) -> bool:
    primary_value, _, _ = _parse_metric(primary)
    if not primary_value:
        return False
    return _metric_count([primary] + supporting) <= 2 or _word_count(primary) <= 7


def _latest_variant_for_archetype(archetype: str, variant_history: dict) -> str:
    variants = variant_history.get(archetype, []) if isinstance(variant_history, dict) else []
    if not isinstance(variants, list) or not variants:
        return ""
    return str(variants[-1]).strip()


def _prefer_variant(candidate: str, avoid_variant: str) -> bool:
    return not avoid_variant or candidate != avoid_variant


def _infer_archetype(intent: str, role: str, slide_index: int, total_slides: int) -> str:
    intent_l = (intent or "").lower()
    role_l = (role or "").lower()

    if slide_index == 0:
        return "hero"
    if slide_index == total_slides - 1 and any(k in intent_l for k in ("ask", "cta", "fund", "raise", "close")):
        return "ask"

    keyword_map = [
        ("hero", "hero"),
        ("cover", "hero"),
        ("problem", "problem"),
        ("pain", "problem"),
        ("challenge", "problem"),
        ("solution", "solution"),
        ("mechanism", "solution"),
        ("stat", "metrics"),
        ("metric", "metrics"),
        ("traction", "metrics"),
        ("proof", "metrics"),
        ("market", "metrics"),
        ("blocks", "blocks"),
        ("grid", "blocks"),
        ("pillar", "blocks"),
        ("business", "business"),
        ("revenue", "business"),
        ("model", "business"),
        ("ask", "ask"),
        ("cta", "ask"),
        ("fundraise", "ask"),
    ]
    for needle, archetype in keyword_map:
        if needle in intent_l:
            return archetype

    role_map = {
        "hook": "hero",
        "context": "blocks",
        "problem": "problem",
        "tension": "problem",
        "explanation": "solution",
        "solution": "solution",
        "application": "business",
        "proof": "metrics",
        "closure": "ask",
    }
    return role_map.get(role_l, "blocks")


def _render_hero(primary: str, supporting: list[str], slide_index: int, avoid_variant: str = "") -> tuple[str, str]:
    subtitle = supporting[0] if supporting else ""
    kicker_lines = supporting[1:] if len(supporting) > 1 else []
    kicker_html = "".join(f'<span class="kicker-line">{_esc(line)}</span>' for line in kicker_lines[:MAX_KICKER_LINES])
    support_count = len(supporting)
    long_primary = _is_long_text(primary, word_limit=12, char_limit=86)

    if (long_primary or support_count >= 3) and _prefer_variant("editorial_left", avoid_variant):
        variant = "editorial_left"
        html_markup = (
            '<article class="layout-hero layout-hero--editorial">'
            '<div class="layout-hero-inner">'
            '<div class="accent-bar accent-bar--side"></div>'
            f'<div class="slide-kicker"><span class="kicker-line">Slide {slide_index + 1:02d}</span>{kicker_html}</div>'
            f"{_render_title_display(primary)}"
            f'<p class="slide-subtitle-hero">{_esc(subtitle)}</p>'
            "</div></article>"
        )
        return html_markup, variant

    if support_count <= 1 and _prefer_variant("statement_center", avoid_variant):
        variant = "statement_center"
        html_markup = (
            '<article class="layout-hero layout-hero--statement">'
            '<div class="layout-hero-inner">'
            f'<p class="slide-label">Slide {slide_index + 1:02d}</p>'
            f"{_render_title_display(primary)}"
            f'<p class="slide-subtitle-hero">{_esc(subtitle)}</p>'
            '<div class="accent-bar accent-bar--bottom"></div>'
            "</div></article>"
        )
        return html_markup, variant

    if _prefer_variant("cover_center", avoid_variant):
        variant = "cover_center"
        html_markup = (
            '<article class="layout-hero layout-hero--cover">'
            '<div class="layout-hero-inner layout-hero-inner--cover">'
            f'<div class="slide-kicker"><span class="kicker-line">Slide {slide_index + 1:02d}</span>{kicker_html}</div>'
            f'{_render_title_display(primary, "slide-title-display--cover")}'
            f'<p class="slide-subtitle-hero slide-subtitle-hero--cover">{_esc(subtitle)}</p>'
            "</div></article>"
        )
        return html_markup, variant

    variant = "cover_center"
    html_markup = (
        '<article class="layout-hero layout-hero--cover">'
        '<div class="layout-hero-inner layout-hero-inner--cover">'
        f'<div class="slide-kicker"><span class="kicker-line">Slide {slide_index + 1:02d}</span>{kicker_html}</div>'
        f'{_render_title_display(primary, "slide-title-display--cover")}'
        f'<p class="slide-subtitle-hero slide-subtitle-hero--cover">{_esc(subtitle)}</p>'
        "</div></article>"
    )
    return html_markup, variant


def _render_problem(
    title: str,
    primary: str,
    supporting: list[str],
    slide_index: int,
    density: str,
    avoid_variant: str = "",
) -> tuple[str, str]:
    pillars = supporting[:]
    has_metric = _has_metrics([primary] + supporting)
    support_count = len(supporting)
    long_primary = _is_long_text(primary, word_limit=14, char_limit=92)
    dominant_metric = _dominant_primary_metric(primary, supporting)
    value, label, _ = _parse_metric(primary)
    stat_value = value or "Problem"
    stat_label = label or primary
    stat_context = supporting[1] if len(supporting) > 1 else (supporting[0] if supporting else primary)
    cards = "".join(
        '<article class="card card--problem-pillar">'
        f'<h3 class="card-headline">Issue {idx + 1}</h3>'
        f'<p class="card-support">{_esc(text)}</p>'
        "</article>"
        for idx, text in enumerate(pillars)
    )

    if dominant_metric and support_count <= 2 and _prefer_variant("stat_focus_column", avoid_variant):
        variant = "stat_focus_column"
        html_markup = (
            '<section class="layout-stats layout-stats--spotlight">'
            '<header class="section-head section-head--stats">'
            f'<h2 class="slide-title-section slide-title-section--stats">{_esc(title)}</h2>'
            "</header>"
            '<article class="stat-cell stat-cell--lead stat-spotlight-block">'
            f'<p class="stat-value">{_esc(stat_value)}</p>'
            f'<p class="stat-label">{_esc(stat_label)}</p>'
            f'<p class="stat-context">{_esc(stat_context)}</p>'
            "</article>"
            f'<p class="slide-body-lg">{_esc(primary)}</p>'
            "</section>"
        )
        return html_markup, variant

    if (long_primary or support_count == 1) and _prefer_variant("split_pressure", avoid_variant):
        variant = "split_pressure"
        cards_html = "".join(
            '<article class="mini-card">'
            f'<p class="slide-body-sm">{_esc(text)}</p>'
            "</article>"
            for text in supporting
        )
        html_markup = (
            '<section class="layout-split layout-split--asymmetric">'
            '<div class="split-left split-left--primary">'
            '<div class="accent-bar accent-bar--side"></div>'
            f'<h2 class="slide-title-section">{_esc(title)}</h2>'
            f'<p class="split-body-lead">{_esc(primary)}</p>'
            '<div class="problem-stat-row">'
            f'<span class="problem-stat-value">{_esc(stat_value)}</span>'
            f'<span class="problem-stat-label">{_esc(stat_label)}</span>'
            "</div></div>"
            '<div class="split-right split-right--secondary">'
            '<div class="split-visual"><div class="split-visual-inner">'
            f"{cards_html}</div></div></div></section>"
        )
        return html_markup, variant

    if support_count >= 3 and _prefer_variant("grid_pillars", avoid_variant):
        variant = "grid_pillars"
        html_markup = (
            '<section class="layout-grid layout-grid--problem">'
            '<header class="section-head section-head--problem">'
            '<div class="accent-bar accent-bar--problem"></div>'
            f'<h2 class="slide-title-section slide-title-section--problem">{_esc(title)}</h2>'
            "</header>"
            '<div class="problem-stat-row">'
            f'<span class="problem-stat-value">{_esc(stat_value)}</span>'
            f'<span class="problem-stat-label">{_esc(stat_label)}</span>'
            f'<span class="problem-stat-context">{_esc(stat_context)}</span>'
            "</div>"
            f'<p class="grid-intro-paragraph">{_esc(primary)}</p>'
            f'<div class="grid-cards grid-cards--problem-pillars">{cards}</div>'
            "</section>"
        )
        return html_markup, variant

    if has_metric and _prefer_variant("stat_focus_column", avoid_variant):
        variant = "stat_focus_column"
        html_markup = (
            '<section class="layout-stats layout-stats--spotlight">'
            '<header class="section-head section-head--stats">'
            f'<h2 class="slide-title-section slide-title-section--stats">{_esc(title)}</h2>'
            "</header>"
            '<article class="stat-cell stat-cell--lead stat-spotlight-block">'
            f'<p class="stat-value">{_esc(stat_value)}</p>'
            f'<p class="stat-label">{_esc(stat_label)}</p>'
            f'<p class="stat-context">{_esc(stat_context)}</p>'
            "</article>"
            f'<p class="slide-body-lg">{_esc(primary)}</p>'
            "</section>"
        )
        return html_markup, variant

    variant = "grid_pillars"
    html_markup = (
        '<section class="layout-grid layout-grid--problem">'
        '<header class="section-head section-head--problem">'
        '<div class="accent-bar accent-bar--problem"></div>'
        f'<h2 class="slide-title-section slide-title-section--problem">{_esc(title)}</h2>'
        "</header>"
        '<div class="problem-stat-row">'
        f'<span class="problem-stat-value">{_esc(stat_value)}</span>'
        f'<span class="problem-stat-label">{_esc(stat_label)}</span>'
        f'<span class="problem-stat-context">{_esc(stat_context)}</span>'
        "</div>"
        f'<p class="grid-intro-paragraph">{_esc(primary)}</p>'
        f'<div class="grid-cards grid-cards--problem-pillars">{cards}</div>'
        "</section>"
    )
    return html_markup, variant


def _render_solution(
    title: str,
    primary: str,
    supporting: list[str],
    slide_index: int,
    density: str,
    avoid_variant: str = "",
) -> tuple[str, str]:
    support_count = len(supporting)
    long_primary = _is_long_text(primary, word_limit=14, char_limit=96)
    dominant_metric = _dominant_primary_metric(primary, supporting)
    bullets = "".join(
        '<li><span class="bullet-dot">●</span>'
        f'<span>{_esc(text)}</span></li>'
        for text in supporting
    )
    mini = "".join(f'<div class="mini-card">{_esc(text)}</div>' for text in supporting[:2])
    if support_count >= 3 and not long_primary and _prefer_variant("steps_flow", avoid_variant):
        variant = "steps_flow"
        rows = []
        for idx, text in enumerate(supporting):
            card_cls = "step-card step-card--focal" if idx == 0 else "step-card step-card--support"
            num_cls = "step-num step-num--lg" if idx == 0 else "step-num step-num--sm"
            connector = '<div class="step-connector"></div>' if idx < len(supporting) - 1 else ""
            rows.append(
                '<div class="step-row">'
                f'<article class="{card_cls}"><div class="{num_cls}">{idx + 1}</div>'
                f'<p class="step-text-lead">{_esc(text)}</p></article>{connector}</div>'
            )
        html_markup = (
            '<section class="layout-steps">'
            '<header class="section-head section-head--compact">'
            f'<h2 class="slide-title-section">{_esc(title)}</h2>'
            f'<p class="slide-body">{_esc(primary)}</p>'
            "</header>"
            f'<div class="steps-stack">{"".join(rows)}</div>'
            "</section>"
        )
        return html_markup, variant

    if (dominant_metric or _has_metrics([primary] + supporting)) and _prefer_variant("split_metric_solution", avoid_variant):
        variant = "split_metric_solution"
        metric_cards = []
        for line in [primary] + supporting:
            value, label, raw = _parse_metric(line)
            if not value:
                continue
            metric_cards.append(
                '<article class="mini-card">'
                f'<p class="stat-value stat-value--support">{_esc(value)}</p>'
                f'<p class="stat-label">{_esc(label or raw)}</p>'
                "</article>"
            )
        if metric_cards:
            html_markup = (
                '<section class="layout-split layout-split--asymmetric">'
                '<div class="split-left split-left--primary">'
                '<div class="accent-bar accent-bar--side"></div>'
                f'<h2 class="slide-title-section">{_esc(title)}</h2>'
                f'<p class="split-body-lead">{_esc(primary)}</p>'
                f'<ul class="split-bullet-list">{bullets}</ul>'
                "</div>"
                '<div class="split-right split-right--secondary">'
                '<div class="split-visual"><div class="split-visual-inner">'
                f'{"".join(metric_cards[:3])}</div></div></div></section>'
            )
            return html_markup, variant

    if (long_primary or support_count <= 2 or density == "high") and _prefer_variant("split_narrative", avoid_variant):
        variant = "split_narrative"
        html_markup = (
            '<section class="layout-split layout-split--asymmetric">'
            '<div class="split-left split-left--primary">'
            '<div class="accent-bar accent-bar--side"></div>'
            f'<h2 class="slide-title-section">{_esc(title)}</h2>'
            f'<p class="split-body-lead">{_esc(primary)}</p>'
            f'<ul class="split-bullet-list">{bullets}</ul>'
            "</div>"
            '<div class="split-right split-right--secondary">'
            '<div class="split-visual"><div class="split-visual-inner">'
            f'{mini}<div class="visual-abstract" aria-hidden="true"></div>'
            "</div></div></div></section>"
        )
        return html_markup, variant

    variant = "split_narrative"
    html_markup = (
        '<section class="layout-split layout-split--asymmetric">'
        '<div class="split-left split-left--primary">'
        '<div class="accent-bar accent-bar--side"></div>'
        f'<h2 class="slide-title-section">{_esc(title)}</h2>'
        f'<p class="split-body-lead">{_esc(primary)}</p>'
        f'<ul class="split-bullet-list">{bullets}</ul>'
        "</div>"
        '<div class="split-right split-right--secondary">'
        '<div class="split-visual"><div class="split-visual-inner">'
        f'{mini}<div class="visual-abstract" aria-hidden="true"></div>'
        "</div></div></div></section>"
    )
    return html_markup, variant


def _render_metrics(
    title: str,
    primary: str,
    supporting: list[str],
    funnel_mode: bool,
    slide_index: int,
    density: str,
    avoid_variant: str = "",
) -> tuple[str, str]:
    lines = [primary] + supporting
    parsed = [_parse_metric(line) for line in lines if line]
    metric_count = sum(1 for value, _, _ in parsed if value)
    dominant_metric = _dominant_primary_metric(primary, supporting)

    if funnel_mode and len(parsed) >= 3 and _prefer_variant("funnel", avoid_variant):
        tiers = []
        tier_classes = ["tam", "sam", "som"]
        for tier, (value, label, raw) in zip(tier_classes, parsed[:3]):
            tiers.append(
                f'<article class="stat-funnel-tier stat-funnel-tier--{tier}">'
                f'<div class="stat-funnel-value">{_esc(value or raw)}</div>'
                f'<p class="stat-funnel-label">{_esc(label or raw)}</p>'
                f'<p class="stat-funnel-context">{_esc(raw)}</p>'
                "</article>"
            )
        variant = "funnel"
        html_markup = (
            '<section class="layout-stats layout-stats--funnel">'
            '<header class="section-head section-head--stats">'
            f'<h2 class="slide-title-section slide-title-section--stats">{_esc(title)}</h2>'
            "</header>"
            f'<div class="stats-funnel-stack">{"".join(tiers)}</div>'
            "</section>"
        )
        return html_markup, variant

    if dominant_metric and _prefer_variant("single_spotlight", avoid_variant):
        value, label, raw = parsed[0] if parsed else ("", "", primary)
        variant = "single_spotlight"
        html_markup = (
            '<article class="layout-hero layout-hero--statement">'
            '<div class="layout-hero-inner">'
            f'<p class="slide-label">{_esc(title)}</p>'
            f'<h1 class="slide-title-display"><span class="title-line title-line--primary">{_esc(value or raw)}</span></h1>'
            f'<p class="slide-subtitle-hero">{_esc(label or raw)}</p>'
            f'<div class="slide-kicker">{"".join(f"<span class=\"kicker-line\">{_esc(s)}</span>" for s in supporting[:MAX_KICKER_LINES])}</div>'
            "</div></article>"
        )
        return html_markup, variant

    if metric_count >= 3 and not _is_long_text(primary, word_limit=12, char_limit=84) and _prefer_variant("grid_kpi", avoid_variant):
        lead_value, lead_label, lead_raw = parsed[0] if parsed else ("", "", primary)
        support_cells = "".join(
            '<article class="stat-cell">'
            f'<p class="stat-value stat-value--support">{_esc(value or raw)}</p>'
            f'<p class="stat-label">{_esc(label or raw)}</p>'
            "</article>"
            for value, label, raw in parsed[1:5]
        )
        variant = "grid_kpi"
        html_markup = (
            '<section class="layout-stats">'
            '<header class="section-head section-head--stats">'
            f'<h2 class="slide-title-section slide-title-section--stats">{_esc(title)}</h2>'
            "</header>"
            '<div class="stats-grid">'
            '<article class="stat-cell stat-cell--lead">'
            f'<p class="stat-value">{_esc(lead_value or lead_raw)}</p>'
            f'<p class="stat-label">{_esc(lead_label or lead_raw)}</p>'
            "</article>"
            f"{support_cells}</div></section>"
        )
        return html_markup, variant

    if (metric_count <= 1 and _is_long_text(primary, word_limit=8, char_limit=60)) and _prefer_variant("single_spotlight", avoid_variant):
        value, label, raw = parsed[0] if parsed else ("", "", primary)
        variant = "single_spotlight"
        html_markup = (
            '<article class="layout-hero layout-hero--statement">'
            '<div class="layout-hero-inner">'
            f'<p class="slide-label">{_esc(title)}</p>'
            f'<h1 class="slide-title-display"><span class="title-line title-line--primary">{_esc(value or raw)}</span></h1>'
            f'<p class="slide-subtitle-hero">{_esc(label or raw)}</p>'
            f'<div class="slide-kicker">{"".join(f"<span class=\"kicker-line\">{_esc(s)}</span>" for s in supporting)}</div>'
            "</div></article>"
        )
        return html_markup, variant

    if _prefer_variant("spotlight", avoid_variant):
        lead_value, lead_label, lead_raw = parsed[0] if parsed else ("", "", primary)
        support_cells = "".join(
            '<article class="stat-cell stat-cell--support">'
            f'<p class="stat-value stat-value--support">{_esc(value or raw)}</p>'
            f'<p class="stat-label">{_esc(label or raw)}</p>'
            f'<p class="stat-context">{_esc(raw)}</p>'
            "</article>"
            for value, label, raw in parsed[1:4]
        )
        variant = "spotlight"
        html_markup = (
            '<section class="layout-stats layout-stats--spotlight">'
            '<header class="section-head section-head--stats">'
            f'<h2 class="slide-title-section slide-title-section--stats">{_esc(title)}</h2>'
            "</header>"
            '<article class="stat-cell stat-cell--lead stat-spotlight-block">'
            f'<p class="stat-value">{_esc(lead_value or lead_raw)}</p>'
            f'<p class="stat-label">{_esc(lead_label or lead_raw)}</p>'
            f'<p class="stat-context">{_esc(lead_raw)}</p>'
            '</article><div class="stats-support-row">'
            f"{support_cells}</div></section>"
        )
        return html_markup, variant

    lead_value, lead_label, lead_raw = parsed[0] if parsed else ("", "", primary)
    support_cells = "".join(
        '<article class="stat-cell stat-cell--support">'
        f'<p class="stat-value stat-value--support">{_esc(value or raw)}</p>'
        f'<p class="stat-label">{_esc(label or raw)}</p>'
        f'<p class="stat-context">{_esc(raw)}</p>'
        "</article>"
        for value, label, raw in parsed[1:4]
    )
    variant = "spotlight"
    html_markup = (
        '<section class="layout-stats layout-stats--spotlight">'
        '<header class="section-head section-head--stats">'
        f'<h2 class="slide-title-section slide-title-section--stats">{_esc(title)}</h2>'
        "</header>"
        '<article class="stat-cell stat-cell--lead stat-spotlight-block">'
        f'<p class="stat-value">{_esc(lead_value or lead_raw)}</p>'
        f'<p class="stat-label">{_esc(lead_label or lead_raw)}</p>'
        f'<p class="stat-context">{_esc(lead_raw)}</p>'
        '</article><div class="stats-support-row">'
        f"{support_cells}</div></section>"
    )
    return html_markup, variant


def _render_blocks(
    title: str,
    primary: str,
    supporting: list[str],
    bento: bool,
    slide_index: int,
    density: str,
    avoid_variant: str = "",
) -> tuple[str, str]:
    support_count = len(supporting)
    long_primary = _is_long_text(primary, word_limit=14, char_limit=96)
    if bento and supporting and (support_count == 1 or long_primary or density == "minimal") and _prefer_variant("bento_asymmetric", avoid_variant):
        stack = "".join(
            '<article class="card card--support card--bento-small">'
            f'<h3 class="card-headline">Block {idx + 1}</h3>'
            f'<p class="card-support">{_esc(text)}</p>'
            "</article>"
            for idx, text in enumerate(supporting[:MAX_SUPPORT_CARDS])
        )
        variant = "bento_asymmetric"
        html_markup = (
            '<section class="layout-grid">'
            '<header class="section-head section-head--compact">'
            f'<h2 class="slide-title-section">{_esc(title)}</h2>'
            f'<p class="grid-intro-paragraph">{_esc(primary)}</p>'
            '</header><div class="grid-cards--bento">'
            '<article class="card card--focal card--bento-hero">'
            '<div class="accent-bar"></div>'
            f'<h3 class="card-headline">{_esc(primary)}</h3>'
            f'<p class="card-support">{_esc(_card_support_text(supporting, title))}</p>'
            f'</article><div class="bento-stack">{stack}</div></div></section>'
        )
        return html_markup, variant

    if support_count >= 3 and density == "high" and _prefer_variant("rail_blocks", avoid_variant):
        rows = []
        for idx, text in enumerate(supporting):
            card_variant = "step-card--focal" if idx == 0 else "step-card--support"
            num_variant = "step-num--lg" if idx == 0 else "step-num--sm"
            rows.append(
                '<div class="step-row">'
                f'<article class="step-card {card_variant}">'
                f'<div class="step-num {num_variant}">{idx + 1}</div>'
                f'<p class="step-text-lead">{_esc(text)}</p>'
                "</article></div>"
            )
        variant = "rail_blocks"
        html_markup = (
            '<section class="layout-steps">'
            '<header class="section-head section-head--compact">'
            f'<h2 class="slide-title-section">{_esc(title)}</h2>'
            f'<p class="slide-body">{_esc(primary)}</p>'
            '</header><div class="steps-stack steps-stack--rail">'
            f'{"".join(rows)}</div></section>'
        )
        return html_markup, variant

    if support_count >= 3 and _prefer_variant("grid_balanced", avoid_variant):
        support_cards = "".join(
            '<article class="card card--support">'
            f'<h3 class="card-headline">Block {idx + 1}</h3>'
            f'<p class="card-support">{_esc(text)}</p>'
            "</article>"
            for idx, text in enumerate(supporting[:MAX_SUPPORT_CARDS])
        )
        variant = "grid_balanced"
        html_markup = (
            '<section class="layout-grid">'
            '<header class="section-head section-head--compact">'
            f'<h2 class="slide-title-section">{_esc(title)}</h2>'
            "</header>"
            '<div class="grid-cards">'
            '<article class="card card--focal">'
            '<div class="accent-bar"></div>'
            f'<h3 class="card-headline">{_esc(primary)}</h3>'
            f'<p class="card-support">{_esc(_card_support_text(supporting, title))}</p>'
            f'</article>{support_cards}</div></section>'
        )
        return html_markup, variant

    support_cards = "".join(
        '<article class="card card--support">'
        f'<h3 class="card-headline">Block {idx + 1}</h3>'
        f'<p class="card-support">{_esc(text)}</p>'
        "</article>"
        for idx, text in enumerate(supporting[:MAX_SUPPORT_CARDS])
    )
    variant = "grid_balanced"
    html_markup = (
        '<section class="layout-grid">'
        '<header class="section-head section-head--compact">'
        f'<h2 class="slide-title-section">{_esc(title)}</h2>'
        "</header>"
        '<div class="grid-cards">'
        '<article class="card card--focal">'
        '<div class="accent-bar"></div>'
        f'<h3 class="card-headline">{_esc(primary)}</h3>'
        f'<p class="card-support">{_esc(_card_support_text(supporting, title))}</p>'
        f'</article>{support_cards}</div></section>'
    )
    return html_markup, variant


def _render_business(
    title: str,
    primary: str,
    supporting: list[str],
    slide_index: int,
    density: str,
    avoid_variant: str = "",
) -> tuple[str, str]:
    metrics_in_lines = _metric_count([primary] + supporting)
    support_count = len(supporting)
    long_primary = _is_long_text(primary, word_limit=14, char_limit=98)
    dominant_metric = _dominant_primary_metric(primary, supporting)
    if (dominant_metric or metrics_in_lines >= 2) and _prefer_variant("kpi_panel", avoid_variant):
        metric_rows = []
        for line in [primary] + supporting:
            value, label, raw = _parse_metric(line)
            if not value:
                continue
            metric_rows.append(
                '<article class="mini-card">'
                f'<p class="stat-value stat-value--support">{_esc(value)}</p>'
                f'<p class="stat-label">{_esc(label or raw)}</p>'
                "</article>"
            )
        variant = "kpi_panel"
        html_markup = (
            '<section class="layout-split layout-split--asymmetric">'
            '<div class="split-left split-left--primary">'
            '<div class="accent-bar accent-bar--side"></div>'
            f'<h2 class="slide-title-section">{_esc(title)}</h2>'
            f'<p class="split-body-lead">{_esc(primary)}</p>'
            f'<p class="split-body-support">{_esc(_support_text(supporting, 0, title))}</p>'
            "</div>"
            '<div class="split-right split-right--secondary">'
            '<div class="split-visual"><div class="split-visual-inner">'
            f'{"".join(metric_rows[:4])}</div></div></div></section>'
        )
        return html_markup, variant

    if (long_primary or support_count == 1) and _prefer_variant("split_brief", avoid_variant):
        grouped = "".join(
            '<article class="mini-card">'
            f'<p class="slide-body-sm">{_esc(text)}</p>'
            "</article>"
            for text in supporting[:4]
        )
        variant = "split_brief"
        html_markup = (
            '<section class="layout-split layout-split--asymmetric">'
            '<div class="split-left split-left--primary">'
            '<div class="accent-bar accent-bar--side"></div>'
            f'<h2 class="slide-title-section">{_esc(title)}</h2>'
            f'<p class="split-body-lead">{_esc(primary)}</p>'
            f'<p class="split-body-support">{_esc(_support_text(supporting, 0, title))}</p>'
            "</div>"
            '<div class="split-right split-right--secondary">'
            '<div class="split-visual"><div class="split-visual-inner">'
            f"{grouped}</div></div></div></section>"
        )
        return html_markup, variant

    if support_count >= 3 and _prefer_variant("asymmetric_cards", avoid_variant):
        support_cards = "".join(
            '<article class="card card--support">'
            f'<h3 class="card-headline">Business Driver {idx + 1}</h3>'
            f'<p class="card-support">{_esc(text)}</p>'
            "</article>"
            for idx, text in enumerate(supporting)
        )
        variant = "asymmetric_cards"
        html_markup = (
            '<section class="layout-grid">'
            '<header class="section-head section-head--compact">'
            f'<h2 class="slide-title-section">{_esc(title)}</h2>'
            f'<p class="grid-intro-paragraph">{_esc(primary)}</p>'
            '</header><div class="grid-cards">'
            '<article class="card card--focal">'
            '<div class="accent-bar"></div>'
            f'<h3 class="card-headline">{_esc(primary)}</h3>'
            f'<p class="card-support">{_esc(_support_text(supporting, 0, title))}</p>'
            f'</article>{support_cards}</div></section>'
        )
        return html_markup, variant

    grouped = "".join(
        '<article class="mini-card">'
        f'<p class="slide-body-sm">{_esc(text)}</p>'
        "</article>"
        for text in supporting[:4]
    )
    variant = "split_brief"
    html_markup = (
        '<section class="layout-split layout-split--asymmetric">'
        '<div class="split-left split-left--primary">'
        '<div class="accent-bar accent-bar--side"></div>'
        f'<h2 class="slide-title-section">{_esc(title)}</h2>'
        f'<p class="split-body-lead">{_esc(primary)}</p>'
        f'<p class="split-body-support">{_esc(_support_text(supporting, 0, title))}</p>'
        "</div>"
        '<div class="split-right split-right--secondary">'
        '<div class="split-visual"><div class="split-visual-inner">'
        f"{grouped}</div></div></div></section>"
    )
    return html_markup, variant


def _render_ask(title: str, primary: str, supporting: list[str], slide_index: int, avoid_variant: str = "") -> tuple[str, str]:
    if _has_metrics([primary] + supporting) and _prefer_variant("metric_cta", avoid_variant):
        primary_value, primary_label, raw = _parse_metric(primary)
        allocation = "".join(
            '<article class="stat-cell stat-cell--support">'
            f'<p class="stat-value stat-value--support">{_esc(v or r)}</p>'
            f'<p class="stat-label">{_esc(l or r)}</p>'
            "</article>"
            for v, l, r in [_parse_metric(line) for line in supporting]
            if v
        )
        variant = "metric_cta"
        html_markup = (
            '<section class="layout-stats layout-stats--spotlight">'
            '<header class="section-head section-head--stats">'
            f'<h2 class="slide-title-section slide-title-section--stats">{_esc(title)}</h2>'
            "</header>"
            '<article class="stat-cell stat-cell--lead stat-spotlight-block">'
            f'<p class="stat-value">{_esc(primary_value or raw)}</p>'
            f'<p class="stat-label">{_esc(primary_label or raw)}</p>'
            "</article>"
            f'<div class="stats-support-row">{allocation}</div>'
            '<div class="card"><p class="card-headline">Investment Ask</p><p class="card-support">Request Access</p></div>'
            "</section>"
        )
        return html_markup, variant

    if len(supporting) >= 2 and _prefer_variant("split_cta", avoid_variant):
        detail_cards = "".join(
            '<article class="mini-card">'
            f'<p class="slide-body-sm">{_esc(text)}</p>'
            "</article>"
            for text in supporting[:MAX_KICKER_LINES]
        )
        variant = "split_cta"
        html_markup = (
            '<section class="layout-split layout-split--asymmetric">'
            '<div class="split-left split-left--primary">'
            f'<p class="slide-label">{_esc(title)}</p>'
            f"{_render_title_display(primary)}"
            '<div class="accent-bar accent-bar--bottom"></div>'
            "</div>"
            '<div class="split-right split-right--secondary">'
            '<div class="split-visual"><div class="split-visual-inner">'
            f'{detail_cards}<div class="card"><p class="card-headline">Request Data Room</p></div>'
            "</div></div></div></section>"
        )
        return html_markup, variant

    details = "".join(f'<span class="kicker-line">{_esc(text)}</span>' for text in supporting[:MAX_KICKER_LINES])
    variant = "statement"
    html_markup = (
        '<article class="layout-hero layout-hero--statement">'
        '<div class="layout-hero-inner">'
        f'<p class="slide-label">{_esc(title)} · Slide {slide_index + 1:02d}</p>'
        f'{_render_title_display(primary)}'
        f'<div class="slide-kicker">{details}</div>'
        '<div class="accent-bar accent-bar--bottom"></div>'
        "</div></article>"
    )
    return html_markup, variant


def compose_slide_markup(
    preprocessing_result: dict,
    visual_plan: dict,
    slide_index: int,
    total_slides: int,
) -> dict:
    title = str(preprocessing_result.get("title") or "").strip() or "Untitled"
    primary = str(preprocessing_result.get("primary_element") or title).strip()
    supporting = _clean_lines(preprocessing_result.get("supporting_elements", []))
    intent = str(preprocessing_result.get("intent", ""))
    role = str(visual_plan.get("narrative_role", ""))
    density = str(visual_plan.get("density", "medium"))

    archetype = _infer_archetype(intent, role, slide_index, total_slides)
    recent_archetype_variants = visual_plan.get("recent_archetype_variants", {})
    avoid_variant = _latest_variant_for_archetype(archetype, recent_archetype_variants)
    rhythm = {"high": "dense", "minimal": "airy"}.get(density, "standard")
    frame_attrs = {
        "data-rhythm": rhythm,
        "data-slide-intent": archetype,
        "data-layout": visual_plan.get("layout", "center_focus"),
        "data-slide-role": role,
    }
    variant = "default"

    if archetype == "hero":
        body, variant = _render_hero(primary, supporting, slide_index, avoid_variant=avoid_variant)
        frame_attrs["data-hero-emphasis"] = "title_dominant"
    elif archetype == "problem":
        body, variant = _render_problem(title, primary, supporting, slide_index, density, avoid_variant=avoid_variant)
        frame_attrs["data-grid-layout"] = "pillars"
    elif archetype == "solution":
        body, variant = _render_solution(title, primary, supporting, slide_index, density, avoid_variant=avoid_variant)
    elif archetype == "metrics":
        funnel_mode = any(k in intent.lower() for k in ("market", "tam", "sam", "som"))
        body, variant = _render_metrics(
            title,
            primary,
            supporting,
            funnel_mode=funnel_mode,
            slide_index=slide_index,
            density=density,
            avoid_variant=avoid_variant,
        )
        frame_attrs["data-stats-layout"] = "funnel" if variant == "funnel" else "spotlight"
    elif archetype == "business":
        body, variant = _render_business(title, primary, supporting, slide_index, density, avoid_variant=avoid_variant)
    elif archetype == "ask":
        body, variant = _render_ask(title, primary, supporting, slide_index, avoid_variant=avoid_variant)
    else:
        body, variant = _render_blocks(
            title,
            primary,
            supporting,
            bento=True,
            slide_index=slide_index,
            density=density,
            avoid_variant=avoid_variant,
        )
        frame_attrs["data-grid-layout"] = "bento" if variant == "bento_asymmetric" else "grid"
    frame_attrs["data-variant"] = variant

    attrs = " ".join(
        f'{k}="{_esc(v)}"'
        for k, v in frame_attrs.items()
        if v and k in SAFE_FRAME_ATTR_KEYS
    )
    index_html = f'<div class="slide-deck-index">{slide_index + 1:02d}</div>'
    html_markup = f'<article class="slide-frame" {attrs}>{body}{index_html}</article>'
    return {
        "html": html_markup,
        "css": "",
        "frame_attrs": frame_attrs,
        "archetype": archetype,
        "variant": variant,
    }
