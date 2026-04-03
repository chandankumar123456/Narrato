from ppt.components import (
    accent_bar_top, accent_bar_bottom, hero_text, divider_line,
    body_text, caption_text,
)
from pptx.enum.text import PP_ALIGN  # type: ignore

from ppt.design_system import Grid, Typography


def render(slide, content: dict, theme, image_path=None):
    # Top accent bar
    accent_bar_top(slide, theme)

    # Hero title — dominant element
    hero_text(
        slide, content.get("title", "Thank You"), theme,
        y=2.2,
    )

    # Centred accent divider
    divider_line(slide, theme, y=3.9)

    # Message
    left, width = Grid.center(8)
    body_text(
        slide, content.get("message", ""), theme,
        left=left, y=4.3, width=width, height=1.0,
        size=Typography.BODY + 2, color=theme.secondary,
        align=PP_ALIGN.CENTER,
    )

    # Contact
    caption_text(
        slide, content.get("contact", ""), theme,
        y=5.6, color=theme.text,
    )

    # Bottom accent bar
    accent_bar_bottom(slide, theme)
