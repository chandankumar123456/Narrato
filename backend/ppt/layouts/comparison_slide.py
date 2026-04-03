from pptx.util import Inches  # type: ignore
from pptx.enum.text import PP_ALIGN  # type: ignore

from ppt.generator import add_text_box
from ppt.components import (
    heading_block, vertical_divider, two_column_headers, bullet_group,
)
from ppt.design_system import Grid, Spacing, Typography, VLayout


def render(slide, content: dict, theme, image_path=None):
    # Title — centred for comparison slides
    heading_block(
        slide, content.get("title", ""), theme,
        align=PP_ALIGN.CENTER,
    )

    # Column headers + vertical divider
    cols = two_column_headers(
        slide,
        content.get("left_label", ""),
        content.get("right_label", ""),
        theme,
        y=VLayout.CONTENT_START - 0.1,
    )
    vertical_divider(slide, theme, y=VLayout.CONTENT_START - 0.1, height=4.8)

    # Left bullet points
    left_points = content.get("left_points", [])
    bullet_group(
        slide, left_points, theme,
        left=cols[0][0] + Spacing.TIGHT,
        start_y=VLayout.CONTENT_START + Spacing.SECTION,
        width=cols[0][1] - Spacing.TIGHT,
        size=Typography.BODY - 2,
    )

    # Right bullet points
    right_points = content.get("right_points", [])
    bullet_group(
        slide, right_points, theme,
        left=cols[1][0] + Spacing.TIGHT,
        start_y=VLayout.CONTENT_START + Spacing.SECTION,
        width=cols[1][1] - Spacing.TIGHT,
        size=Typography.BODY - 2,
    )
