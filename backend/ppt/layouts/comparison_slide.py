"""Comparison slide — TWO-COLUMN layout with Grid.split(6, 6)."""

from pptx.enum.text import PP_ALIGN  # type: ignore

from ppt.components import (
    heading_block, vertical_divider, two_column_headers, bullet_group,
)
from ppt.design_system import Grid, Spacing, Typography, VLayout


def render(slide, content: dict, theme, image_path=None):
    # PRIMARY: Title — centred for comparison slides
    heading_block(
        slide, content.get("title", ""), theme,
        align=PP_ALIGN.CENTER,
    )

    # SECONDARY: Column headers via Grid.split(6, 6)
    header_y = VLayout.CONTENT_START
    cols = two_column_headers(
        slide,
        content.get("left_label", ""),
        content.get("right_label", ""),
        theme,
        y=header_y,
    )

    # Decorative: vertical divider at grid centre
    vertical_divider(slide, theme, y=header_y)

    # TERTIARY: Left bullet points
    bullet_y = header_y + 0.7 + Spacing.MD
    left_points = content.get("left_points", [])
    bullet_group(
        slide, left_points, theme,
        left=cols[0][0] + Spacing.SM,
        start_y=bullet_y,
        width=cols[0][1] - Spacing.SM,
        size=Typography.BODY,
        gap=Spacing.SM,
    )

    # TERTIARY: Right bullet points
    right_points = content.get("right_points", [])
    bullet_group(
        slide, right_points, theme,
        left=cols[1][0] + Spacing.SM,
        start_y=bullet_y,
        width=cols[1][1] - Spacing.SM,
        size=Typography.BODY,
        gap=Spacing.SM,
    )
