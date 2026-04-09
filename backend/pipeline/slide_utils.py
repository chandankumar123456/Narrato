"""Shared utilities for slide content analysis.

Common helpers used across slide_evaluator.py and deck_consistency_optimizer.py.
"""

from __future__ import annotations

import html
import re

from models.presentation_state import PresentationState


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
    for sep in (": ", " — ", " - "):
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
    # \$? optional currency symbol, \d[\d,.]*(?:\.\d+)? numeric core, optional unit suffix.
    match = re.search(r"(\$?\d[\d,.]*(?:\.\d+)?\s?(?:%|x|X|k|K|m|M|b|B|mo|yr|yrs|years?)?)", raw)
    if not match:
        return "", raw, ""
    value = match.group(1).strip()
    label = (raw[:match.start()] + raw[match.end():]).strip(" :,-")
    if not label:
        label = "Key metric"
    return value, label, raw


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


def _render_hero(primary: str, supporting: list[str], slide_index: int) -> str:
    subtitle = supporting[0] if supporting else ""
    kicker_lines = supporting[1:] if len(supporting) > 1 else []
    kicker_html = "".join(f'<span class="kicker-line">{_esc(line)}</span>' for line in kicker_lines[:2])
    return (
        '<article class="layout-hero layout-hero--cover">'
        '<div class="layout-hero-inner layout-hero-inner--cover">'
        f'<div class="slide-kicker"><span class="kicker-line">Slide {slide_index + 1}</span>{kicker_html}</div>'
        f'{_render_title_display(primary, "slide-title-display--cover")}'
        f'<p class="slide-subtitle-hero slide-subtitle-hero--cover">{_esc(subtitle)}</p>'
        "</div></article>"
    )


