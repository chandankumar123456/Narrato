from pptx.enum.text import PP_ALIGN  # type: ignore

from ppt.generator import set_background
from ppt.components import (
    accent_bar_top, accent_bar_bottom, hero_text,
    body_text, divider_line, caption_text,
)
from ppt.design_system import Grid, Spacing, Typography


def render(slide, content: dict, theme, image_path=None):
    # Full-bleed primary background
    set_background(slide, theme.primary)

    # Top accent bar
    accent_bar_top(slide, theme, height=0.10)

    # Hero title — dominant element
    hero_text(
        slide, content.get("title", "Get Started"), theme,
        y=2.0, color=theme.background,
    )

    # CTA text
    left, width = Grid.center(8)
    body_text(
        slide, content.get("cta_text", ""), theme,
        left=left, y=3.5, width=width, height=1.0,
        size=Typography.SUBHEADING - 4, color=theme.background,
        align=PP_ALIGN.CENTER,
    )

    # Centred divider
    divider_line(slide, theme, y=4.8)

    # Contact
    caption_text(
        slide, content.get("contact", ""), theme,
        y=5.2, color=theme.background,
    )

    # Bottom accent bar
    accent_bar_bottom(slide, theme)
