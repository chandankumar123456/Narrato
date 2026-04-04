"""Title slide — HERO layout with dominant title."""

from pptx.enum.text import PP_ALIGN  # type: ignore

from ppt.components import (
    accent_bar_top, accent_bar_bottom, hero_text, body_text, caption_text,
)
from ppt.design_system import Grid, Spacing, Typography, VStack


def render(slide, content: dict, theme, image_path=None):
    # Decorative: top accent bar
    accent_bar_top(slide, theme)

    flow = VStack(start_y=Spacing.XXL + Spacing.XL)

    # PRIMARY: Hero title — dominant, centred, 10-col span
    y_title = flow.next(height=1.6)
    hero_text(slide, content.get("title", ""), theme, y=y_title, span=10)

    # SECONDARY: Subtitle — 8-col span, centred
    y_sub = flow.next(height=0.8, gap=Spacing.LG)
    left, width = Grid.center(8)
    body_text(
        slide, content.get("subtitle", ""), theme,
        left=left, y=y_sub, width=width, height=0.8,
        size=Typography.SUBHEADING, color=theme.secondary,
        align=PP_ALIGN.CENTER,
    )

    # TERTIARY: Presenter name
    y_pres = flow.next(height=0.45, gap=Spacing.LG)
    caption_text(slide, content.get("presenter", ""), theme,
                 y=y_pres, color=theme.text)

    # Decorative: bottom accent bar
    accent_bar_bottom(slide, theme)