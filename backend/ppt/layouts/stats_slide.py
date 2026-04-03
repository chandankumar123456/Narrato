from pptx.util import Inches, Pt  # type: ignore
from pptx.enum.text import PP_ALIGN  # type: ignore
from ppt.generator import add_text_box, hex_to_rgb, set_background


def render(slide, content: dict, theme, image_path=None):
    # Title
    add_text_box(
        slide, content.get("title", ""),
        Inches(0.8), Inches(0.4), Inches(11.73), Inches(0.9),
        theme.font_heading, theme.heading_size, bold=True,
        color=theme.primary, align=PP_ALIGN.LEFT,
    )

    # Hero stat – large centered number
    add_text_box(
        slide, content.get("stat", ""),
        Inches(1), Inches(2.0), Inches(11.33), Inches(2.0),
        theme.font_heading, 72, bold=True,
        color=theme.accent, align=PP_ALIGN.CENTER,
    )

    # Stat label
    add_text_box(
        slide, content.get("stat_label", ""),
        Inches(1), Inches(3.9), Inches(11.33), Inches(0.7),
        theme.font_body, 24, bold=False,
        color=theme.secondary, align=PP_ALIGN.CENTER,
    )

    # Thin divider line
    divider = slide.shapes.add_shape(
        1, Inches(5.67), Inches(4.75), Inches(2), Inches(0.04),
    )
    divider.fill.solid()
    divider.fill.fore_color.rgb = hex_to_rgb(theme.accent)
    divider.line.fill.background()

    # Description
    add_text_box(
        slide, content.get("description", ""),
        Inches(2), Inches(5.0), Inches(9.33), Inches(1.0),
        theme.font_body, 16, bold=False,
        color=theme.text, align=PP_ALIGN.CENTER,
    )

    # Source
    source = content.get("source", "")
    if source:
        add_text_box(
            slide, f"Source: {source}",
            Inches(2), Inches(6.3), Inches(9.33), Inches(0.5),
            theme.font_body, 12, bold=False,
            color=theme.secondary, align=PP_ALIGN.CENTER,
        )