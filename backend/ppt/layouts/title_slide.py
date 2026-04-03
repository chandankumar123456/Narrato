from pptx.util import Inches, Pt # type: ignore
from pptx.enum.text import PP_ALIGN # type: ignore
from ppt.generator import add_text_box, hex_to_rgb, set_background

def render(slide, content: dict, theme, image_path=None):
    # Accent bar at top
    bar = slide.shapes.add_shape(1, Inches(0), Inches(0), Inches(13.33), Inches(0.12))
    bar.fill.solid()
    bar.fill.fore_color.rgb = hex_to_rgb(theme.primary)
    bar.line.fill.background()

    # Title
    add_text_box(
        slide, content.get("title", ""),
        Inches(1), Inches(2.5), Inches(11.33), Inches(1.8),
        theme.font_heading, 48, bold=True,
        color=theme.primary, align=PP_ALIGN.CENTER
    )

    # Subtitle
    add_text_box(
        slide, content.get("subtitle", ""),
        Inches(1.5), Inches(4.4), Inches(10.33), Inches(0.8),
        theme.font_body, 24, bold=False,
        color=theme.secondary, align=PP_ALIGN.CENTER
    )

    # Presenter
    add_text_box(
        slide, content.get("presenter", ""),
        Inches(1.5), Inches(5.5), Inches(10.33), Inches(0.5),
        theme.font_body, 16, bold=False,
        color=theme.text, align=PP_ALIGN.CENTER
    )

    # Accent bar at bottom
    bar2 = slide.shapes.add_shape(1, Inches(0), Inches(7.35), Inches(13.33), Inches(0.15))
    bar2.fill.solid()
    bar2.fill.fore_color.rgb = hex_to_rgb(theme.accent)
    bar2.line.fill.background()