"""Example / case study slide — TWO-COLUMN (Context | Result) + highlight."""

from pptx.util import Inches  # type: ignore
from pptx.enum.text import PP_ALIGN  # type: ignore

from ppt.generator import add_text_box
from ppt.components import (
    heading_block, accent_underline, subheading_text, body_text,
    highlight_box,
)
from ppt.design_system import (
    ContentTransform, Grid, Spacing, Typography, VLayout, VStack,
)


def render(slide, content: dict, theme, image_path=None):
    # PRIMARY: Title heading
    heading_block(slide, content.get("title", "Case Study"), theme)

    # Decorative: accent underline
    accent_underline(slide, theme)

    # SECONDARY: Example subtitle
    subheading_text(
        slide, content.get("example_title", ""), theme,
        y=VLayout.ACCENT_Y + Spacing.MD,
        color=theme.secondary,
    )

    # SECONDARY: Two-column Context / Result via Grid.split(6, 6)
    cols = Grid.split(6, 6)
    section_y = VLayout.CONTENT_START + Spacing.LG

    for i, (label, key) in enumerate([("Context", "context"), ("Result", "result")]):
        col_left, col_w = cols[i]

        # Section label (TERTIARY)
        add_text_box(
            slide, label,
            Inches(col_left + Spacing.SM), Inches(section_y),
            Inches(col_w - Spacing.SM), Inches(0.5),
            theme.font_heading, Typography.CAPTION + 2, bold=True,
            color=theme.accent, align=PP_ALIGN.LEFT,
        )

        # Section body
        raw = content.get(key, "")
        display = ContentTransform.truncate(raw, max_words=30)
        body_text(
            slide, display, theme,
            left=col_left + Spacing.SM,
            y=section_y + 0.5 + Spacing.SM,
            width=col_w - Spacing.SM,
            height=1.5,
            size=Typography.BODY, color=theme.text,
        )

    # SECONDARY: Key takeaway highlight box
    highlight_box(
        slide, theme,
        label="Key Takeaway",
        text=content.get("takeaway", ""),
        y=VLayout.CONTENT_END - 1.3,
        height=1.3,
    )
