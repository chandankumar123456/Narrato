"""
Stage 2: Template Engine

Converts design specs into full-screen HTML slides using Tailwind CSS.
Each slide is a standalone HTML document renderable at 1920×1080.

Design intelligence applied:
  - Visual hierarchy (title dominance, supporting elements recede)
  - Focal point design (one dominant element per slide)
  - Asymmetric spacing rhythm (top-heavy breathing, dense middle, open bottom)
  - Premium card styles (glass, shadows, layering)
  - Typography scale (8xl/6xl/3xl/lg/sm)
  - Composed layouts (intentional asymmetry, visual weight variation)
  - Subtle accents (gradient bars, dividers, glows)

Supports:
  - 6 layout types (hero_center, grid_cards, split, step_flow, stats_blocks, timeline_flow)
  - 3 themes (dark_modern, minimal_light, bold_gradient)
"""

import html
import logging
from typing import Any

from pipeline.visual_design_engine import VISUAL_THEMES, DEFAULT_THEME

logger = logging.getLogger(__name__)

TAILWIND_CDN = "https://cdn.tailwindcss.com"

# ── HTML wrapper ─────────────────────────────────────────────────────
# Asymmetric padding: more top (pt-24) for breathing, moderate sides,
# less bottom — creates intentional spacing rhythm per Rule 3.

_HTML_WRAPPER = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=1920,height=1080"/>
<script src="{tailwind_cdn}"></script>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap');
  body {{ margin:0; padding:0; font-family:'Inter',sans-serif; overflow:hidden; -webkit-font-smoothing:antialiased; }}
  .slide {{ width:1920px; height:1080px; position:relative; }}
</style>
</head>
<body>
<div class="slide {bg_class} {text_class} flex flex-col justify-center pt-24 pb-12 px-24">
{inner_html}
</div>
</body>
</html>"""


def _esc(text: Any) -> str:
    """HTML-escape a value."""
    return html.escape(str(text)) if text else ""


# ── Layout renderers ─────────────────────────────────────────────────

def _render_hero_center(components: dict, theme: dict) -> str:
    """Hero layout — dominant centered headline with strong focal point."""
    title = _esc(components.get("title", ""))
    subtitle = _esc(components.get("subtitle", ""))
    accent = theme["accent"]
    accent_line = theme["accent_line"]
    text_secondary = theme["text_secondary"]
    title_grad = theme["title_gradient"]
    text_muted = theme["text_muted"]
    image_url = components.get("image_url", "")

    # Optional background image (AI-generated, context-aware)
    bg_image = ""
    if image_url:
        bg_image = (
            f'<div class="absolute inset-0 z-0">'
            f'<img src="{_esc(image_url)}" alt="" class="w-full h-full object-cover opacity-20" />'
            f'<div class="absolute inset-0 bg-gradient-to-t from-black/80 via-black/40 to-transparent"></div>'
            f'</div>'
        )

    return f"""\
{bg_image}
<div class="flex-1 flex items-center justify-center relative z-10">
  <div class="text-center max-w-4xl mx-auto">
    <!-- Accent bar — focal point anchor -->
    <div class="w-16 h-1.5 {accent_line} rounded-full mx-auto mb-10"></div>
    <!-- Title: dominant element (60% visual weight) -->
    <h1 class="text-8xl font-extrabold leading-[1.05] tracking-tight mb-8 {title_grad}">{title}</h1>
    {f'<p class="text-2xl {text_secondary} leading-relaxed max-w-2xl mx-auto font-light">{subtitle}</p>' if subtitle else ''}
    <!-- Bottom accent — visual termination -->
    <div class="w-24 h-0.5 {accent_line} opacity-40 rounded-full mx-auto mt-12"></div>
  </div>
</div>"""


def _render_grid_cards(components: dict, theme: dict) -> str:
    """Grid cards — composed layout with first card as focal point."""
    title = _esc(components.get("title", ""))
    items = components.get("items", [])
    accent = theme["accent"]
    accent_line = theme["accent_line"]
    card_bg = theme["card_bg"]
    card_border = theme["card_border"]
    card_shadow = theme["card_shadow"]
    card_highlight = theme["card_highlight"]
    text_secondary = theme["text_secondary"]
    text_muted = theme["text_muted"]
    title_grad = theme["title_gradient"]

    # Composed grid: first card is emphasized (col-span-2 if 3+ items)
    cards_parts = []
    for idx, item in enumerate(items[:4]):
        text = _esc(item.get("text", ""))
        if idx == 0 and len(items) >= 3:
            # Focal card — larger, highlighted, dominant
            cards_parts.append(f"""\
    <div class="col-span-2 {card_highlight} border {card_shadow} rounded-3xl p-10 transition-all">
      <div class="w-10 h-1 {accent_line} rounded-full mb-6"></div>
      <p class="{text_secondary} text-xl leading-relaxed font-medium">{text}</p>
    </div>""")
        else:
            # Supporting cards — lighter visual weight
            cards_parts.append(f"""\
    <div class="{card_bg} {card_border} {card_shadow} rounded-2xl p-8 transition-all">
      <p class="{text_secondary} text-lg leading-relaxed">{text}</p>
    </div>""")
    cards_html = "\n".join(cards_parts)

    return f"""\
