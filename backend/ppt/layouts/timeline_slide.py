from pptx.util import Inches  # type: ignore
from pptx.enum.text import PP_ALIGN  # type: ignore

from ppt.generator import add_text_box, hex_to_rgb
from ppt.components import heading_block
from ppt.design_system import Grid, Spacing, Typography, VLayout


def render(slide, content: dict, theme, image_path=None):
    # Title
    heading_block(slide, content.get("title", ""), theme)

    events = content.get("events", [])[:6]
    if not events:
        return

    count = len(events)
    usable_w = Grid.USABLE_WIDTH
    start_x = Grid.MARGIN
    spacing = usable_w / max(count - 1, 1) if count > 1 else 0
    line_y = 3.8

    # Horizontal timeline
    line = slide.shapes.add_shape(
        1, Inches(start_x), Inches(line_y),
        Inches(usable_w), Inches(0.05),
    )
    line.fill.solid()
    line.fill.fore_color.rgb = hex_to_rgb(theme.secondary)
    line.line.fill.background()

    # Dot and label sizing from grid
    dot_size = 0.3
    label_w = Grid.span_width(2) if count <= 4 else Grid.span_width(1) + Grid.GUTTER
    year_size = Typography.BODY
    label_size = Typography.CAPTION

    for i, event in enumerate(events):
        cx = start_x + i * spacing if count > 1 else start_x + usable_w / 2

        # Dot
        dot = slide.shapes.add_shape(
            1, Inches(cx - dot_size / 2), Inches(line_y - dot_size / 2 + 0.025),
            Inches(dot_size), Inches(dot_size),
        )
        dot.fill.solid()
        dot.fill.fore_color.rgb = hex_to_rgb(theme.accent)
        dot.line.fill.background()

        # Year above
        add_text_box(
            slide, event.get("year", ""),
            Inches(cx - label_w / 2), Inches(line_y - 1.1),
            Inches(label_w), Inches(0.7),
            theme.font_heading, year_size, bold=True,
            color=theme.primary, align=PP_ALIGN.CENTER,
        )

        # Label below
        add_text_box(
            slide, event.get("label", ""),
            Inches(cx - label_w / 2), Inches(line_y + Spacing.ELEMENT + Spacing.TIGHT),
            Inches(label_w), Inches(1.5),
            theme.font_body, label_size, bold=False,
            color=theme.text, align=PP_ALIGN.CENTER,
        )
