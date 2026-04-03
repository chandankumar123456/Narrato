"""
Reusable visual components for slide rendering.

Each component follows the design system's spacing, typography, and
alignment rules.  Components use *python-pptx* primitives internally
and are called from individual layout renderers.
"""

from __future__ import annotations

from pptx.util import Inches, Pt  # type: ignore
from pptx.enum.text import PP_ALIGN  # type: ignore

from ppt.generator import add_text_box, hex_to_rgb
from ppt.design_system import (
    Grid,
    Spacing,
    Typography,
    VLayout,
    SLIDE_WIDTH,
    SLIDE_HEIGHT,
)


# ======================================================================
# Accent / Decorative Elements
# ======================================================================

def accent_bar_top(slide, theme, *, height: float = 0.10):
    """Full-width accent bar at the very top."""
    bar = slide.shapes.add_shape(
        1, Inches(0), Inches(0), Inches(SLIDE_WIDTH), Inches(height),
    )
    bar.fill.solid()
    bar.fill.fore_color.rgb = hex_to_rgb(theme.primary)
    bar.line.fill.background()
    return bar


def accent_bar_bottom(slide, theme, *, height: float = 0.12,
                      color: str | None = None):
    """Full-width accent bar at the very bottom."""
    y = SLIDE_HEIGHT - height
    c = color or theme.accent
    bar = slide.shapes.add_shape(
        1, Inches(0), Inches(y), Inches(SLIDE_WIDTH), Inches(height),
    )
    bar.fill.solid()
    bar.fill.fore_color.rgb = hex_to_rgb(c)
    bar.line.fill.background()
    return bar


def accent_underline(slide, theme, *, left: float | None = None,
                     y: float | None = None, width: float = 1.5,
                     color: str | None = None):
    """Thin accent underline (typically below a heading)."""
    _left = left if left is not None else Grid.MARGIN
    _y = y if y is not None else VLayout.ACCENT_Y
    c = color or theme.accent
    bar = slide.shapes.add_shape(
        1, Inches(_left), Inches(_y), Inches(width), Inches(VLayout.ACCENT_HEIGHT),
    )
    bar.fill.solid()
    bar.fill.fore_color.rgb = hex_to_rgb(c)
    bar.line.fill.background()
    return bar


def divider_line(slide, theme, *, y: float = 4.5, width: float = 2.0,
                 center: bool = True, color: str | None = None):
    """Thin horizontal divider."""
    c = color or theme.accent
    left = (SLIDE_WIDTH - width) / 2 if center else Grid.MARGIN
    bar = slide.shapes.add_shape(
        1, Inches(left), Inches(y), Inches(width), Inches(0.05),
    )
    bar.fill.solid()
    bar.fill.fore_color.rgb = hex_to_rgb(c)
    bar.line.fill.background()
    return bar


def vertical_divider(slide, theme, *, y: float = 1.8, height: float = 4.8,
                     color: str | None = None):
    """Vertical divider at the horizontal centre of the slide."""
    c = color or theme.accent
    x = SLIDE_WIDTH / 2 - 0.03
    div = slide.shapes.add_shape(
        1, Inches(x), Inches(y), Inches(0.06), Inches(height),
    )
    div.fill.solid()
    div.fill.fore_color.rgb = hex_to_rgb(c)
    div.line.fill.background()
    return div


# ======================================================================
# Text Components
# ======================================================================

def hero_text(slide, text: str, theme, *, y: float = 2.4,
              color: str | None = None, align=PP_ALIGN.CENTER):
    """Large hero text — the dominant visual element."""
    left, width = Grid.center(10)
    c = color or theme.primary
    return add_text_box(
        slide, text,
        Inches(left), Inches(y), Inches(width), Inches(1.6),
        theme.font_heading, Typography.HERO, bold=True,
        color=c, align=align,
    )


