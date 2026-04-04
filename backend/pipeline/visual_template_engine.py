"""
Stage 2: Template Engine

Converts design specs into full-screen HTML slides using Tailwind CSS.
Each slide is a standalone HTML document renderable at 1920×1080.

Supports:
  - 6 layout types (hero_center, grid_cards, split, step_flow, stats_blocks, timeline_flow)
  - 3 themes (dark_modern, minimal_light, bold_gradient)
  - Glass effects, gradients, rounded corners, strong typography
"""

import html
import logging
from typing import Any

from pipeline.visual_design_engine import VISUAL_THEMES, DEFAULT_THEME

logger = logging.getLogger(__name__)

TAILWIND_CDN = "https://cdn.tailwindcss.com"

# ── HTML wrapper ─────────────────────────────────────────────────────

_HTML_WRAPPER = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=1920,height=1080"/>
<script src="{tailwind_cdn}"></script>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
  body {{ margin:0; padding:0; font-family:'Inter',sans-serif; overflow:hidden; }}
  .slide {{ width:1920px; height:1080px; }}
</style>
</head>
<body>
<div class="slide {bg_class} {text_class} flex items-center justify-center p-16">
{inner_html}
</div>
</body>
</html>"""


def _esc(text: Any) -> str:
    """HTML-escape a value."""
    return html.escape(str(text)) if text else ""


# ── Layout renderers ─────────────────────────────────────────────────

def _render_hero_center(components: dict, theme: dict) -> str:
    title = _esc(components.get("title", ""))
    subtitle = _esc(components.get("subtitle", ""))
    accent = theme["accent"]
    text_secondary = theme["text_secondary"]
    return f"""\
<div class="text-center max-w-4xl mx-auto">
  <h1 class="text-7xl font-extrabold leading-tight mb-8 {accent}">{title}</h1>
  {f'<p class="text-2xl {text_secondary} leading-relaxed">{subtitle}</p>' if subtitle else ''}
</div>"""


def _render_grid_cards(components: dict, theme: dict) -> str:
    title = _esc(components.get("title", ""))
    items = components.get("items", [])
    accent = theme["accent"]
    card_bg = theme["card_bg"]
    card_border = theme["card_border"]
    text_secondary = theme["text_secondary"]

    cols = "grid-cols-2" if len(items) <= 2 else "grid-cols-3"
    cards_html = ""
    for item in items[:4]:
        text = _esc(item.get("text", ""))
        cards_html += f"""\
    <div class="{card_bg} {card_border} rounded-2xl p-8 transition-transform hover:scale-105">
      <p class="{text_secondary} text-lg leading-relaxed">{text}</p>
    </div>
"""

    return f"""\
<div class="w-full max-w-6xl mx-auto">
  <h2 class="text-5xl font-bold mb-12 text-center {accent}">{title}</h2>
  <div class="grid {cols} gap-8">
{cards_html}  </div>
</div>"""


def _render_split(components: dict, theme: dict) -> str:
    title = _esc(components.get("title", ""))
    body = _esc(components.get("body", ""))
    accent = theme["accent"]
    text_secondary = theme["text_secondary"]
    card_bg = theme["card_bg"]
    card_border = theme["card_border"]

    items = components.get("items", [])
    bullet_parts = []
    for item in items[:4]:
        text = _esc(item.get("text", ""))
        if text:
            bullet_parts.append(f'      <li class="mb-3">{text}</li>')
    bullets_html = "\n".join(bullet_parts)

    return f"""\
<div class="flex w-full max-w-6xl mx-auto gap-12">
  <div class="flex-1 flex flex-col justify-center">
    <h2 class="text-5xl font-bold mb-6 {accent}">{title}</h2>
    {f'<p class="text-xl {text_secondary} mb-6 leading-relaxed">{body}</p>' if body else ''}
    {f'<ul class="list-disc list-inside {text_secondary} text-lg space-y-2">{bullets_html}</ul>' if bullets_html else ''}
  </div>
  <div class="flex-1 flex items-center justify-center">
    <div class="{card_bg} {card_border} rounded-3xl w-full h-80 flex items-center justify-center">
      <span class="{text_secondary} text-lg">Visual</span>
    </div>
  </div>
