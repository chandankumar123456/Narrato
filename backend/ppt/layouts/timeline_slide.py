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

    events = content.get("events", [])[:6]
    if not events:
        return

    count = len(events)
    usable_w = 11.0
    start_x = 1.17
    spacing = usable_w / max(count - 1, 1) if count > 1 else 0
    line_y = 3.8

    # Horizontal line
    line = slide.shapes.add_shape(
        1, Inches(start_x), Inches(line_y), Inches(usable_w), Inches(0.05),
    )
    line.fill.solid()
    line.fill.fore_color.rgb = hex_to_rgb(theme.secondary)
    line.line.fill.background()

    for i, event in enumerate(events):
        cx = start_x + i * spacing if count > 1 else start_x + usable_w / 2

        # Dot on timeline
        dot_size = 0.28
        dot = slide.shapes.add_shape(
            1, Inches(cx - dot_size / 2), Inches(line_y - dot_size / 2 + 0.025),
            Inches(dot_size), Inches(dot_size),
        )
        dot.fill.solid()
        dot.fill.fore_color.rgb = hex_to_rgb(theme.accent)
        dot.line.fill.background()

        # Year above dot
        add_text_box(
            slide, event.get("year", ""),
            Inches(cx - 0.8), Inches(line_y - 1.1), Inches(1.6), Inches(0.7),
            theme.font_heading, 18, bold=True,
            color=theme.primary, align=PP_ALIGN.CENTER,
        )

        # Label below dot
        add_text_box(
            slide, event.get("label", ""),
            Inches(cx - 0.9), Inches(line_y + 0.5), Inches(1.8), Inches(1.5),
            theme.font_body, 13, bold=False,
            color=theme.text, align=PP_ALIGN.CENTER,
        )
