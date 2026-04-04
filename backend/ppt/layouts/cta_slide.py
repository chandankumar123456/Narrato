"""CTA slide — HERO layout with full-bleed primary background."""

from pptx.enum.text import PP_ALIGN  # type: ignore

from ppt.generator import set_background
from ppt.components import (
    accent_bar_top, accent_bar_bottom, hero_text,
    body_text, divider_line, caption_text,
)
from ppt.design_system import Grid, Spacing, Typography, VStack


def render(slide, content: dict, theme, image_path=None):
    # Full-bleed primary background
    set_background(slide, theme.primary)

    # Decorative: top accent bar
    accent_bar_top(slide, theme, height=0.10)

    flow = VStack(start_y=Spacing.XXL + Spacing.XL)

    # PRIMARY: Hero title — dominant element
    y_title = flow.next(height=1.6)
    hero_text(
        slide, content.get("title", "Get Started"), theme,
        y=y_title, color=theme.background,
    )

    # SECONDARY: CTA text — 8-col centred
    y_cta = flow.next(height=1.0, gap=Spacing.LG)
    left, width = Grid.center(8)
    body_text(
        slide, content.get("cta_text", ""), theme,
        left=left, y=y_cta, width=width, height=1.0,
        size=Typography.SUBHEADING, color=theme.background,
        align=PP_ALIGN.CENTER,
    )

    # Decorative: centred divider
    y_div = flow.next(height=0.05, gap=Spacing.LG)
    divider_line(slide, theme, y=y_div, span=3)

    # TERTIARY: Contact
    y_contact = flow.next(height=0.45, gap=Spacing.MD)
    caption_text(
        slide, content.get("contact", ""), theme,
        y=y_contact, color=theme.background,
    )

    # Decorative: bottom accent bar
    accent_bar_bottom(slide, theme)
