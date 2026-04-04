from dataclasses import dataclass, field


@dataclass
class ThemeConfig:
    name: str
    primary: str        # hex colour (no leading '#')
    secondary: str
    background: str
    text: str
    accent: str
    font_heading: str
    font_body: str
    heading_size: int
    body_size: int
    # Surface colour used for card backgrounds (defaults to background)
    surface: str = ""

    def __post_init__(self):
        if not self.surface:
            self.surface = self.background


MODERN = ThemeConfig(
    name="modern",
    primary="6C63FF",
    secondary="A29BFE",
    background="FFFFFF",
    text="2D2D2D",
    accent="FD79A8",
    font_heading="Calibri",
    font_body="Calibri",
    heading_size=44,
    body_size=20,
    surface="F8F8FF",
)

CORPORATE = ThemeConfig(
    name="corporate",
    primary="1A3C5E",
    secondary="2E75B6",
    background="F5F5F5",
    text="1A1A1A",
    accent="E8A020",
    font_heading="Calibri",
    font_body="Calibri",
    heading_size=44,
    body_size=20,
    surface="FFFFFF",
)

MINIMAL = ThemeConfig(
    name="minimal",
    primary="2D2D2D",
    secondary="888888",
    background="FAFAFA",
    text="1A1A1A",
    accent="000000",
    font_heading="Calibri",
    font_body="Calibri",
    heading_size=44,
    body_size=20,
    surface="FFFFFF",
)

THEMES = {"modern": MODERN, "corporate": CORPORATE, "minimal": MINIMAL}