</div>"""


def _render_step_flow(components: dict, theme: dict) -> str:
    title = _esc(components.get("title", ""))
    steps = components.get("steps", [])
    accent = theme["accent"]
    step_bg = theme["step_number_bg"]
    text_secondary = theme["text_secondary"]
    card_bg = theme["card_bg"]
    card_border = theme["card_border"]

    steps_html = ""
    for step in steps[:4]:
        num = _esc(step.get("step", ""))
        text = _esc(step.get("text", ""))
        steps_html += f"""\
    <div class="{card_bg} {card_border} rounded-2xl p-6 flex items-start gap-4">
      <div class="{step_bg} text-white rounded-full w-10 h-10 flex items-center justify-center font-bold text-lg shrink-0">{num}</div>
      <p class="{text_secondary} text-lg leading-relaxed">{text}</p>
    </div>
"""

    return f"""\
<div class="w-full max-w-5xl mx-auto">
  <h2 class="text-5xl font-bold mb-12 text-center {accent}">{title}</h2>
  <div class="flex flex-col gap-6">
{steps_html}  </div>
</div>"""


def _render_stats_blocks(components: dict, theme: dict) -> str:
    title = _esc(components.get("title", ""))
    items = components.get("items", [])
    stat_color = theme["stat_value_color"]
    text_secondary = theme["text_secondary"]
    card_bg = theme["card_bg"]
    card_border = theme["card_border"]
    accent = theme["accent"]

    cols = "grid-cols-2" if len(items) <= 2 else "grid-cols-3"
    stats_html = ""
    for item in items[:4]:
        value = _esc(item.get("value", ""))
        label = _esc(item.get("label", ""))
        stats_html += f"""\
    <div class="{card_bg} {card_border} rounded-2xl p-8 text-center">
      <div class="text-5xl font-extrabold {stat_color} mb-3">{value}</div>
      <div class="{text_secondary} text-lg">{label}</div>
    </div>
"""

    return f"""\
<div class="w-full max-w-6xl mx-auto">
  <h2 class="text-5xl font-bold mb-12 text-center {accent}">{title}</h2>
  <div class="grid {cols} gap-8">
{stats_html}  </div>
</div>"""


def _render_timeline_flow(components: dict, theme: dict) -> str:
    title = _esc(components.get("title", ""))
    events = components.get("events", [])
    accent = theme["accent"]
    text_secondary = theme["text_secondary"]
    divider = theme["divider"]
    step_bg = theme["step_number_bg"]

    events_html = ""
    for ev in events[:4]:
        date = _esc(ev.get("date", ""))
        text = _esc(ev.get("text", ""))
        events_html += f"""\
    <div class="flex items-start gap-6 mb-8">
      <div class="flex flex-col items-center">
        <div class="{step_bg} text-white rounded-full w-4 h-4"></div>
        <div class="w-0.5 h-16 {divider} border-l-2"></div>
      </div>
      <div>
        {f'<div class="{accent} font-semibold text-lg mb-1">{date}</div>' if date else ''}
        <p class="{text_secondary} text-lg leading-relaxed">{text}</p>
      </div>
    </div>
"""

    return f"""\
<div class="w-full max-w-4xl mx-auto">
  <h2 class="text-5xl font-bold mb-12 text-center {accent}">{title}</h2>
  <div class="flex flex-col">
{events_html}  </div>
</div>"""


# ── Layout dispatcher ────────────────────────────────────────────────

_LAYOUT_RENDERERS = {
    "hero_center": _render_hero_center,
    "grid_cards": _render_grid_cards,
    "split_left_text_right_visual": _render_split,
    "step_flow": _render_step_flow,
    "stats_blocks": _render_stats_blocks,
    "timeline_flow": _render_timeline_flow,
}


def render_slide_html(design: dict) -> str:
    """
    Convert a single design spec into a full HTML document.

    Args:
        design: output from the design engine with keys
                layout, theme, components.
    Returns:
        Complete HTML string for the slide.
    """
    layout = design.get("layout", "hero_center")
    theme_name = design.get("theme", DEFAULT_THEME)
    components = design.get("components", {})

    theme = VISUAL_THEMES.get(theme_name, VISUAL_THEMES[DEFAULT_THEME])
    renderer = _LAYOUT_RENDERERS.get(layout, _render_hero_center)
    inner_html = renderer(components, theme)

    return _HTML_WRAPPER.format(
        tailwind_cdn=TAILWIND_CDN,
        bg_class=theme["background"],
        text_class=theme["text_primary"],
        inner_html=inner_html,
    )


def run_template_engine(designs: list[dict]) -> list[str]:
    """
    Stage 2 entry point.

    Takes design specs from Stage 1 and produces one HTML string per slide.
    """
    html_slides = []
    for design in designs:
        slide_html = render_slide_html(design)
        html_slides.append(slide_html)

    logger.info("[template_engine] Generated %d HTML slides", len(html_slides))
    return html_slides
