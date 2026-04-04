"""Feature slide — GRID/CARDS layout for feature cards."""

from ppt.components import (
    heading_block, accent_underline, card as render_card,
)
from ppt.design_system import Grid, Spacing, VLayout


def render(slide, content: dict, theme, image_path=None):
    # PRIMARY: Title heading
    heading_block(slide, content.get("title", "Features"), theme)

    # Decorative: accent underline
    accent_underline(slide, theme)

    # SECONDARY: Feature cards via grid layout
    features = content.get("features", [])[:4]
    if not features:
        return

    positions = Grid.card_layout(len(features), gap=Spacing.MD)
    card_y = VLayout.CONTENT_START
    card_h = VLayout.CONTENT_END - card_y

    for (x, w), feat in zip(positions, features):
        render_card(
            slide, theme,
            left=x, y=card_y, width=w, height=card_h,
            icon=feat.get("icon", "●"),
            label=feat.get("label", ""),
            description=feat.get("description", ""),
        )