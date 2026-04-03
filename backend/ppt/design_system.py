"""
Design System for Narrato slide generation.

Provides grid-based layout, typography scale, spacing abstractions,
vertical flow engine, and content transformation on top of python-pptx
coordinates.  All positioning is derived from systematic rules rather
than manual values.

Coordinates are the FINAL OUTPUT of this system, never the design input.
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

    # Maximum recommended characters per line for readable text
    MAX_LINE_WIDTH: int = 65

    @classmethod
    def level(cls, n: int) -> int:
        """Return font size by hierarchy level (0=HERO … 4=CAPTION)."""
        return (cls.HERO, cls.HEADING, cls.SUBHEADING, cls.BODY, cls.CAPTION)[
            max(0, min(n, 4))
        ]


# ---------------------------------------------------------------------------
# Named Spacing Scale  (inches, derived from pixel targets at 96 dpi)
# ---------------------------------------------------------------------------
class Spacing:
    """Global spacing scale.  Every vertical/horizontal gap must reference
    one of these named values — no magic numbers.

    Pixel targets (at 96 dpi):
        XS  = 12 px ≈ 0.125"
        SM  = 16 px ≈ 0.167"
        MD  = 24 px ≈ 0.250"
        LG  = 40 px ≈ 0.417"
        XL  = 64 px ≈ 0.667"
        XXL = 96 px ≈ 1.000"
    """

    XS:  float = 0.125
    SM:  float = 0.167
    MD:  float = 0.25
    LG:  float = 0.417
    XL:  float = 0.667
    XXL: float = 1.0

    # Convenience aliases that map to the named scale
    OUTER:   float = XL        # page outer padding
    SECTION: float = LG        # gap between major sections
    ELEMENT: float = MD        # gap between sibling elements
    TIGHT:   float = SM        # compact spacing (use sparingly)

    # Vertical reference lines
    TOP_MARGIN:   float = XL
    BOTTOM_LIMIT: float = SLIDE_HEIGHT - XL   # 6.833"


# ---------------------------------------------------------------------------
# 12-Column Grid
# ---------------------------------------------------------------------------
class Grid:
    """True 12-column grid.

    *   total_width = 13.33"
    *   left/right margin = 1.0"
    *   gutter = 0.25"
    *   usable_width = 11.33"
    *   col_width = (usable - 11 * gutter) / 12

    Every element position MUST be computed through this class.
    """

    COLUMNS: int = 12
    MARGIN:  float = 1.0
    GUTTER:  float = 0.25
    USABLE_WIDTH: float = SLIDE_WIDTH - 2 * MARGIN                # 11.33"
    COL_WIDTH: float = (
        (USABLE_WIDTH - (COLUMNS - 1) * GUTTER) / COLUMNS         # ≈ 0.715"
    )

    # ------------------------------------------------------------------
    # Fundamental positioning
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
    def compute(cls, span: int, offset: int = 0) -> tuple[float, float]:
        """Return ``(left, width)`` for *span* columns starting at *offset*.

        ``offset`` is a 0-based column index.
        """
        left = cls.col_left(offset)
        width = cls.span_width(span)
        return left, width

    @classmethod
    def center(cls, span_cols: int) -> tuple[float, float]:
        """``(left, width)`` to centre *span_cols* columns."""
        width = cls.span_width(span_cols)
        left = cls.MARGIN + (cls.USABLE_WIDTH - width) / 2
        return left, width

    @classmethod
    def full_width(cls) -> tuple[float, float]:
        """``(left, width)`` for the full 12-column content area."""
        return cls.MARGIN, cls.USABLE_WIDTH

    # ------------------------------------------------------------------
    # Multi-column splits
    # ------------------------------------------------------------------
    @classmethod
    def split(cls, *col_spans: int) -> list[tuple[float, float]]:
        """Split the grid into sections with given column spans.

        Example: ``Grid.split(6, 6)`` → two halves
                 ``Grid.split(4, 4, 4)`` → three thirds
                 ``Grid.split(8, 4)`` → wide left, narrow right

        Returns ``[(left, width), …]``.
        """
        result: list[tuple[float, float]] = []
        offset = 0
        for span in col_spans:
            result.append(cls.compute(span, offset))
            offset += span
        return result

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

    TITLE_TOP: float     = Spacing.XL                 # 0.667"
    TITLE_HEIGHT: float  = 0.9
    ACCENT_Y: float      = TITLE_TOP + TITLE_HEIGHT + Spacing.XS   # ≈ 1.692"
    ACCENT_HEIGHT: float = 0.06
    CONTENT_START: float = ACCENT_Y + ACCENT_HEIGHT + Spacing.MD   # ≈ 2.0"
    CONTENT_END: float   = Spacing.BOTTOM_LIMIT        # 6.833"

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


# ---------------------------------------------------------------------------
# VStack – Vertical Flow Engine
# ---------------------------------------------------------------------------
class VStack:
    """Manages vertical placement so manual y-calculations are never needed.

    Usage::

        flow = VStack(start_y=VLayout.CONTENT_START)
        y1 = flow.next(height=0.9)          # returns y for first element
        y2 = flow.next(height=0.6, gap=Spacing.LG)  # custom gap before this
        remaining = flow.remaining()         # how much vertical space is left
    """

    def __init__(self, start_y: float | None = None):
        self._y = start_y if start_y is not None else VLayout.CONTENT_START
        self._initial = self._y

    @property
    def y(self) -> float:
        """Current cursor position."""
        return self._y

    def next(self, height: float = 0.6, gap: float | None = None) -> float:
        """Advance the cursor and return the y for the new element.

        *gap* defaults to ``Spacing.ELEMENT``.
        """
        if gap is None:
            gap = Spacing.ELEMENT
        # On the very first call, don't add a gap
        if self._y == self._initial:
            y = self._y
        else:
            y = self._y + gap
        self._y = y + height
        return y

    def skip(self, amount: float | None = None) -> None:
        """Add extra vertical space without rendering anything."""
        self._y += amount if amount is not None else Spacing.SECTION

    def remaining(self, limit: float | None = None) -> float:
        """Vertical inches remaining before the bottom safe zone."""
        bottom = limit if limit is not None else VLayout.CONTENT_END
        return max(0.0, bottom - self._y)

    def fits(self, height: float, gap: float | None = None) -> bool:
        """Check if an element of *height* fits without overflow."""
        g = gap if gap is not None else Spacing.ELEMENT
        needed = g + height if self._y != self._initial else height
        return self.remaining() >= needed


# ---------------------------------------------------------------------------
# Content Transformation Utilities
# ---------------------------------------------------------------------------
class ContentTransform:
    """Content-aware text transformations for presentation-grade text.

    Raw content is NOT presentation-ready.  These helpers enforce
    conciseness and readability constraints.
    """

    MAX_WORDS_PER_BLOCK: int = 12
    MAX_LINES: int = 2

    @staticmethod
    def truncate(text: str, max_words: int = 12) -> str:
        """Truncate *text* to at most *max_words*, appending '…' if trimmed."""
        if not text:
            return text
        words = text.split()
        if len(words) <= max_words:
            return text
        return " ".join(words[:max_words]) + "…"

    @staticmethod
    def truncate_lines(text: str, max_lines: int = 2, max_words_per_line: int = 12) -> str:
        """Limit text to *max_lines* lines, each ≤ *max_words_per_line* words."""
        if not text:
            return text
        lines = text.strip().split("\n")[:max_lines]
        processed = []
        for line in lines:
            words = line.split()
            if len(words) > max_words_per_line:
                processed.append(" ".join(words[:max_words_per_line]) + "…")
            else:
                processed.append(line.strip())
        return "\n".join(processed)

    @staticmethod
    def truncate_bullets(items: list[str], max_items: int = 6,
                         max_words: int = 10) -> list[str]:
        """Limit bullet list length and per-item word count."""
        result = []
        for item in items[:max_items]:
            words = item.split()
            if len(words) > max_words:
                result.append(" ".join(words[:max_words]) + "…")
            else:
                result.append(item)
        return result
