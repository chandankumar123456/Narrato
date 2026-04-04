"""
Stage 1: Design Engine

Decides layout, structure, components, and theme for each slide.
Enforces deck-level consistency before processing individual slides.

Available layouts:
  - hero_center
  - grid_cards
  - split_left_text_right_visual
  - step_flow
  - stats_blocks
  - timeline_flow

Themes:
  - dark_modern (default)
  - minimal_light
  - bold_gradient
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)

# ── Layout mapping: slide intent → layout ────────────────────────────
INTENT_LAYOUT_MAP: dict[str, str] = {
    "problem": "grid_cards",
    "solution": "split_left_text_right_visual",
    "product": "step_flow",
    "market": "stats_blocks",
    "vision": "hero_center",
    "timeline": "timeline_flow",
    # Existing Narrato slide types → visual layouts
    "title_slide": "hero_center",
    "section_header": "hero_center",
    "agenda_slide": "grid_cards",
    "problem_slide": "grid_cards",
    "stats_slide": "stats_blocks",
    "feature_slide": "step_flow",
    "comparison_slide": "grid_cards",
    "timeline_slide": "timeline_flow",
    "example_slide": "split_left_text_right_visual",
    "example_detail_slide": "split_left_text_right_visual",
    "quote_slide": "hero_center",
    "image_slide": "split_left_text_right_visual",
    "conclusion_slide": "hero_center",
    "cta_slide": "hero_center",
    "thank_you_slide": "hero_center",
}

VALID_LAYOUTS = frozenset([
    "hero_center",
    "grid_cards",
    "split_left_text_right_visual",
    "step_flow",
    "stats_blocks",
    "timeline_flow",
])

# ── Theme definitions ────────────────────────────────────────────────

VISUAL_THEMES: dict[str, dict[str, str]] = {
    "dark_modern": {
        "background": "bg-gradient-to-br from-black to-gray-900",
        "text_primary": "text-white",
        "text_secondary": "text-gray-300",
        "card_bg": "bg-white/10 backdrop-blur-md",
        "card_border": "border border-white/20",
        "accent": "text-purple-400",
        "accent_bg": "bg-purple-500/20",
        "font_heading": "font-sans",
        "font_body": "font-sans",
        "stat_value_color": "text-purple-400",
        "step_number_bg": "bg-purple-500",
        "divider": "border-white/20",
    },
    "minimal_light": {
        "background": "bg-white",
        "text_primary": "text-gray-900",
        "text_secondary": "text-gray-600",
        "card_bg": "bg-gray-50",
        "card_border": "border border-gray-200",
        "accent": "text-indigo-600",
        "accent_bg": "bg-indigo-50",
        "font_heading": "font-sans",
        "font_body": "font-sans",
        "stat_value_color": "text-indigo-600",
        "step_number_bg": "bg-indigo-600",
        "divider": "border-gray-200",
    },
    "bold_gradient": {
        "background": "bg-gradient-to-br from-indigo-900 via-purple-900 to-pink-800",
        "text_primary": "text-white",
        "text_secondary": "text-pink-200",
        "card_bg": "bg-white/15 backdrop-blur-lg",
        "card_border": "border border-white/30",
        "accent": "text-pink-300",
        "accent_bg": "bg-pink-500/20",
        "font_heading": "font-sans",
        "font_body": "font-sans",
        "stat_value_color": "text-pink-300",
        "step_number_bg": "bg-pink-500",
        "divider": "border-white/30",
    },
}

DEFAULT_THEME = "dark_modern"

MAX_ITEMS = 4
MAX_BULLET_WORDS = 15


def select_layout(slide_data: dict) -> str:
    """Select layout based on slide_type or intent."""
    slide_type = slide_data.get("type", "") or ""
    intent = slide_data.get("intent", "") or ""

    # Try intent first, then slide_type
    layout = INTENT_LAYOUT_MAP.get(intent.lower())
    if not layout:
        layout = INTENT_LAYOUT_MAP.get(slide_type.lower())
    if not layout:
        layout = "hero_center"

    return layout


def _extract_items(content: dict) -> list[dict]:
    """Extract structured items from slide content."""
    items = []

    # Try bullet_points / bullets
    for key in ("bullet_points", "bullets", "items", "features"):
        raw = content.get(key)
        if isinstance(raw, list):
            for item in raw[:MAX_ITEMS]:
                if isinstance(item, str):
                    items.append({"text": _truncate(item)})
                elif isinstance(item, dict):
                    items.append({
                        k: _truncate(str(v)) for k, v in item.items()
                    })
            return items

    # Try stats
    stats = content.get("stats")
    if isinstance(stats, list):
        for s in stats[:MAX_ITEMS]:
            if isinstance(s, dict):
                items.append({
                    "value": str(s.get("value", "")),
                    "label": _truncate(str(s.get("label", ""))),
                })
        return items

    # Try events (timeline)
    events = content.get("events")
    if isinstance(events, list):
        for idx, ev in enumerate(events[:MAX_ITEMS]):
            if isinstance(ev, dict):
                items.append({
                    "step": idx + 1,
                    "date": str(ev.get("date", "")),
                    "text": _truncate(str(ev.get("description", ""))),
                })
        return items

    # Fallback: extract body/description as single item
    body = content.get("body") or content.get("description") or ""
    if body:
        items.append({"text": _truncate(str(body))})

    return items


def _truncate(text: str, max_words: int = MAX_BULLET_WORDS) -> str:
    words = text.split()
    if len(words) > max_words:
        return " ".join(words[:max_words]) + "…"
    return text


def map_components(slide_data: dict, layout: str) -> dict[str, Any]:
    """Convert slide content into structured UI components."""
    content = slide_data.get("content", {})
    title = content.get("title") or content.get("section_title") or ""

    components: dict[str, Any] = {"title": str(title)}

    items = _extract_items(content)

    if layout == "grid_cards":
        components["type"] = "card_grid"
        components["items"] = items

    elif layout == "step_flow":
        steps = []
        for idx, item in enumerate(items):
            steps.append({
                "step": item.get("step", idx + 1),
                "text": item.get("text", ""),
            })
        components["type"] = "steps"
        components["steps"] = steps

    elif layout == "stats_blocks":
        stats = []
        for item in items:
            stats.append({
                "value": item.get("value", ""),
                "label": item.get("label", item.get("text", "")),
            })
        components["type"] = "stats"
        components["items"] = stats

    elif layout == "timeline_flow":
        timeline = []
        for idx, item in enumerate(items):
            timeline.append({
                "step": item.get("step", idx + 1),
                "date": item.get("date", ""),
                "text": item.get("text", ""),
            })
        components["type"] = "timeline"
        components["events"] = timeline

    elif layout == "split_left_text_right_visual":
        body = content.get("body") or content.get("description") or ""
        components["type"] = "split"
        components["body"] = _truncate(str(body), 30)
        components["items"] = items

    elif layout == "hero_center":
        subtitle = (
            content.get("subtitle")
            or content.get("body")
            or content.get("description")
            or ""
        )
        components["type"] = "hero"
        components["subtitle"] = _truncate(str(subtitle), 20)

    return components


def enforce_design_rules(components: dict) -> dict:
    """Enforce max 4 items, clean hierarchy, no overcrowding."""
    for key in ("items", "steps", "events"):
        if key in components and isinstance(components[key], list):
            components[key] = components[key][:MAX_ITEMS]
    return components


def resolve_theme(state_theme: str) -> str:
    """Resolve the Narrato theme to a visual theme name."""
    theme_map = {
        "modern": "dark_modern",
        "corporate": "minimal_light",
        "minimal": "minimal_light",
        "dark_modern": "dark_modern",
        "minimal_light": "minimal_light",
        "bold_gradient": "bold_gradient",
    }
    return theme_map.get(state_theme, DEFAULT_THEME)


def run_design_engine(slides: list[dict], state_theme: str = "modern") -> list[dict]:
    """
    Stage 1 entry point.

    Returns a list of design specs, one per slide:
    {
        "slide_index": int,
        "layout": str,
        "theme": str,
        "components": dict,
    }
    """
    theme_name = resolve_theme(state_theme)
    designs = []

    for idx, slide_data in enumerate(slides):
        layout = select_layout(slide_data)
        components = map_components(slide_data, layout)
        components = enforce_design_rules(components)

        designs.append({
            "slide_index": idx,
            "layout": layout,
            "theme": theme_name,
            "components": components,
        })

    # Deck-level consistency: ensure ALL slides use same theme
    # (already guaranteed by resolve_theme returning one value)
    logger.info(
        "[design_engine] Processed %d slides with theme=%s",
        len(designs), theme_name,
    )
    return designs
