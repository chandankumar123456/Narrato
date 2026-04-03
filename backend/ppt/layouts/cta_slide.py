from pptx.util import Inches, Pt  # type: ignore
from pptx.enum.text import PP_ALIGN  # type: ignore
from ppt.generator import add_text_box, hex_to_rgb, set_background


def render(slide, content: dict, theme, image_path=None):
    # Full-bleed primary background
    set_background(slide, theme.primary)

    # Top accent bar
    bar = slide.shapes.add_shape(1, Inches(0), Inches(0), Inches(13.33), Inches(0.1))
    bar.fill.solid()
    bar.fill.fore_color.rgb = hex_to_rgb(theme.accent)
    bar.line.fill.background()

    # Title
    add_text_box(
        slide, content.get("title", "Get Started"),
        Inches(1), Inches(2.0), Inches(11.33), Inches(1.2),
        theme.font_heading, 44, bold=True,
        color=theme.background, align=PP_ALIGN.CENTER,
    )

    # CTA text
    add_text_box(
        slide, content.get("cta_text", ""),
        Inches(1.5), Inches(3.5), Inches(10.33), Inches(1.0),
        theme.font_body, 24, bold=False,
        color=theme.background, align=PP_ALIGN.CENTER,
    )

    # Accent divider
    divider = slide.shapes.add_shape(
        1, Inches(5.67), Inches(4.8), Inches(2), Inches(0.06),
    )
    divider.fill.solid()
    divider.fill.fore_color.rgb = hex_to_rgb(theme.accent)
    divider.line.fill.background()

    # Contact info
    add_text_box(
        slide, content.get("contact", ""),
        Inches(1.5), Inches(5.2), Inches(10.33), Inches(0.8),
        theme.font_body, 18, bold=False,
        color=theme.background, align=PP_ALIGN.CENTER,
    )

    # Bottom accent bar
    bar2 = slide.shapes.add_shape(1, Inches(0), Inches(7.38), Inches(13.33), Inches(0.12))
    bar2.fill.solid()
    bar2.fill.fore_color.rgb = hex_to_rgb(theme.accent)
    bar2.line.fill.background()
