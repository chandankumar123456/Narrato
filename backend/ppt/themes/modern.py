from dataclasses import dataclass

@dataclass
class ThemeConfig:
    name: str
    primary: str        # hex
    secondary: str
    background: str
    text: str
    accent: str
    font_heading: str
    font_body: str
    heading_size: int
    body_size: int

MODERN = ThemeConfig(
    name="modern",
    primary="6C63FF",
    secondary="A29BFE",
    background="FFFFFF",
    text="2D2D2D",
    accent="FD79A8",
    font_heading="Calibri",
    font_body="Calibri",
    heading_size=36,
    body_size=18,
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
    heading_size=34,
    body_size=18,
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
    heading_size=36,
    body_size=18,
)

THEMES = {"modern": MODERN, "corporate": CORPORATE, "minimal": MINIMAL}