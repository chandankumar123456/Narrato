"""
Design System for Narrato slide generation.

Provides grid-based layout, typography scale, and spacing abstractions
on top of python-pptx coordinates.  All positioning is derived from
systematic rules rather than manual values.
"""

from __future__ import annotations

from pptx.util import Inches, Pt  # type: ignore

# ---------------------------------------------------------------------------
# Slide Dimensions
# ---------------------------------------------------------------------------
SLIDE_WIDTH: float = 13.33   # inches  (16:9 widescreen)
SLIDE_HEIGHT: float = 7.5    # inches


# ---------------------------------------------------------------------------
# Typography Scale  (points)
# ---------------------------------------------------------------------------
class Typography:
    """Strict typographic hierarchy.

    Sizes satisfy a ≥1.5× contrast between adjacent levels.
    """

    HERO: int = 60            # 56-64 pt  → single key idea
    HEADING: int = 44         # 40-48 pt  → section headings
    SUBHEADING: int = 30      # 28-32 pt  → secondary headings
    BODY: int = 20            # 18-22 pt  → body text
    CAPTION: int = 14         # 14-16 pt  → captions / sources


# ---------------------------------------------------------------------------
# Spacing Scale  (inches)
# ---------------------------------------------------------------------------
class Spacing:
    """Consistent spacing system (values in **inches**)."""

    OUTER: float = 1.0        # Left/right page margins  (~72 px)
    SECTION: float = 0.75     # Between major sections    (~54 px)
    ELEMENT: float = 0.4      # Between elements          (~29 px)
    TIGHT: float = 0.2        # Compact spacing           (~14 px)

    # Vertical reference lines
    TOP_MARGIN: float = 0.6
    BOTTOM_LIMIT: float = 7.0


# ---------------------------------------------------------------------------
# 12-Column Grid
# ---------------------------------------------------------------------------
class Grid:
    """12-column grid with gutters.

    Every element position should be computed through this class instead
    of using hard-coded ``Inches(…)`` values.
    """

    COLUMNS: int = 12
    MARGIN: float = 1.0                                           # left & right
    GUTTER: float = 0.25                                          # between columns
    USABLE_WIDTH: float = SLIDE_WIDTH - 2 * MARGIN                # 11.33
    COL_WIDTH: float = (
        (USABLE_WIDTH - (COLUMNS - 1) * GUTTER) / COLUMNS        # ≈ 0.715
    )

    # ------------------------------------------------------------------
    @classmethod
    def col_left(cls, col: int) -> float:
        """Left position (inches) for 0-based column *col*."""
        return cls.MARGIN + col * (cls.COL_WIDTH + cls.GUTTER)

    @classmethod
    def span_width(cls, n: int) -> float:
        """Width (inches) when spanning *n* columns."""
        return n * cls.COL_WIDTH + max(n - 1, 0) * cls.GUTTER

    @classmethod
    def center(cls, span_cols: int) -> tuple[float, float]:
        """``(left, width)`` to centre *span_cols* columns."""
        width = cls.span_width(span_cols)
        left = cls.MARGIN + (cls.USABLE_WIDTH - width) / 2
        return left, width

    @classmethod
    def full_width(cls) -> tuple[float, float]:
        """``(left, width)`` for the full content area."""
        return cls.MARGIN, cls.USABLE_WIDTH

    @classmethod
    def columns_layout(
        cls, count: int, gap: float | None = None
    ) -> list[tuple[float, float]]:
        """Divide the content area into *count* equal columns.

        Returns ``[(left, width), …]``.
        """
        if gap is None:
            gap = cls.GUTTER * 3
        total_gap = (count - 1) * gap
        col_w = (cls.USABLE_WIDTH - total_gap) / count
        return [
            (cls.MARGIN + i * (col_w + gap), col_w)
            for i in range(count)
        ]

    @classmethod
    def card_layout(
        cls, count: int, gap: float = 0.5
    ) -> list[tuple[float, float]]:
        """Centre *count* cards with *gap* between them.

        Returns ``[(left, width), …]``.
        """
        total_gap = (count - 1) * gap
        card_w = (cls.USABLE_WIDTH - total_gap) / count
        # Cap width for aesthetic balance when few cards
        max_w = 5.0
        if card_w > max_w and count <= 2:
            card_w = max_w
        total_w = count * card_w + total_gap
        start_x = (SLIDE_WIDTH - total_w) / 2
        return [
            (start_x + i * (card_w + gap), card_w)
            for i in range(count)
        ]


# ---------------------------------------------------------------------------
# Vertical Layout Helpers
# ---------------------------------------------------------------------------
class VLayout:
    """Named vertical positions and distribution helpers."""

    TITLE_TOP: float = 0.6
    TITLE_HEIGHT: float = 0.9
    ACCENT_Y: float = 1.45            # just below title
    ACCENT_HEIGHT: float = 0.06
    CONTENT_START: float = 1.9        # first content row
    CONTENT_END: float = 6.8          # last usable row

    @classmethod
    def stack(
        cls,
        count: int,
        start_y: float | None = None,
        item_height: float = 0.6,
        gap: float | None = None,
    ) -> list[float]:
        """Return *count* y-positions stacked vertically."""
        if start_y is None:
            start_y = cls.CONTENT_START
        if gap is None:
            gap = Spacing.ELEMENT
        return [start_y + i * (item_height + gap) for i in range(count)]

    @classmethod
    def distribute(
        cls,
        count: int,
        start_y: float | None = None,
        end_y: float | None = None,
    ) -> list[float]:
        """Evenly distribute *count* items between *start_y* and *end_y*."""
        if start_y is None:
            start_y = cls.CONTENT_START
        if end_y is None:
            end_y = cls.CONTENT_END
        if count <= 1:
            return [start_y + (end_y - start_y) / 2]
        step = (end_y - start_y) / (count - 1)
        return [start_y + i * step for i in range(count)]
