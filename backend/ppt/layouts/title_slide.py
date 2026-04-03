from pptx.enum.text import PP_ALIGN  # type: ignore

from ppt.components import (
    accent_bar_top, accent_bar_bottom, hero_text, body_text, caption_text,
)
from ppt.design_system import Grid, Typography


def render(slide, content: dict, theme, image_path=None):
    # Top accent bar
    accent_bar_top(slide, theme)

    # Hero title — dominant element, centred
    hero_text(slide, content.get("title", ""), theme, y=2.2)

    # Subtitle
    left, width = Grid.center(8)
    body_text(
        slide, content.get("subtitle", ""), theme,
        left=left, y=4.2, width=width, height=0.8,
        size=Typography.SUBHEADING - 4, color=theme.secondary,
        align=PP_ALIGN.CENTER,
    )

    # Presenter
    caption_text(
        slide, content.get("presenter", ""), theme,
        y=5.5, color=theme.text,
    )

    # Bottom accent bar
    accent_bar_bottom(slide, theme)