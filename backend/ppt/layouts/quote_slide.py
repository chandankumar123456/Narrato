from pptx.util import Inches  # type: ignore
from pptx.enum.text import PP_ALIGN  # type: ignore

from ppt.generator import add_text_box, set_background
from ppt.components import divider_line, body_text
from ppt.design_system import Grid, Spacing, Typography


def render(slide, content: dict, theme, image_path=None):
    # Full-bleed primary background
    set_background(slide, theme.primary)

    # Large opening quotation mark
    add_text_box(
        slide, "\u201C",
        Inches(Grid.MARGIN + Spacing.TIGHT), Inches(1.0),
        Inches(2), Inches(1.5),
        theme.font_heading, 96, bold=True,
        color=theme.accent, align=PP_ALIGN.LEFT,
    )

    # Quote text — centred horizontally using grid
    left, width = Grid.center(9)
    body_text(
        slide, content.get("quote", ""), theme,
        left=left, y=2.2, width=width, height=3.0,
        size=Typography.SUBHEADING - 2, color=theme.background,
    )

    # Accent divider
    divider_line(
        slide, theme,
        y=5.5, center=False, width=2.0,
    )

    # Attribution
    add_text_box(
        slide, content.get("attribution", ""),
        Inches(Grid.MARGIN + Spacing.TIGHT), Inches(5.8),
        Inches(Grid.USABLE_WIDTH), Inches(0.6),
        theme.font_body, Typography.BODY, bold=True,
        color=theme.background, align=PP_ALIGN.LEFT,
    )
