from pptx.enum.text import PP_ALIGN  # type: ignore

from ppt.components import (
    heading_block, stat_block, divider_line, body_text, caption_text,
)
from ppt.design_system import Grid, Spacing, Typography, VLayout


def render(slide, content: dict, theme, image_path=None):
    # Title
    heading_block(slide, content.get("title", ""), theme)

    # Hero stat — dominant visual element
    stat_block(
        slide,
        stat=content.get("stat", ""),
        label=content.get("stat_label", ""),
        theme=theme,
        y=2.0,
    )

    # Centred divider
    divider_line(slide, theme, y=4.6)

    # Description
    left, width = Grid.center(8)
    body_text(
        slide, content.get("description", ""), theme,
        left=left, y=4.9, width=width, height=1.0,
        size=Typography.BODY - 2, color=theme.text,
        align=PP_ALIGN.CENTER,
    )

    # Source attribution
    source = content.get("source", "")
    if source:
        caption_text(
            slide, f"Source: {source}", theme,
            y=6.2,
        )