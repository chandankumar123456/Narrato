from pptx.util import Inches  # type: ignore
from pptx.enum.text import PP_ALIGN  # type: ignore

from ppt.generator import add_text_box
from ppt.components import (
    accent_bar_top, accent_underline, heading_block,
)
from ppt.design_system import Grid, Spacing, Typography, VLayout


def render(slide, content: dict, theme, image_path=None):
    # Top accent bar
    accent_bar_top(slide, theme)

    # Title
    heading_block(slide, content.get("title", "Agenda"), theme)

    # Accent underline below title
    accent_underline(slide, theme)

    # Agenda items — numbered list using grid positioning
    items = content.get("items", [])
    num_left = Grid.MARGIN + Spacing.TIGHT
    text_left = Grid.col_left(1)
    text_width = Grid.span_width(10)
    positions = VLayout.stack(
        len(items), start_y=VLayout.CONTENT_START,
        item_height=0.6, gap=Spacing.ELEMENT + Spacing.TIGHT,
    )

    for i, item in enumerate(items):
        y = positions[i]
        # Number
        add_text_box(
            slide, f"{i + 1:02d}",
            Inches(num_left), Inches(y), Inches(0.6), Inches(0.6),
            theme.font_heading, Typography.BODY, bold=True,
            color=theme.accent, align=PP_ALIGN.CENTER,
        )
        # Item text
        add_text_box(
            slide, item,
            Inches(text_left), Inches(y), Inches(text_width), Inches(0.6),
            theme.font_body, Typography.BODY, bold=False,
            color=theme.text, align=PP_ALIGN.LEFT,
        )
