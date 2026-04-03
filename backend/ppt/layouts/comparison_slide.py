from pptx.util import Inches, Pt  # type: ignore
from pptx.enum.text import PP_ALIGN  # type: ignore
from ppt.generator import add_text_box, hex_to_rgb, set_background


def render(slide, content: dict, theme, image_path=None):
    # Title
    add_text_box(
        slide, content.get("title", ""),
        Inches(0.8), Inches(0.4), Inches(11.73), Inches(0.9),
        theme.font_heading, theme.heading_size, bold=True,
        color=theme.primary, align=PP_ALIGN.CENTER,
    )

    # Central vertical divider
    divider = slide.shapes.add_shape(
        1, Inches(6.6), Inches(1.6), Inches(0.06), Inches(5.2),
    )
    divider.fill.solid()
    divider.fill.fore_color.rgb = hex_to_rgb(theme.accent)
    divider.line.fill.background()

    # --- Left column ---
    add_text_box(
        slide, content.get("left_label", ""),
        Inches(0.8), Inches(1.6), Inches(5.5), Inches(0.7),
        theme.font_heading, 22, bold=True,
        color=theme.primary, align=PP_ALIGN.CENTER,
    )

    left_points = content.get("left_points", [])
    for i, point in enumerate(left_points):
        add_text_box(
            slide, f"•  {point}",
            Inches(1.2), Inches(2.5 + i * 0.75), Inches(4.8), Inches(0.65),
            theme.font_body, 16, bold=False,
            color=theme.text, align=PP_ALIGN.LEFT,
        )

    # --- Right column ---
    add_text_box(
        slide, content.get("right_label", ""),
        Inches(7.0), Inches(1.6), Inches(5.5), Inches(0.7),
        theme.font_heading, 22, bold=True,
        color=theme.primary, align=PP_ALIGN.CENTER,
    )

    right_points = content.get("right_points", [])
    for i, point in enumerate(right_points):
        add_text_box(
            slide, f"•  {point}",
            Inches(7.4), Inches(2.5 + i * 0.75), Inches(4.8), Inches(0.65),
            theme.font_body, 16, bold=False,
            color=theme.text, align=PP_ALIGN.LEFT,
        )
