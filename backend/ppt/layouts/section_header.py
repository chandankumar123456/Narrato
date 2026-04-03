"""Section header — HERO layout for section transitions."""

from pptx.enum.text import PP_ALIGN  # type: ignore

from ppt.components import hero_text, divider_line, body_text
from ppt.design_system import Grid, Spacing, Typography, VStack


def render(slide, content: dict, theme, image_path=None):
    flow = VStack(start_y=Spacing.XXL + Spacing.XL)

    # PRIMARY: Hero section title — dominant, centred
    y_title = flow.next(height=1.6)
    hero_text(slide, content.get("section_title", ""), theme, y=y_title)

    # Decorative: centred accent divider
    y_div = flow.next(height=0.05, gap=Spacing.LG)
    divider_line(slide, theme, y=y_div, span=3)

    # SECONDARY: Tagline — 8-col span, centred
    y_tag = flow.next(height=0.8, gap=Spacing.MD)
    left, width = Grid.center(8)
    body_text(
        slide, content.get("tagline", ""), theme,
        left=left, y=y_tag, width=width, height=0.8,
        size=Typography.BODY, color=theme.secondary,
        align=PP_ALIGN.CENTER,
    )