def heading_block(slide, text: str, theme, *, left: float | None = None,
                  y: float | None = None, width: float | None = None,
                  size: int | None = None, color: str | None = None,
                  align=PP_ALIGN.LEFT):
    """Standard section heading."""
    _left = left if left is not None else Grid.MARGIN
    _y = y if y is not None else VLayout.TITLE_TOP
    _w = width if width is not None else Grid.USABLE_WIDTH
    _sz = size or Typography.HEADING
    c = color or theme.primary
    return add_text_box(
        slide, text,
        Inches(_left), Inches(_y), Inches(_w), Inches(VLayout.TITLE_HEIGHT),
        theme.font_heading, _sz, bold=True,
        color=c, align=align,
    )


def subheading_text(slide, text: str, theme, *, left: float | None = None,
                    y: float = 1.6, width: float | None = None,
                    color: str | None = None, align=PP_ALIGN.LEFT):
    """Secondary heading below the main heading."""
    _left = left if left is not None else Grid.MARGIN
    _w = width if width is not None else Grid.USABLE_WIDTH
    c = color or theme.secondary
    return add_text_box(
        slide, text,
        Inches(_left), Inches(y), Inches(_w), Inches(0.7),
        theme.font_heading, Typography.SUBHEADING, bold=True,
        color=c, align=align,
    )


def body_text(slide, text: str, theme, *, left: float | None = None,
              y: float = 2.5, width: float | None = None,
              height: float = 1.5, size: int | None = None,
              color: str | None = None, align=PP_ALIGN.LEFT):
    """Standard body text."""
    _left = left if left is not None else Grid.MARGIN
    _w = width if width is not None else Grid.USABLE_WIDTH
    _sz = size or Typography.BODY
    c = color or theme.text
    return add_text_box(
        slide, text,
        Inches(_left), Inches(y), Inches(_w), Inches(height),
        theme.font_body, _sz, bold=False,
        color=c, align=align,
    )


def caption_text(slide, text: str, theme, *, left: float | None = None,
                 y: float = 6.5, width: float | None = None,
                 color: str | None = None, align=PP_ALIGN.CENTER):
    """Small caption or source attribution."""
    _left = left if left is not None else Grid.MARGIN
    _w = width if width is not None else Grid.USABLE_WIDTH
    c = color or theme.secondary
    return add_text_box(
        slide, text,
        Inches(_left), Inches(y), Inches(_w), Inches(0.45),
        theme.font_body, Typography.CAPTION, bold=False,
        color=c, align=align,
    )


# ======================================================================
# Bullet Group
# ======================================================================

def bullet_group(slide, items: list[str], theme, *, left: float | None = None,
                 start_y: float | None = None, width: float | None = None,
                 size: int | None = None, gap: float | None = None,
                 color: str | None = None):
    """Render a list of bullet points with consistent spacing."""
    _left = left if left is not None else Grid.MARGIN + Spacing.ELEMENT
    _y = start_y if start_y is not None else VLayout.CONTENT_START
    _w = width if width is not None else Grid.USABLE_WIDTH - Spacing.ELEMENT
    _sz = size or Typography.BODY
    _gap = gap if gap is not None else (Spacing.ELEMENT + Spacing.TIGHT)
    c = color or theme.text

    boxes = []
    for i, item in enumerate(items):
        y_pos = _y + i * _gap
        box = add_text_box(
            slide, f"•  {item}",
            Inches(_left), Inches(y_pos), Inches(_w), Inches(0.6),
            theme.font_body, _sz, bold=False,
            color=c, align=PP_ALIGN.LEFT,
        )
        boxes.append(box)
    return boxes


# ======================================================================
# Card
# ======================================================================

