from pptx.util import Inches, Pt  # type: ignore
from pptx.enum.text import PP_ALIGN  # type: ignore
from ppt.generator import add_text_box, hex_to_rgb, set_background


def render(slide, content: dict, theme, image_path=None):
    # Full-bleed primary background
    set_background(slide, theme.primary)

    # Large opening quotation mark
    add_text_box(
        slide, "\u201C",
        Inches(1.2), Inches(1.0), Inches(2), Inches(1.5),
        theme.font_heading, 96, bold=True,
        color=theme.accent, align=PP_ALIGN.LEFT,
    )

    # Quote text
    add_text_box(
        slide, content.get("quote", ""),
        Inches(1.8), Inches(2.2), Inches(9.73), Inches(3.0),
        theme.font_body, 28, bold=False,
        color=theme.background, align=PP_ALIGN.LEFT,
    )

    # Thin accent line
    bar = slide.shapes.add_shape(
        1, Inches(1.8), Inches(5.5), Inches(2), Inches(0.06),
    )
    bar.fill.solid()
    bar.fill.fore_color.rgb = hex_to_rgb(theme.accent)
    bar.line.fill.background()

    # Attribution
    add_text_box(
        slide, content.get("attribution", ""),
        Inches(1.8), Inches(5.8), Inches(9.73), Inches(0.6),
        theme.font_body, 18, bold=True,
        color=theme.background, align=PP_ALIGN.LEFT,
    )
