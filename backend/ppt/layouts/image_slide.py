import os
from pptx.util import Inches, Pt  # type: ignore
from pptx.enum.text import PP_ALIGN  # type: ignore
from ppt.generator import add_text_box, hex_to_rgb, set_background


def render(slide, content: dict, theme, image_path=None):
    # Add image if provided and exists
    if image_path and os.path.isfile(image_path):
        slide.shapes.add_picture(
            image_path, Inches(0), Inches(0), Inches(13.33), Inches(7.5),
        )

    # Semi-transparent overlay bar at bottom
    overlay = slide.shapes.add_shape(
        1, Inches(0), Inches(5.0), Inches(13.33), Inches(2.5),
    )
    overlay.fill.solid()
    overlay.fill.fore_color.rgb = hex_to_rgb(theme.primary)
    overlay.line.fill.background()

    # Title on overlay
    add_text_box(
        slide, content.get("title", ""),
        Inches(1), Inches(5.2), Inches(11.33), Inches(1.0),
        theme.font_heading, 32, bold=True,
        color=theme.background, align=PP_ALIGN.LEFT,
    )

    # Caption on overlay
    add_text_box(
        slide, content.get("caption", ""),
        Inches(1), Inches(6.2), Inches(11.33), Inches(0.8),
        theme.font_body, 18, bold=False,
        color=theme.background, align=PP_ALIGN.LEFT,
    )