<div class="w-full max-w-6xl mx-auto flex-1 flex flex-col justify-center">
  <!-- Section title with accent -->
  <div class="mb-14">
    <div class="w-12 h-1 {accent_line} rounded-full mb-6"></div>
    <h2 class="text-6xl font-bold tracking-tight {title_grad}">{title}</h2>
  </div>
  <!-- Composed grid — asymmetric emphasis -->
  <div class="grid grid-cols-3 gap-6 auto-rows-auto">
{cards_html}
  </div>
</div>"""


def _render_split(components: dict, theme: dict) -> str:
    """Split layout — left text dominance with right visual image.

    STRICT: image_url is REQUIRED for split layouts. No empty panels.
    """
    from pipeline.slide_validator import SlideRenderError

    title = _esc(components.get("title", ""))
    body = _esc(components.get("body", ""))
    accent = theme["accent"]
    accent_line = theme["accent_line"]
    text_secondary = theme["text_secondary"]
    text_muted = theme["text_muted"]
    card_bg = theme["card_bg"]
    card_border = theme["card_border"]
    card_shadow = theme["card_shadow"]
    title_grad = theme["title_gradient"]
    image_url = components.get("image_url", "")

    items = components.get("items", [])
    bullet_parts = []
    for item in items[:4]:
        text = _esc(item.get("text", ""))
        if text:
            bullet_parts.append(
                f'      <li class="flex items-start gap-3">'
                f'<span class="{accent} text-lg mt-1">&#x2022;</span>'
                f'<span>{text}</span></li>'
            )
    bullets_html = "\n".join(bullet_parts)

    # STRICT: Split layout requires an image — no empty panel allowed
    if not image_url:
        raise SlideRenderError(
            [f"Split layout requires image_url but none provided (title: {title})"]
        )

    right_panel = f"""\
    <div class="{card_bg} {card_border} {card_shadow} rounded-3xl w-full aspect-[4/3] overflow-hidden">
      <img src="{_esc(image_url)}" alt="{title}" class="w-full h-full object-cover" />
    </div>"""

    return f"""\
<div class="flex w-full max-w-7xl mx-auto gap-16 flex-1 items-center">
  <!-- Left: text content (dominant) -->
  <div class="flex-1 flex flex-col justify-center max-w-2xl">
    <div class="w-12 h-1 {accent_line} rounded-full mb-8"></div>
    <h2 class="text-6xl font-bold tracking-tight leading-[1.1] mb-6 {title_grad}">{title}</h2>
    {f'<p class="text-xl {text_secondary} mb-8 leading-relaxed font-light">{body}</p>' if body else ''}
    {f'<ul class="{text_secondary} text-lg space-y-4 leading-relaxed">{bullets_html}</ul>' if bullets_html else ''}
  </div>
  <!-- Right: visual (secondary weight) -->
  <div class="flex-1 flex items-center justify-center">
    {right_panel}
  </div>
</div>"""


def _render_step_flow(components: dict, theme: dict) -> str:
    """Step flow — numbered steps with connecting line and first-step emphasis."""
    title = _esc(components.get("title", ""))
    steps = components.get("steps", [])
    accent = theme["accent"]
    accent_line = theme["accent_line"]
    step_bg = theme["step_number_bg"]
    step_connector = theme["step_connector"]
    text_secondary = theme["text_secondary"]
    text_muted = theme["text_muted"]
    card_bg = theme["card_bg"]
    card_border = theme["card_border"]
    card_shadow = theme["card_shadow"]
    card_highlight = theme["card_highlight"]
    accent_glow = theme["accent_glow"]
    title_grad = theme["title_gradient"]

    steps_parts = []
    for idx, step in enumerate(steps[:4]):
        num = _esc(step.get("step", ""))
        text = _esc(step.get("text", ""))
        is_first = idx == 0
        # First step gets emphasis (focal point)
        bg = card_highlight if is_first else card_bg
        border = f"border {card_shadow}" if is_first else card_border
        num_size = "w-14 h-14 text-xl" if is_first else "w-11 h-11 text-lg"
        text_size = "text-xl font-medium" if is_first else "text-lg"
        glow = accent_glow if is_first else ""

        # Connector line between steps (not after last)
        connector = ""
        if idx < len(steps) - 1:
            connector = f'<div class="w-0.5 h-6 {step_connector} mx-auto"></div>'

        steps_parts.append(f"""\
    <div>
      <div class="{bg} {border} {glow} rounded-2xl p-7 flex items-center gap-5">
        <div class="{step_bg} {accent_glow} text-white rounded-xl {num_size} flex items-center justify-center font-bold shrink-0">{num}</div>
        <p class="{text_secondary} {text_size} leading-relaxed">{text}</p>
      </div>
      {connector}
    </div>""")
    steps_html = "\n".join(steps_parts)

    return f"""\
