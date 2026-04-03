"""Quote slide — HERO layout with full-bleed background."""

from pptx.util import Inches  # type: ignore
from pptx.enum.text import PP_ALIGN  # type: ignore

from ppt.generator import add_text_box, set_background
from ppt.components import divider_line, body_text
from ppt.design_system import (
    ContentTransform, Grid, Spacing, Typography, VStack,
)


def render(slide, content: dict, theme, image_path=None):
    # Full-bleed primary background
    set_background(slide, theme.primary)

    flow = VStack(start_y=Spacing.XXL)

    # Decorative: large opening quotation mark
    y_mark = flow.next(height=1.5)
    left_mark, _ = Grid.compute(2, offset=0)
    add_text_box(
        slide, "\u201C",
        Inches(left_mark), Inches(y_mark),
        Inches(Grid.span_width(2)), Inches(1.5),
        theme.font_heading, 96, bold=True,
        color=theme.accent, align=PP_ALIGN.LEFT,
    )

    # PRIMARY: Quote text — 9-col centred
    y_quote = flow.next(height=2.8, gap=Spacing.XS)
    q_left, q_width = Grid.center(9)
    raw_quote = content.get("quote", "")
    display = ContentTransform.truncate(raw_quote, max_words=30)
    body_text(
        slide, display, theme,
        left=q_left, y=y_quote, width=q_width, height=2.8,
        size=Typography.SUBHEADING, color=theme.background,
    )

    # Decorative: accent divider
    y_div = flow.next(height=0.05, gap=Spacing.LG)
    divider_line(slide, theme, y=y_div, span=3, center=False)

    # SECONDARY: Attribution
    y_attr = flow.next(height=0.6, gap=Spacing.MD)
    add_text_box(
        slide, content.get("attribution", ""),
        Inches(Grid.MARGIN + Spacing.SM), Inches(y_attr),
        Inches(Grid.USABLE_WIDTH), Inches(0.6),
        theme.font_body, Typography.BODY, bold=True,
        color=theme.background, align=PP_ALIGN.LEFT,
    )
