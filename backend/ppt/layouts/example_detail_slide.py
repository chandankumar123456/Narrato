"""Example detail slide - renders user-specified fields as labeled rows.

Used in strict mode to display one example with exactly the fields the
user requested (e.g. name, origin, history).
"""

from pptx.util import Inches  # type: ignore
from pptx.enum.text import PP_ALIGN  # type: ignore

from ppt.generator import add_text_box
from ppt.components import heading_block, accent_underline, body_text
from ppt.design_system import (
    ContentTransform, Grid, Spacing, Typography, VLayout, VStack,
)


def render(slide, content: dict, theme, image_path=None):
    """Render an example detail slide.

    Expected *content* keys:
        - ``name``  (str): example name shown as the slide title
        - any number of user-specified fields (str): displayed as
          labelled rows below the title
    """

    name = content.get("name", "Example")

    # PRIMARY: Example name as heading
    heading_block(slide, name, theme)

    # Decorative accent
    accent_underline(slide, theme)

    # Determine which keys are user fields (everything except 'name')
    field_keys = [k for k in content if k != "name"]

    if not field_keys:
        return

    flow = VStack(start_y=VLayout.CONTENT_START)
    left, width = Grid.full_width()

    for key in field_keys:
        raw_value = content.get(key, "")
        display_value = ContentTransform.truncate(str(raw_value), max_words=12)
        label = key.replace("_", " ").title()

        if not flow.fits(1.0):
            break

        # Field label (TERTIARY)
        y_label = flow.next(height=0.4, gap=Spacing.ELEMENT)
        add_text_box(
            slide, label,
            Inches(left), Inches(y_label), Inches(width), Inches(0.4),
            theme.font_heading, Typography.CAPTION + 2, bold=True,
            color=theme.accent, align=PP_ALIGN.LEFT,
        )

        # Field value
        y_value = flow.next(height=0.5, gap=Spacing.TIGHT)
        body_text(
            slide, display_value, theme,
            left=left, y=y_value, width=width, height=0.5,
            size=Typography.BODY, color=theme.text,
        )
