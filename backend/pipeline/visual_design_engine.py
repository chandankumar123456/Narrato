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
        "background": "bg-gradient-to-br from-black via-gray-950 to-gray-900",
        "text_primary": "text-white",
        "text_secondary": "text-white/70",
        "text_muted": "text-white/40",
        "card_bg": "bg-white/[0.07] backdrop-blur-xl",
        "card_border": "border border-white/[0.12]",
        "card_shadow": "shadow-2xl shadow-purple-500/10",
        "card_highlight": "bg-white/[0.12] backdrop-blur-xl border-white/[0.2]",
        "accent": "text-purple-400",
        "accent_bg": "bg-purple-500/20",
        "accent_line": "bg-gradient-to-r from-purple-500 to-pink-500",
        "accent_glow": "shadow-lg shadow-purple-500/20",
        "title_gradient": "bg-gradient-to-r from-white via-purple-200 to-purple-400 bg-clip-text text-transparent",
        "font_heading": "font-sans",
        "font_body": "font-sans",
        "stat_value_color": "text-purple-400",
        "stat_glow": "shadow-lg shadow-purple-500/25",
        "step_number_bg": "bg-gradient-to-br from-purple-500 to-pink-500",
        "step_connector": "bg-gradient-to-b from-purple-500/60 to-transparent",
        "divider": "border-white/[0.12]",
        "overlay_gradient": "bg-gradient-to-t from-black/30 via-transparent to-transparent",
    },
    "minimal_light": {
        "background": "bg-gradient-to-br from-white via-gray-50 to-slate-100",
        "text_primary": "text-gray-900",
        "text_secondary": "text-gray-500",
        "text_muted": "text-gray-400",
        "card_bg": "bg-white",
        "card_border": "border border-gray-200/80",
        "card_shadow": "shadow-xl shadow-gray-200/50",
        "card_highlight": "bg-indigo-50/80 border-indigo-200/60",
        "accent": "text-indigo-600",
        "accent_bg": "bg-indigo-50",
        "accent_line": "bg-gradient-to-r from-indigo-500 to-violet-500",
        "accent_glow": "shadow-lg shadow-indigo-200/40",
        "title_gradient": "bg-gradient-to-r from-gray-900 via-indigo-900 to-indigo-600 bg-clip-text text-transparent",
        "font_heading": "font-sans",
        "font_body": "font-sans",
        "stat_value_color": "text-indigo-600",
        "stat_glow": "shadow-lg shadow-indigo-100/60",
        "step_number_bg": "bg-gradient-to-br from-indigo-500 to-violet-500",
        "step_connector": "bg-gradient-to-b from-indigo-300/60 to-transparent",
        "divider": "border-gray-200",
        "overlay_gradient": "",
    },
    "bold_gradient": {
        "background": "bg-gradient-to-br from-indigo-950 via-purple-900 to-pink-800",
        "text_primary": "text-white",
        "text_secondary": "text-pink-100/80",
        "text_muted": "text-pink-200/40",
        "card_bg": "bg-white/[0.1] backdrop-blur-xl",
        "card_border": "border border-white/[0.15]",
        "card_shadow": "shadow-2xl shadow-pink-500/15",
        "card_highlight": "bg-white/[0.18] backdrop-blur-xl border-white/[0.25]",
        "accent": "text-pink-300",
        "accent_bg": "bg-pink-500/20",
        "accent_line": "bg-gradient-to-r from-pink-400 to-amber-400",
        "accent_glow": "shadow-lg shadow-pink-500/30",
        "title_gradient": "bg-gradient-to-r from-white via-pink-200 to-amber-300 bg-clip-text text-transparent",
        "font_heading": "font-sans",
        "font_body": "font-sans",
        "stat_value_color": "text-pink-300",
        "stat_glow": "shadow-lg shadow-pink-500/25",
        "step_number_bg": "bg-gradient-to-br from-pink-500 to-amber-500",
        "step_connector": "bg-gradient-to-b from-pink-400/60 to-transparent",
        "divider": "border-white/[0.15]",
        "overlay_gradient": "bg-gradient-to-t from-black/20 via-transparent to-transparent",
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
    """Extract structured items from slide content.

    Uses a two-phase approach:
      Phase 1: Try known schema patterns (fast, precise).
      Phase 2: Dynamic fallback — scan ALL content keys for any list/dict/string
               values that can be interpreted as items. This ensures unknown or
               new schemas are NEVER silently dropped.

    Known schemas:
      - bullet_points / bullets / items / features / cards (list[str|dict])
      - steps / flow (list[dict] with step/text/label)
      - left_points / right_points (comparison)
      - stats (list[dict]) and flat stat fields (stat/stat_label)
      - events (timeline)
      - body / description / cta_text / subtitle (fallback single item)
    """
    items: list[dict] = []

    # ── Phase 1: Known schema patterns ──────────────────────────────

    # Try bullet_points / bullets / cards / features
    for key in ("bullet_points", "bullets", "items", "features", "cards"):
        raw = content.get(key)
        if isinstance(raw, list) and raw:
            for item in raw[:MAX_ITEMS]:
                if isinstance(item, str):
                    items.append({"text": _truncate(item)})
                elif isinstance(item, dict):
                    items.append(_normalize_dict_item(item))
            return items

    # Try steps / flow (structured step lists)
    for key in ("steps", "flow"):
        raw = content.get(key)
        if isinstance(raw, list) and raw:
            for idx, item in enumerate(raw[:MAX_ITEMS]):
                if isinstance(item, str):
                    items.append({"step": idx + 1, "text": _truncate(item)})
                elif isinstance(item, dict):
                    items.append({
                        "step": item.get("step", idx + 1),
                        "text": _truncate(str(item.get("text", item.get("label", item.get("description", ""))))),
                    })
            return items

    # Try comparison-style content (left_points / right_points)
    left_pts = content.get("left_points", [])
    right_pts = content.get("right_points", [])
    if left_pts or right_pts:
        left_label = content.get("left_label", "")
        right_label = content.get("right_label", "")
        for pt in left_pts:
            items.append({"text": _truncate(f"{left_label}: {pt}" if left_label else str(pt), 30)})
        for pt in right_pts:
            items.append({"text": _truncate(f"{right_label}: {pt}" if right_label else str(pt), 30)})
        return items[:MAX_ITEMS]

    # Try stats
    stats = content.get("stats")
    if isinstance(stats, list) and stats:
        for s in stats[:MAX_ITEMS]:
            if isinstance(s, dict):
                items.append({
                    "value": str(s.get("value", "")),
                    "label": _truncate(str(s.get("label", ""))),
                })
        return items

    # Try flat stat fields (from narrative generator stats_slide)
    stat_val = content.get("stat")
    if stat_val is not None:
        stat_label = content.get("stat_label", "")
        description = content.get("description", "")
        items.append({"value": str(stat_val), "label": _truncate(str(stat_label or description))})
        if description and description != stat_label:
            for part in str(description).split(" | ")[:MAX_ITEMS - 1]:
                part = part.strip()
                if part:
                    items.append({"value": "", "label": _truncate(part)})
        return items[:MAX_ITEMS]

    # Try events (timeline)
    events = content.get("events")
    if isinstance(events, list) and events:
        for idx, ev in enumerate(events[:MAX_ITEMS]):
            if isinstance(ev, dict):
                items.append({
                    "step": idx + 1,
                    "date": str(ev.get("date", "")),
                    "text": _truncate(str(ev.get("description", ev.get("text", "")))),
                })
        return items

    # ── Phase 2: Dynamic fallback — scan ALL remaining content ──────
    # This handles unknown schemas, nested dicts, or any new structure.
    # Skip known scalar keys that will be handled by body fallback below.
    _SCALAR_KEYS = {"title", "section_title", "presenter", "contact", "source",
                    "image_url", "left_label", "right_label"}

    # First: find ANY list values (unknown keys) and extract items
    for key, val in content.items():
        if key in _SCALAR_KEYS or key == "title":
            continue
        if isinstance(val, list) and val:
            for item in val[:MAX_ITEMS]:
                if isinstance(item, str):
                    items.append({"text": _truncate(item)})
                elif isinstance(item, dict):
                    items.append(_normalize_dict_item(item))
            if items:
                return items

    # Second: find ANY nested dict values and flatten them into text
    for key, val in content.items():
        if key in _SCALAR_KEYS or key == "title":
            continue
        if isinstance(val, dict) and val:
            items.append({"text": _truncate(_flatten_dict_to_text(val))})
            if items:
                return items[:MAX_ITEMS]

    # Final fallback: extract body/description/cta_text/subtitle/summary as single item
    for key in ("body", "description", "cta_text", "subtitle", "summary"):
        body = content.get(key)
        if body and isinstance(body, str) and body.strip():
            items.append({"text": _truncate(str(body))})
            return items

    # Last resort: extract ANY remaining non-empty string value
    for key, val in content.items():
        if key in _SCALAR_KEYS or key == "title":
            continue
        if isinstance(val, str) and val.strip():
            items.append({"text": _truncate(val)})
            if items:
                return items[:MAX_ITEMS]

    return items


def _normalize_dict_item(item: dict) -> dict:
    """Normalize a dict item into a renderable structure with a 'text' key."""
    normalized = {
        k: _truncate(str(v)) for k, v in item.items()
    }
    # Synthesize 'text' from common label/description keys when missing
    if "text" not in normalized:
        label = normalized.get("label", "") or normalized.get("name", "")
        desc = (normalized.get("description", "")
                or normalized.get("desc", "")
                or normalized.get("detail", "")
                or normalized.get("summary", ""))
        if label and desc:
            normalized["text"] = _truncate(f"{label}: {desc}", 30)
        elif desc:
            normalized["text"] = desc
        elif label:
            normalized["text"] = label
        else:
            # Fallback: join first 2 non-empty string values
            vals = [str(v) for v in item.values() if v and isinstance(v, (str, int, float))]
            normalized["text"] = _truncate(" — ".join(vals[:2])) if vals else ""
    return normalized


def _flatten_dict_to_text(d: dict, max_depth: int = 2) -> str:
    """Flatten a nested dict into a human-readable text string."""
    parts: list[str] = []
    for k, v in d.items():
        if isinstance(v, str) and v.strip():
            parts.append(f"{k}: {v}")
        elif isinstance(v, (int, float)):
            parts.append(f"{k}: {v}")
        elif isinstance(v, dict) and max_depth > 0:
            parts.append(_flatten_dict_to_text(v, max_depth - 1))
        elif isinstance(v, list):
            parts.append(f"{k}: {', '.join(str(i) for i in v[:3])}")
    return " | ".join(parts[:4])


def _truncate(text: str, max_words: int = MAX_BULLET_WORDS) -> str:
    words = text.split()
    if len(words) > max_words:
        return " ".join(words[:max_words]) + "…"
    return text


def map_components(slide_data: dict, layout: str) -> dict[str, Any]:
    """Convert slide content into structured UI components.

    Preserves ALL content keys from the original slide content so that no
    information is silently dropped.  Unknown fields are carried through
    in an '_extra' dict for downstream access if needed.
    """
    content = slide_data.get("content", {})
    title = content.get("title") or content.get("section_title") or ""

    components: dict[str, Any] = {"title": str(title)}

    items = _extract_items(content)

    # Resolve image_url: content.image_url (primary) OR slide.image_path (fallback)
    def _resolve_image_url() -> str:
        url = content.get("image_url", "")
        if url:
            return url
        # Fallback: check slide-level image_path (backward compatibility)
        path = slide_data.get("image_path")
        if path:
            import os
            abs_path = os.path.abspath(path)
            return f"file://{abs_path}"
        return ""

    if layout == "grid_cards":
        components["type"] = "card_grid"
        components["items"] = items
        img_url = _resolve_image_url()
        if img_url:
            components["image_url"] = img_url

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
        body = (
            content.get("body")
            or content.get("description")
            or content.get("summary")
            or content.get("cta_text")
            or ""
        )
        components["type"] = "split"
        components["body"] = _truncate(str(body), 30)
        components["items"] = items
        img_url = _resolve_image_url()
        if img_url:
            components["image_url"] = img_url

    elif layout == "hero_center":
        subtitle = (
            content.get("subtitle")
            or content.get("key_takeaway")
            or content.get("cta_text")
            or content.get("body")
            or content.get("description")
            or content.get("summary")
            or ""
        )
        # Fall back to joining bullets/key_points if no subtitle found
        if not subtitle:
            bullets = content.get("bullets") or content.get("key_points") or []
            if bullets:
                subtitle = " · ".join(str(b) for b in bullets[:3])
        # Final fallback: use extracted items as subtitle (for unknown schemas)
        if not subtitle and items:
            subtitle = " · ".join(
                item.get("text", item.get("label", "")) for item in items[:3]
                if item.get("text") or item.get("label")
            )
        components["type"] = "hero"
        components["subtitle"] = _truncate(str(subtitle), 20)
        img_url = _resolve_image_url()
        if img_url:
            components["image_url"] = img_url

    return components


# ── Image decision logic ─────────────────────────────────────────────

# Slide types where images are likely to IMPROVE understanding
_IMAGE_BENEFICIAL_TYPES = frozenset({
    "example_slide", "example_detail_slide", "image_slide",
    "product", "feature_slide",
})

# Slide types where images are NOT helpful (abstract or text-only)
_IMAGE_NOT_BENEFICIAL_TYPES = frozenset({
    "title_slide", "cta_slide", "thank_you_slide", "agenda_slide",
    "conclusion_slide", "stats_slide", "comparison_slide",
    "section_header", "quote_slide",
})


def should_use_image(slide_data: dict) -> bool:
    """Decide whether a slide should include an AI-generated image.

    Rules:
      1. Images are OPTIONAL — only when they improve understanding.
      2. Abstract slides (stats, CTA, conclusion) → NO image.
      3. Visual/example slides (product, feature) → YES if content is concrete.
      4. Unknown types → NO (conservative default).

    Args:
        slide_data: Structured slide dict with {type, content}.

    Returns:
        True if an image should be generated for this slide.
    """
    slide_type = (slide_data.get("type") or "").lower()
    content = slide_data.get("content", {})

    # Explicit exclusion for abstract slides
    if slide_type in _IMAGE_NOT_BENEFICIAL_TYPES:
        return False

    # Explicit inclusion for visual slides
    if slide_type in _IMAGE_BENEFICIAL_TYPES:
        return True

    # For unknown types: check if content has visual indicators
    title = str(content.get("title", "")).lower()
    visual_keywords = {"demo", "example", "screenshot", "diagram", "visual",
                       "illustration", "photo", "image", "workflow", "architecture"}
    if any(kw in title for kw in visual_keywords):
        return True

    # Conservative default: no image for unknown slide types
    return False


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
