from pptx.util import Inches  # type: ignore
from pptx.enum.text import PP_ALIGN  # type: ignore

from ppt.generator import add_text_box
from ppt.components import (
    heading_block, accent_underline, subheading_text, body_text,
    highlight_box,
)
from ppt.design_system import Grid, Spacing, Typography, VLayout


def render(slide, content: dict, theme, image_path=None):
    # Title
    heading_block(slide, content.get("title", "Case Study"), theme)

    # Accent underline
    accent_underline(slide, theme)

    # Example subtitle
    subheading_text(
        slide, content.get("example_title", ""), theme,
        y=VLayout.ACCENT_Y + Spacing.ELEMENT,
        color=theme.secondary,
    )

    # Two-column: Context / Result  (grid-based)
    cols = Grid.columns_layout(2, gap=0.8)
    section_y = VLayout.CONTENT_START + Spacing.SECTION

    for i, (label, key) in enumerate([("Context", "context"), ("Result", "result")]):
        col_left, col_w = cols[i]

        # Section label
        add_text_box(
            slide, label,
            Inches(col_left), Inches(section_y),
            Inches(col_w), Inches(0.5),
            theme.font_heading, Typography.CAPTION + 2, bold=True,
            color=theme.accent, align=PP_ALIGN.LEFT,
        )

        # Section body
        body_text(
            slide, content.get(key, ""), theme,
            left=col_left, y=section_y + 0.5 + Spacing.TIGHT,
            width=col_w, height=1.5,
            size=Typography.BODY - 4, color=theme.text,
        )

    # Takeaway highlight box
    highlight_box(
        slide, theme,
        label="Key Takeaway",
        text=content.get("takeaway", ""),
        y=5.3,
        height=1.4,
    )
