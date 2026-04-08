from pathlib import Path

from pipeline.dynamic_composition_engine import _HTML_WRAPPER
from pipeline.visual_rendering_engine import build_render_instructions


CSS_PATH = Path(__file__).resolve().parents[1] / "pipeline" / "static" / "slides.css"


def _read_css() -> str:
    return CSS_PATH.read_text(encoding="utf-8")


def test_layered_neutral_tokens_present():
    css = _read_css()
    for token in (
        "--bg-base: #FAFAFA",
        "--surface-primary: #FFFFFF",
        "--surface-elevated: #F4F6F8",
        "--border: #E2E8F0",
        "--text-primary: #0F172A",
        "--text-secondary: #64748B",
        "--accent: #2563EB",
        "--radius: 8px",
        "--s-1: 8px",
        "--s-2: 16px",
        "--s-3: 24px",
        "--s-4: 32px",
        "--s-6: 48px",
        "--s-8: 64px",
    ):
        assert token in css


def test_forbidden_visual_effects_removed():
    css = _read_css().lower()
    for forbidden in ("linear-gradient", "radial-gradient", "box-shadow", "drop-shadow"):
        assert forbidden not in css


def test_legacy_theme_variants_removed():
    css = _read_css()
    for legacy in ("dark_modern", "minimal_light", "bold_gradient", "data-theme"):
        assert legacy not in css


def test_wrapper_is_global_stylesheet_only_and_section_based():
    assert "{custom_style}" not in _HTML_WRAPPER
    assert "deck-surface" in _HTML_WRAPPER
    assert "slide-section" in _HTML_WRAPPER
    assert "data-render-system" in _HTML_WRAPPER


def test_render_instructions_allow_scroll_mode():
    instructions = build_render_instructions(3)
    assert instructions["render_mode"] == "continuous_scroll_sections"
    assert instructions["quality"]["allow_vertical_scroll"] is True
    assert "no_scrolling" not in instructions["quality"]
    assert "no_overflow" not in instructions["quality"]
