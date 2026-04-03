"""Problem slide — GRID/CARDS layout with accent-stripped cards."""

from ppt.components import (
    heading_block, accent_underline, card as render_card,
)
from ppt.design_system import Grid, Spacing, VLayout


def render(slide, content: dict, theme, image_path=None):
    # PRIMARY: Title heading
    heading_block(slide, content.get("title", ""), theme)

    # Decorative: accent underline
    accent_underline(slide, theme)

    # SECONDARY: Up to 3 cards via grid-based card layout
    cards_data = content.get("cards", [])[:3]
    if not cards_data:
        return

    positions = Grid.card_layout(len(cards_data), gap=Spacing.MD)
    card_y = VLayout.CONTENT_START + Spacing.XS
    card_h = VLayout.CONTENT_END - card_y

    for (x, w), c in zip(positions, cards_data):
        render_card(
            slide, theme,
            left=x, y=card_y, width=w, height=card_h,
            icon=c.get("icon", "●"),
            label=c.get("label", ""),
            description=c.get("description", ""),
            show_accent_strip=True,
        )