def _render_problem(title: str, primary: str, supporting: list[str]) -> str:
    pillars = supporting[:3]
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
    return (
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


def _render_solution(title: str, primary: str, supporting: list[str]) -> str:
    bullets = "".join(
        '<li><span class="bullet-dot">●</span>'
        f'<span>{_esc(text)}</span></li>'
        for text in supporting
    )
    mini = "".join(f'<div class="mini-card">{_esc(text)}</div>' for text in supporting[:2])
    return (
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


def _render_metrics(title: str, primary: str, supporting: list[str], funnel_mode: bool) -> str:
    lines = [primary] + supporting
    parsed = [_parse_metric(line) for line in lines if line]
    if funnel_mode and len(parsed) >= 3:
        tiers = []
        tier_classes = ["tam", "sam", "som"]
        for idx, (value, label, raw) in enumerate(parsed[:3]):
            tier = tier_classes[idx]
            tiers.append(
                f'<article class="stat-funnel-tier stat-funnel-tier--{tier}">'
                f'<div class="stat-funnel-value">{_esc(value or raw)}</div>'
                f'<p class="stat-funnel-label">{_esc(label or raw)}</p>'
                f'<p class="stat-funnel-context">{_esc(raw)}</p>'
                "</article>"
            )
        return (
            '<section class="layout-stats layout-stats--funnel">'
            '<header class="section-head section-head--stats">'
            f'<h2 class="slide-title-section slide-title-section--stats">{_esc(title)}</h2>'
            "</header>"
            f'<div class="stats-funnel-stack">{"".join(tiers)}</div>'
            "</section>"
        )

    lead_value, lead_label, lead_raw = parsed[0] if parsed else ("", "", primary)
    support_cells = "".join(
        '<article class="stat-cell stat-cell--support">'
        f'<p class="stat-value stat-value--support">{_esc(value or raw)}</p>'
        f'<p class="stat-label">{_esc(label or raw)}</p>'
        f'<p class="stat-context">{_esc(raw)}</p>'
        "</article>"
        for value, label, raw in parsed[1:4]
    )
    return (
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


def _render_blocks(title: str, primary: str, supporting: list[str], bento: bool) -> str:
    if bento and supporting:
        stack = "".join(
            '<article class="card card--support card--bento-small">'
            f'<h3 class="card-headline">Block {idx + 1}</h3>'
            f'<p class="card-support">{_esc(text)}</p>'
            "</article>"
            for idx, text in enumerate(supporting[:3])
        )
        return (
            '<section class="layout-grid">'
            '<header class="section-head section-head--compact">'
            f'<h2 class="slide-title-section">{_esc(title)}</h2>'
            f'<p class="grid-intro-paragraph">{_esc(primary)}</p>'
            '</header><div class="grid-cards--bento">'
            '<article class="card card--focal card--bento-hero">'
            '<div class="accent-bar"></div>'
            f'<h3 class="card-headline">{_esc(primary)}</h3>'
            f'<p class="card-support">{_esc(supporting[1]) if len(supporting) > 1 else (_esc(supporting[0]) if supporting else _esc(title))}</p>'
            f'</article><div class="bento-stack">{stack}</div></div></section>'
        )

    support_cards = "".join(
        '<article class="card card--support">'
        f'<h3 class="card-headline">Block {idx + 1}</h3>'
        f'<p class="card-support">{_esc(text)}</p>'
        "</article>"
        for idx, text in enumerate(supporting[:3])
    )
    return (
        '<section class="layout-grid">'
        '<header class="section-head section-head--compact">'
        f'<h2 class="slide-title-section">{_esc(title)}</h2>'
        "</header>"
        '<div class="grid-cards">'
        '<article class="card card--focal">'
        '<div class="accent-bar"></div>'
        f'<h3 class="card-headline">{_esc(primary)}</h3>'
        f'<p class="card-support">{_esc(supporting[1]) if len(supporting) > 1 else (_esc(supporting[0]) if supporting else _esc(title))}</p>'
        f'</article>{support_cards}</div></section>'
    )


def _render_business(title: str, primary: str, supporting: list[str]) -> str:
    grouped = "".join(
        '<article class="mini-card">'
        f'<p class="slide-body-sm">{_esc(text)}</p>'
        "</article>"
        for text in supporting[:4]
    )
    return (
        '<section class="layout-split layout-split--asymmetric">'
        '<div class="split-left split-left--primary">'
        '<div class="accent-bar accent-bar--side"></div>'
        f'<h2 class="slide-title-section">{_esc(title)}</h2>'
        f'<p class="split-body-lead">{_esc(primary)}</p>'
        f'<p class="split-body-support">{_esc(supporting[0]) if supporting else _esc(title)}</p>'
        "</div>"
        '<div class="split-right split-right--secondary">'
        '<div class="split-visual"><div class="split-visual-inner">'
        f"{grouped}</div></div></div></section>"
    )


def _render_ask(title: str, primary: str, supporting: list[str]) -> str:
    details = "".join(f'<span class="kicker-line">{_esc(text)}</span>' for text in supporting)
    return (
        '<article class="layout-hero layout-hero--statement">'
        '<div class="layout-hero-inner">'
        f'<p class="slide-label">{_esc(title)}</p>'
        f'{_render_title_display(primary)}'
        f'<div class="slide-kicker">{details}</div>'
        '<div class="accent-bar accent-bar--bottom"></div>'
        "</div></article>"
    )


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

    archetype = _infer_archetype(intent, role, slide_index, total_slides)
    density = visual_plan.get("density")
    rhythm = {"high": "dense", "minimal": "airy"}.get(density, "standard")
    frame_attrs = {
        "data-rhythm": rhythm,
        "data-slide-intent": archetype,
        "data-layout": visual_plan.get("layout", "center_focus"),
        "data-slide-role": role,
    }

    if archetype == "hero":
        body = _render_hero(primary, supporting, slide_index)
        frame_attrs["data-hero-emphasis"] = "title_dominant"
    elif archetype == "problem":
        body = _render_problem(title, primary, supporting)
        frame_attrs["data-grid-layout"] = "pillars"
    elif archetype == "solution":
        body = _render_solution(title, primary, supporting)
    elif archetype == "metrics":
        funnel_mode = any(k in intent.lower() for k in ("market", "tam", "sam", "som"))
        body = _render_metrics(title, primary, supporting, funnel_mode=funnel_mode)
        frame_attrs["data-stats-layout"] = "funnel" if funnel_mode else "spotlight"
    elif archetype == "business":
        body = _render_business(title, primary, supporting)
    elif archetype == "ask":
        body = _render_ask(title, primary, supporting)
    else:
        body = _render_blocks(title, primary, supporting, bento=True)
        frame_attrs["data-grid-layout"] = "bento"

    attrs = " ".join(f'{k}="{_esc(v)}"' for k, v in frame_attrs.items() if v)
    index_html = f'<div class="slide-deck-index">{slide_index + 1:02d}</div>'
    html_markup = f'<article class="slide-frame" {attrs}>{body}{index_html}</article>'
    return {
        "html": html_markup,
        "css": "",
        "frame_attrs": frame_attrs,
        "archetype": archetype,
    }
