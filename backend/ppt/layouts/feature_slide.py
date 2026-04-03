from pptx.util import Inches, Pt  # type: ignore
from pptx.enum.text import PP_ALIGN  # type: ignore
from ppt.generator import add_text_box, hex_to_rgb, set_background


def render(slide, content: dict, theme, image_path=None):
    # Title
    add_text_box(
        slide, content.get("title", "Features"),
        Inches(0.8), Inches(0.4), Inches(11.73), Inches(0.9),
        theme.font_heading, theme.heading_size, bold=True,
        color=theme.primary, align=PP_ALIGN.LEFT,
    )

    # Accent underline
    bar = slide.shapes.add_shape(1, Inches(0.8), Inches(1.25), Inches(1.5), Inches(0.06))
    bar.fill.solid()
    bar.fill.fore_color.rgb = hex_to_rgb(theme.accent)
    bar.line.fill.background()

    features = content.get("features", [])[:4]
    count = len(features) if features else 1
    cols = min(count, 4)
    card_w = 2.6
    gap = 0.35
    total_w = cols * card_w + (cols - 1) * gap
    start_x = (13.33 - total_w) / 2

    for i, feat in enumerate(features):
        x = start_x + i * (card_w + gap)
        y = 1.9

        # Card background
        card = slide.shapes.add_shape(1, Inches(x), Inches(y), Inches(card_w), Inches(4.8))
        card.fill.solid()
        card.fill.fore_color.rgb = hex_to_rgb(theme.background)
        card.line.color.rgb = hex_to_rgb(theme.secondary)
        card.line.width = Pt(1)

        # Icon/emoji
        add_text_box(
            slide, feat.get("icon", "●"),
            Inches(x), Inches(y + 0.4), Inches(card_w), Inches(0.7),
            theme.font_body, 28, bold=False,
            color=theme.accent, align=PP_ALIGN.CENTER,
        )

        # Feature label
        add_text_box(
            slide, feat.get("label", ""),
            Inches(x + 0.2), Inches(y + 1.2), Inches(card_w - 0.4), Inches(0.7),
            theme.font_heading, 18, bold=True,
            color=theme.primary, align=PP_ALIGN.CENTER,
        )

        # Feature description
        add_text_box(
            slide, feat.get("description", ""),
            Inches(x + 0.2), Inches(y + 2.0), Inches(card_w - 0.4), Inches(2.4),
            theme.font_body, 14, bold=False,
            color=theme.text, align=PP_ALIGN.CENTER,
        )