"""Stats slide — STATS layout with dominant number as PRIMARY element."""

from pptx.enum.text import PP_ALIGN  # type: ignore

from ppt.components import (
    heading_block, stat_block, divider_line, body_text, caption_text,
)
from ppt.design_system import Grid, Spacing, Typography, VStack


def render(slide, content: dict, theme, image_path=None):
    # TERTIARY: Title heading (smaller role — stat is dominant)
    heading_block(slide, content.get("title", ""), theme)

    flow = VStack(start_y=Spacing.XXL + Spacing.XL)

    # PRIMARY: Hero stat — dominant visual element
    y_stat = flow.next(height=2.5)
    stat_block(
        slide,
        stat=content.get("stat", ""),
        label=content.get("stat_label", ""),
        theme=theme,
        y=y_stat,
        span=10,
    )

    # Decorative: centred divider
    y_div = flow.next(height=0.05, gap=Spacing.LG)
    divider_line(slide, theme, y=y_div, span=3)

    # SECONDARY: Description — 8-col centred
    y_desc = flow.next(height=1.0, gap=Spacing.MD)
    left, width = Grid.center(8)
    body_text(
        slide, content.get("description", ""), theme,
        left=left, y=y_desc, width=width, height=1.0,
        size=Typography.BODY, color=theme.text,
        align=PP_ALIGN.CENTER,
    )

    # TERTIARY: Source attribution
    source = content.get("source", "")
    if source and flow.fits(0.45):
        y_src = flow.next(height=0.45, gap=Spacing.MD)
        caption_text(slide, f"Source: {source}", theme, y=y_src)