"""Conclusion slide — STACKED FLOW with bullets + highlight box."""

from ppt.components import (
    heading_block, accent_underline, bullet_group, highlight_box,
)
from ppt.design_system import Spacing, VLayout, VStack


def render(slide, content: dict, theme, image_path=None):
    # PRIMARY: Title heading
    heading_block(slide, content.get("title", "Conclusion"), theme)

    # Decorative: accent underline
    accent_underline(slide, theme)

    # SECONDARY: Bullet points
    bullets = content.get("bullets", [])
    bullet_group(
        slide, bullets, theme,
        start_y=VLayout.CONTENT_START,
        gap=Spacing.MD,
    )

    # SECONDARY: Key takeaway highlight box via VStack overflow check
    takeaway = content.get("key_takeaway", "")
    if takeaway:
        # Calculate where bullets end using shared item height constant
        bullet_end = VLayout.CONTENT_START + len(bullets) * (VStack.ITEM_HEIGHT + Spacing.MD)
        box_y = max(bullet_end + Spacing.LG, VLayout.CONTENT_END - 1.4)
        # Ensure it doesn't exceed bottom limit
        box_y = min(box_y, VLayout.CONTENT_END - 1.3)
        highlight_box(
            slide, theme,
            label="Key Takeaway",
            text=takeaway,
            y=box_y,
            height=1.3,
        )
