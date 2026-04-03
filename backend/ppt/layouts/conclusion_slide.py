from pptx.util import Inches, Pt  # type: ignore
from pptx.enum.text import PP_ALIGN  # type: ignore
from ppt.generator import add_text_box, hex_to_rgb, set_background


def render(slide, content: dict, theme, image_path=None):
    # Title
    add_text_box(
        slide, content.get("title", "Conclusion"),
        Inches(0.8), Inches(0.4), Inches(11.73), Inches(0.9),
        theme.font_heading, theme.heading_size, bold=True,
        color=theme.primary, align=PP_ALIGN.LEFT,
    )

    # Accent underline
    bar = slide.shapes.add_shape(1, Inches(0.8), Inches(1.25), Inches(1.5), Inches(0.06))
    bar.fill.solid()
    bar.fill.fore_color.rgb = hex_to_rgb(theme.accent)
    bar.line.fill.background()

    # Bullet points
    bullets = content.get("bullets", [])
    for i, bullet in enumerate(bullets):
        add_text_box(
            slide, f"•  {bullet}",
            Inches(1.2), Inches(1.8 + i * 0.7), Inches(10.5), Inches(0.6),
            theme.font_body, 18, bold=False,
            color=theme.text, align=PP_ALIGN.LEFT,
        )

    # Key takeaway highlight box
    takeaway = content.get("key_takeaway", "")
    if takeaway:
        box_y = max(1.8 + len(bullets) * 0.7 + 0.3, 4.6)
        bg = slide.shapes.add_shape(
            1, Inches(0.8), Inches(box_y), Inches(11.73), Inches(1.6),
        )
        bg.fill.solid()
        bg.fill.fore_color.rgb = hex_to_rgb(theme.primary)
        bg.line.fill.background()

        add_text_box(
            slide, "Key Takeaway",
            Inches(1.2), Inches(box_y + 0.15), Inches(10.93), Inches(0.4),
            theme.font_heading, 14, bold=True,
            color=theme.background, align=PP_ALIGN.LEFT,
        )
        add_text_box(
            slide, takeaway,
            Inches(1.2), Inches(box_y + 0.6), Inches(10.93), Inches(0.8),
            theme.font_body, 18, bold=False,
            color=theme.background, align=PP_ALIGN.LEFT,
        )
