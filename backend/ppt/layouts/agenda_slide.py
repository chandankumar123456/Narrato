"""Agenda slide — numbered list, title + content layout."""

from pptx.util import Inches  # type: ignore
from pptx.enum.text import PP_ALIGN  # type: ignore

from ppt.generator import add_text_box
from ppt.components import accent_bar_top, accent_underline, heading_block
from ppt.design_system import (
    ContentTransform, Grid, Spacing, Typography, VLayout, VStack,
)


def render(slide, content: dict, theme, image_path=None):
    # Decorative: top accent bar
    accent_bar_top(slide, theme)

    # PRIMARY: Title heading
    heading_block(slide, content.get("title", "Agenda"), theme)

    # Decorative: accent underline
    accent_underline(slide, theme)

    # SECONDARY: Numbered agenda items via VStack flow
    items = ContentTransform.truncate_bullets(
        content.get("items", []), max_items=8, max_words=12,
    )
    num_left, _ = Grid.compute(1, offset=0)
    text_left, text_width = Grid.compute(10, offset=1)

    flow = VStack(start_y=VLayout.CONTENT_START)

    for i, item in enumerate(items):
        y = flow.next(height=0.6, gap=Spacing.MD if i > 0 else None)
        # Number label
        add_text_box(
            slide, f"{i + 1:02d}",
            Inches(num_left), Inches(y), Inches(Grid.span_width(1)), Inches(0.6),
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
