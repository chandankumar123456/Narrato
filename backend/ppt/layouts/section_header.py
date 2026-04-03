from pptx.util import Inches, Pt  # type: ignore
from pptx.enum.text import PP_ALIGN  # type: ignore
from ppt.generator import add_text_box, hex_to_rgb, set_background


def render(slide, content: dict, theme, image_path=None):
    # Centered section title
    add_text_box(
        slide, content.get("section_title", ""),
        Inches(1), Inches(2.6), Inches(11.33), Inches(1.5),
        theme.font_heading, 44, bold=True,
        color=theme.primary, align=PP_ALIGN.CENTER,
    )

    # Thin accent line below title
    bar = slide.shapes.add_shape(
        1, Inches(5.67), Inches(4.2), Inches(2), Inches(0.06),
    )
    bar.fill.solid()
    bar.fill.fore_color.rgb = hex_to_rgb(theme.accent)
    bar.line.fill.background()

    # Tagline
    add_text_box(
        slide, content.get("tagline", ""),
        Inches(2), Inches(4.6), Inches(9.33), Inches(0.8),
        theme.font_body, 20, bold=False,
        color=theme.secondary, align=PP_ALIGN.CENTER,
    )