<div class="w-full max-w-5xl mx-auto flex-1 flex flex-col justify-center">
  <div class="mb-14">
    <div class="w-12 h-1 {accent_line} rounded-full mb-6"></div>
    <h2 class="text-6xl font-bold tracking-tight {title_grad}">{title}</h2>
  </div>
  <div class="flex flex-col">
{steps_html}
  </div>
</div>"""


def _render_stats_blocks(components: dict, theme: dict) -> str:
    """Stats blocks — first stat dominates as focal point with glow."""
    title = _esc(components.get("title", ""))
    items = components.get("items", [])
    stat_color = theme["stat_value_color"]
    stat_glow = theme["stat_glow"]
    text_secondary = theme["text_secondary"]
    text_muted = theme["text_muted"]
    card_bg = theme["card_bg"]
    card_border = theme["card_border"]
    card_shadow = theme["card_shadow"]
    card_highlight = theme["card_highlight"]
    accent = theme["accent"]
    accent_line = theme["accent_line"]
    accent_glow = theme["accent_glow"]
    title_grad = theme["title_gradient"]

    stats_parts = []
    for idx, item in enumerate(items[:4]):
        value = _esc(item.get("value", ""))
        label = _esc(item.get("label", ""))
        if idx == 0:
            # Dominant stat — focal point (large number, glow, highlight bg)
            stats_parts.append(f"""\
    <div class="col-span-2 {card_highlight} border {stat_glow} rounded-3xl p-10 text-center relative overflow-hidden">
      <div class="absolute top-0 left-0 right-0 h-1 {accent_line}"></div>
      <div class="text-7xl font-black {stat_color} mb-4 tracking-tight">{value}</div>
      <div class="{text_secondary} text-xl font-medium">{label}</div>
    </div>""")
        else:
            # Supporting stats — lighter weight
            stats_parts.append(f"""\
    <div class="{card_bg} {card_border} {card_shadow} rounded-2xl p-8 text-center">
      <div class="text-5xl font-extrabold {stat_color} mb-3">{value}</div>
      <div class="{text_muted} text-base">{label}</div>
    </div>""")
    stats_html = "\n".join(stats_parts)

    return f"""\
<div class="w-full max-w-6xl mx-auto flex-1 flex flex-col justify-center">
  <div class="mb-14">
    <div class="w-12 h-1 {accent_line} rounded-full mb-6"></div>
    <h2 class="text-6xl font-bold tracking-tight {title_grad}">{title}</h2>
  </div>
  <!-- Composed stat grid — first stat dominates -->
  <div class="grid grid-cols-3 gap-6">
{stats_html}
  </div>
</div>"""


def _render_timeline_flow(components: dict, theme: dict) -> str:
    """Timeline — vertical flow with gradient accent line and date badges."""
    title = _esc(components.get("title", ""))
    events = components.get("events", [])
    accent = theme["accent"]
    accent_line = theme["accent_line"]
    text_secondary = theme["text_secondary"]
    text_muted = theme["text_muted"]
    divider = theme["divider"]
    step_bg = theme["step_number_bg"]
    accent_glow = theme["accent_glow"]
    card_bg = theme["card_bg"]
    card_border = theme["card_border"]
    card_shadow = theme["card_shadow"]
    title_grad = theme["title_gradient"]

    events_parts = []
    for idx, ev in enumerate(events[:4]):
        date = _esc(ev.get("date", ""))
        text = _esc(ev.get("text", ""))
        is_first = idx == 0
        node_size = "w-5 h-5" if is_first else "w-3.5 h-3.5"
        glow = accent_glow if is_first else ""
        text_weight = "text-xl font-medium" if is_first else "text-lg"

        # Connecting line (not after last)
        connector = ""
        if idx < len(events) - 1:
            connector = f'<div class="w-0.5 flex-1 {accent_line} opacity-30 min-h-[2rem]"></div>'

        events_parts.append(f"""\
    <div class="flex items-stretch gap-8">
      <!-- Timeline spine -->
      <div class="flex flex-col items-center pt-2">
        <div class="{step_bg} {glow} rounded-full {node_size} shrink-0"></div>
        {connector}
      </div>
      <!-- Event content -->
      <div class="pb-10">
        {f'<div class="{step_bg} text-white text-sm font-semibold px-4 py-1.5 rounded-full inline-block mb-3">{date}</div>' if date else ''}
        <p class="{text_secondary} {text_weight} leading-relaxed">{text}</p>
      </div>
    </div>""")
    events_html = "\n".join(events_parts)

    return f"""\
<div class="w-full max-w-4xl mx-auto flex-1 flex flex-col justify-center">
  <div class="mb-14">
    <div class="w-12 h-1 {accent_line} rounded-full mb-6"></div>
    <h2 class="text-6xl font-bold tracking-tight {title_grad}">{title}</h2>
  </div>
  <div class="flex flex-col pl-4">
{events_html}
  </div>
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
