from pptx.util import Inches, Pt  # type: ignore
from pptx.enum.text import PP_ALIGN  # type: ignore
from ppt.generator import add_text_box, hex_to_rgb, set_background


def render(slide, content: dict, theme, image_path=None):
    # Top accent bar
    bar = slide.shapes.add_shape(1, Inches(0), Inches(0), Inches(13.33), Inches(0.1))
    bar.fill.solid()
    bar.fill.fore_color.rgb = hex_to_rgb(theme.primary)
    bar.line.fill.background()

    # Title
    add_text_box(
        slide, content.get("title", "Agenda"),
        Inches(0.8), Inches(0.5), Inches(11.73), Inches(0.9),
        theme.font_heading, theme.heading_size, bold=True,
        color=theme.primary, align=PP_ALIGN.LEFT,
    )

    # Accent underline
    underline = slide.shapes.add_shape(
        1, Inches(0.8), Inches(1.35), Inches(1.5), Inches(0.06),
    )
    underline.fill.solid()
    underline.fill.fore_color.rgb = hex_to_rgb(theme.accent)
    underline.line.fill.background()

    # Agenda items
    items = content.get("items", [])
    start_y = 1.8
    for i, item in enumerate(items):
        # Number circle
        num_text = f"{i + 1:02d}"
        add_text_box(
            slide, num_text,
            Inches(1.0), Inches(start_y + i * 0.85), Inches(0.6), Inches(0.6),
            theme.font_heading, 18, bold=True,
            color=theme.accent, align=PP_ALIGN.CENTER,
        )
        # Item text
        add_text_box(
            slide, item,
            Inches(1.8), Inches(start_y + i * 0.85), Inches(9.5), Inches(0.6),
            theme.font_body, 20, bold=False,
            color=theme.text, align=PP_ALIGN.LEFT,
        )
