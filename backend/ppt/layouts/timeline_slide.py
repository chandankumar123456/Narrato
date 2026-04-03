"""Timeline slide — horizontal timeline with grid-derived positions."""

from pptx.util import Inches  # type: ignore
from pptx.enum.text import PP_ALIGN  # type: ignore

from ppt.generator import add_text_box, hex_to_rgb
from ppt.components import heading_block
from ppt.design_system import Grid, Spacing, Typography, VLayout


def render(slide, content: dict, theme, image_path=None):
    # PRIMARY: Title heading
    heading_block(slide, content.get("title", ""), theme)

    events = content.get("events", [])[:6]
    if not events:
        return

    count = len(events)
    usable_w = Grid.USABLE_WIDTH
    start_x = Grid.MARGIN
    step = usable_w / max(count - 1, 1) if count > 1 else 0
    line_y = 3.8

    # Decorative: horizontal timeline
    line = slide.shapes.add_shape(
        1, Inches(start_x), Inches(line_y),
        Inches(usable_w), Inches(0.05),
    )
    line.fill.solid()
    line.fill.fore_color.rgb = hex_to_rgb(theme.secondary)
    line.line.fill.background()

    # Sizing from grid:  wider labels when fewer events
    dot_size = Spacing.MD + Spacing.XS      # 0.375"
    # Wider labels for fewer events (2 cols), narrower for many (1 col + gutter)
    label_w = Grid.span_width(2) if count <= 4 else Grid.span_width(1) + Grid.GUTTER

    for i, event in enumerate(events):
        cx = start_x + i * step if count > 1 else start_x + usable_w / 2

        # Decorative: accent dot at intersection
        dot = slide.shapes.add_shape(
            1, Inches(cx - dot_size / 2),
            Inches(line_y - dot_size / 2 + 0.025),
            Inches(dot_size), Inches(dot_size),
        )
        dot.fill.solid()
        dot.fill.fore_color.rgb = hex_to_rgb(theme.accent)
        dot.line.fill.background()

        # SECONDARY: Year above
        add_text_box(
            slide, event.get("year", ""),
            Inches(cx - label_w / 2), Inches(line_y - 1.1),
            Inches(label_w), Inches(0.7),
            theme.font_heading, Typography.BODY, bold=True,
            color=theme.primary, align=PP_ALIGN.CENTER,
        )

        # TERTIARY: Label below
        add_text_box(
            slide, event.get("label", ""),
            Inches(cx - label_w / 2), Inches(line_y + Spacing.MD + Spacing.SM),
            Inches(label_w), Inches(1.5),
            theme.font_body, Typography.CAPTION, bold=False,
            color=theme.text, align=PP_ALIGN.CENTER,
        )
