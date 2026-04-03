from ppt.components import (
    heading_block, accent_underline, card as render_card,
)
from ppt.design_system import Grid, VLayout


def render(slide, content: dict, theme, image_path=None):
    # Title
    heading_block(slide, content.get("title", ""), theme)

    # Accent underline
    accent_underline(slide, theme)

    # Up to 3 cards via grid-based card layout
    cards_data = content.get("cards", [])[:3]
    if not cards_data:
        return

    positions = Grid.card_layout(len(cards_data), gap=0.5)
    card_y = VLayout.CONTENT_START + 0.1
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
