from ppt.components import (
    heading_block, accent_underline, bullet_group, highlight_box,
)
from ppt.design_system import Spacing, VLayout


def render(slide, content: dict, theme, image_path=None):
    # Title
    heading_block(slide, content.get("title", "Conclusion"), theme)

    # Accent underline
    accent_underline(slide, theme)

    # Bullet points
    bullets = content.get("bullets", [])
    bullet_group(
        slide, bullets, theme,
        start_y=VLayout.CONTENT_START,
    )

    # Key takeaway highlight box
    takeaway = content.get("key_takeaway", "")
    if takeaway:
        # Position box after bullets with section spacing, minimum y = 4.8
        gap = Spacing.ELEMENT + Spacing.TIGHT
        box_y = max(
            VLayout.CONTENT_START + len(bullets) * gap + Spacing.SECTION,
            4.8,
        )
        highlight_box(
            slide, theme,
            label="Key Takeaway",
            text=takeaway,
            y=box_y,
            height=1.4,
        )
