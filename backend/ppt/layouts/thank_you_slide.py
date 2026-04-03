"""Thank You slide — HERO layout with centred messaging."""

from ppt.components import (
    accent_bar_top, accent_bar_bottom, hero_text, divider_line,
    body_text, caption_text,
)
from pptx.enum.text import PP_ALIGN  # type: ignore

from ppt.design_system import Grid, Spacing, Typography, VStack


def render(slide, content: dict, theme, image_path=None):
    # Decorative: top accent bar
    accent_bar_top(slide, theme)

    flow = VStack(start_y=Spacing.XXL + Spacing.XL)

    # PRIMARY: Hero title — dominant element
    y_title = flow.next(height=1.6)
    hero_text(
        slide, content.get("title", "Thank You"), theme,
        y=y_title,
    )

    # Decorative: centred accent divider
    y_div = flow.next(height=0.05, gap=Spacing.LG)
    divider_line(slide, theme, y=y_div, span=3)

    # SECONDARY: Message — 8-col centred
    y_msg = flow.next(height=1.0, gap=Spacing.MD)
    left, width = Grid.center(8)
    body_text(
        slide, content.get("message", ""), theme,
        left=left, y=y_msg, width=width, height=1.0,
        size=Typography.BODY + 2, color=theme.secondary,
        align=PP_ALIGN.CENTER,
    )

    # TERTIARY: Contact
    y_contact = flow.next(height=0.45, gap=Spacing.LG)
    caption_text(
        slide, content.get("contact", ""), theme,
        y=y_contact, color=theme.text,
    )

    # Decorative: bottom accent bar
    accent_bar_bottom(slide, theme)
