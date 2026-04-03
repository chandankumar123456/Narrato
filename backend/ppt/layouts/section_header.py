from pptx.enum.text import PP_ALIGN  # type: ignore

from ppt.components import hero_text, divider_line, body_text
from ppt.design_system import Grid, Typography


def render(slide, content: dict, theme, image_path=None):
    # Hero section title — dominant, centred
    hero_text(
        slide, content.get("section_title", ""), theme,
        y=2.4,
    )

    # Centred accent divider
    divider_line(slide, theme, y=4.1)

    # Tagline
    left, width = Grid.center(8)
    body_text(
        slide, content.get("tagline", ""), theme,
        left=left, y=4.5, width=width, height=0.8,
        size=Typography.BODY, color=theme.secondary,
        align=PP_ALIGN.CENTER,
    )
