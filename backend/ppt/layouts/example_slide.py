from pptx.util import Inches, Pt  # type: ignore
from pptx.enum.text import PP_ALIGN  # type: ignore
from ppt.generator import add_text_box, hex_to_rgb, set_background


def render(slide, content: dict, theme, image_path=None):
    # Title
    add_text_box(
        slide, content.get("title", "Case Study"),
        Inches(0.8), Inches(0.4), Inches(11.73), Inches(0.9),
        theme.font_heading, theme.heading_size, bold=True,
        color=theme.primary, align=PP_ALIGN.LEFT,
    )

    # Accent underline
    bar = slide.shapes.add_shape(1, Inches(0.8), Inches(1.25), Inches(1.5), Inches(0.06))
    bar.fill.solid()
    bar.fill.fore_color.rgb = hex_to_rgb(theme.accent)
    bar.line.fill.background()

    # Example title
    add_text_box(
        slide, content.get("example_title", ""),
        Inches(0.8), Inches(1.7), Inches(11.73), Inches(0.7),
        theme.font_heading, 24, bold=True,
        color=theme.secondary, align=PP_ALIGN.LEFT,
    )

    # Context section
    add_text_box(
        slide, "Context",
        Inches(0.8), Inches(2.6), Inches(5.5), Inches(0.5),
        theme.font_heading, 16, bold=True,
        color=theme.accent, align=PP_ALIGN.LEFT,
    )
    add_text_box(
        slide, content.get("context", ""),
        Inches(0.8), Inches(3.1), Inches(5.5), Inches(1.5),
        theme.font_body, 15, bold=False,
        color=theme.text, align=PP_ALIGN.LEFT,
    )

    # Result section
    add_text_box(
        slide, "Result",
        Inches(7.0), Inches(2.6), Inches(5.5), Inches(0.5),
        theme.font_heading, 16, bold=True,
        color=theme.accent, align=PP_ALIGN.LEFT,
    )
    add_text_box(
        slide, content.get("result", ""),
        Inches(7.0), Inches(3.1), Inches(5.5), Inches(1.5),
        theme.font_body, 15, bold=False,
        color=theme.text, align=PP_ALIGN.LEFT,
    )

    # Takeaway box
    takeaway_bg = slide.shapes.add_shape(
        1, Inches(0.8), Inches(5.2), Inches(11.73), Inches(1.5),
    )
    takeaway_bg.fill.solid()
    takeaway_bg.fill.fore_color.rgb = hex_to_rgb(theme.primary)
    takeaway_bg.line.fill.background()

    add_text_box(
        slide, "Key Takeaway",
        Inches(1.2), Inches(5.3), Inches(10.93), Inches(0.5),
        theme.font_heading, 14, bold=True,
        color=theme.background, align=PP_ALIGN.LEFT,
    )
    add_text_box(
        slide, content.get("takeaway", ""),
        Inches(1.2), Inches(5.8), Inches(10.93), Inches(0.8),
        theme.font_body, 16, bold=False,
        color=theme.background, align=PP_ALIGN.LEFT,
    )