def card(slide, theme, *, left: float, y: float, width: float,
         height: float, icon: str = "", label: str = "",
         description: str = "", show_accent_strip: bool = False):
    """Card with optional icon, label, and description."""
    # Background
    bg = slide.shapes.add_shape(
        1, Inches(left), Inches(y), Inches(width), Inches(height),
    )
    bg.fill.solid()
    surface = getattr(theme, "surface", None) or theme.background
    bg.fill.fore_color.rgb = hex_to_rgb(surface)
    bg.line.color.rgb = hex_to_rgb(theme.secondary)
    bg.line.width = Pt(1)

    if show_accent_strip:
        strip = slide.shapes.add_shape(
            1, Inches(left), Inches(y), Inches(width), Inches(0.08),
        )
        strip.fill.solid()
        strip.fill.fore_color.rgb = hex_to_rgb(theme.accent)
        strip.line.fill.background()

    pad = Spacing.TIGHT
    inner_left = left + pad
    inner_w = width - 2 * pad
    cur_y = y + Spacing.ELEMENT

    if icon:
        add_text_box(
            slide, icon,
            Inches(left), Inches(cur_y), Inches(width), Inches(0.6),
            theme.font_body, Typography.SUBHEADING, bold=False,
            color=theme.accent, align=PP_ALIGN.CENTER,
        )
        cur_y += 0.6 + pad

    if label:
        add_text_box(
            slide, label,
            Inches(inner_left), Inches(cur_y), Inches(inner_w), Inches(0.6),
            theme.font_heading, Typography.BODY, bold=True,
            color=theme.primary, align=PP_ALIGN.CENTER,
        )
        cur_y += 0.6 + pad

    if description:
        remaining = (y + height) - cur_y - pad
        add_text_box(
            slide, description,
            Inches(inner_left), Inches(cur_y),
            Inches(inner_w), Inches(max(remaining, 0.5)),
            theme.font_body, Typography.CAPTION, bold=False,
            color=theme.text, align=PP_ALIGN.CENTER,
        )


# ======================================================================
# Stat Block
# ======================================================================

def stat_block(slide, stat: str, label: str, theme, *,
               left: float | None = None, y: float = 2.2,
               width: float | None = None):
    """Large statistic number with label — the dominant element."""
    if left is None or width is None:
        _left, _width = Grid.center(10)
        if left is not None:
            _left = left
        if width is not None:
            _width = width
    else:
        _left, _width = left, width

    # Big number
    add_text_box(
        slide, stat,
        Inches(_left), Inches(y), Inches(_width), Inches(1.8),
        theme.font_heading, Typography.HERO + 12, bold=True,
        color=theme.accent, align=PP_ALIGN.CENTER,
    )
    # Label underneath
    add_text_box(
        slide, label,
        Inches(_left), Inches(y + 1.8 + Spacing.TIGHT),
        Inches(_width), Inches(0.7),
        theme.font_body, Typography.SUBHEADING - 4, bold=False,
        color=theme.secondary, align=PP_ALIGN.CENTER,
    )


# ======================================================================
# Two-Column Helpers
# ======================================================================

def two_column_headers(slide, left_label: str, right_label: str, theme,
                       *, y: float = 1.8):
    """Render column headers and return the column positions."""
    cols = Grid.columns_layout(2, gap=0.8)

    for i, label in enumerate((left_label, right_label)):
        add_text_box(
            slide, label,
            Inches(cols[i][0]), Inches(y),
            Inches(cols[i][1]), Inches(0.7),
            theme.font_heading, Typography.SUBHEADING - 4, bold=True,
            color=theme.primary, align=PP_ALIGN.CENTER,
        )
    return cols


# ======================================================================
# Highlight Box
# ======================================================================

def highlight_box(slide, theme, *, label: str, text: str,
                  y: float = 5.4, height: float = 1.4):
    """Coloured highlight box with label and body (e.g. key takeaway)."""
    left, width = Grid.full_width()
    bg = slide.shapes.add_shape(
        1, Inches(left), Inches(y), Inches(width), Inches(height),
    )
    bg.fill.solid()
    bg.fill.fore_color.rgb = hex_to_rgb(theme.primary)
    bg.line.fill.background()

    inner_left = left + Spacing.ELEMENT
    inner_w = width - 2 * Spacing.ELEMENT

    add_text_box(
        slide, label,
        Inches(inner_left), Inches(y + Spacing.TIGHT),
        Inches(inner_w), Inches(0.4),
        theme.font_heading, Typography.CAPTION, bold=True,
        color=theme.background, align=PP_ALIGN.LEFT,
    )
    add_text_box(
        slide, text,
        Inches(inner_left), Inches(y + Spacing.TIGHT + 0.45),
        Inches(inner_w), Inches(height - 0.65),
        theme.font_body, Typography.BODY, bold=False,
        color=theme.background, align=PP_ALIGN.LEFT,
    )
