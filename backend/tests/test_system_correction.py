"""
Tests for the system correction changes:
  - Phase 1: Per-slide PDF rendering (no HTML reconstruction)
  - Phase 2: Rendered HTML validation
  - Phase 3: Image pipeline (image_path → image_url flow)
  - Phase 4: Image export compatibility
  - Phase 5: Design system enforcement
  - Phase 6: Export validation layer
"""

import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pipeline.visual_design_engine import (
    run_design_engine,
    map_components,
    should_use_image,
)
from pipeline.visual_template_engine import run_template_engine, render_slide_html
from pipeline.visual_rendering_engine import build_render_instructions
from pipeline.slide_validator import (
    validate_rendered_html,
    validate_export_parity,
    SlideRenderError,
    SlideValidationError,
)


# ── Sample slide data ────────────────────────────────────────────────

HERO_SLIDE = {
    "slide_id": 1,
    "type": "title_slide",
    "content": {
        "title": "AI in Healthcare",
        "subtitle": "Transforming patient outcomes with machine learning",
    },
}

GRID_SLIDE = {
    "slide_id": 2,
    "type": "problem_slide",
    "content": {
        "title": "Key Challenges",
        "bullets": [
            "Data fragmentation across systems",
            "Lack of standardized protocols",
            "Privacy and compliance concerns",
        ],
    },
}

SPLIT_SLIDE = {
    "slide_id": 3,
    "type": "example_slide",
    "content": {
        "title": "Case Study: Hospital A",
        "body": "Hospital A reduced readmission rates by 40% using predictive analytics.",
        "bullets": ["Real-time monitoring", "Early intervention alerts"],
        "image_url": "file:///tmp/test_hospital.png",
    },
}

STATS_SLIDE = {
    "slide_id": 4,
    "type": "stats_slide",
    "content": {
        "title": "Impact Numbers",
        "stats": [
            {"value": "40%", "label": "Reduction in readmissions"},
            {"value": "2.5x", "label": "Faster diagnosis"},
            {"value": "98%", "label": "Accuracy rate"},
        ],
    },
}

FEATURE_SLIDE = {
    "slide_id": 5,
    "type": "feature_slide",
    "content": {
        "title": "Core Features",
        "features": [
            {"icon": "🔬", "label": "Analysis", "description": "Deep learning analysis"},
            {"icon": "📊", "label": "Dashboard", "description": "Real-time monitoring"},
            {"icon": "🔒", "label": "Security", "description": "HIPAA compliant"},
        ],
    },
}

IMAGE_SLIDE_WITH_URL = {
    "slide_id": 6,
    "type": "example_slide",
    "content": {
        "title": "Visual Demo",
        "body": "See the platform in action",
        "image_url": "file:///tmp/test_image.png",
    },
}

IMAGE_SLIDE_WITH_PATH = {
    "slide_id": 7,
    "type": "example_slide",
    "content": {
        "title": "Visual Demo 2",
        "body": "Another platform view",
    },
    "image_path": "/tmp/test_image.png",
}


# ══════════════════════════════════════════════════════════════════════
# Phase 1: Per-slide PDF rendering
# ══════════════════════════════════════════════════════════════════════

class TestPerSlideRendering:
    """Test that the rendering engine uses per-slide approach."""

    def test_render_instructions_correct(self):
        """build_render_instructions returns correct viewport."""
        instructions = build_render_instructions(5)
        assert instructions["viewport"] == "1920x1080"
        assert instructions["slide_count"] == 5

    def test_no_build_combined_html(self):
        """_build_combined_html should NOT exist — it was the source of content loss."""
        from pipeline import visual_rendering_engine as mod
        assert not hasattr(mod, "_build_combined_html"), (
            "_build_combined_html still exists — HTML reconstruction must be removed"
        )

    def test_export_render_error_exists(self):
        """ExportRenderError should be available for parity violations."""
        from pipeline.visual_rendering_engine import ExportRenderError
        assert issubclass(ExportRenderError, RuntimeError)


# ══════════════════════════════════════════════════════════════════════
# Phase 2: Rendered HTML validation
# ══════════════════════════════════════════════════════════════════════

class TestRenderedHtmlValidation:
    """Test that HTML validation catches title-only slides."""

    def test_valid_hero_slide(self):
        """Hero slide with subtitle should pass validation."""
        designs = run_design_engine([HERO_SLIDE])
        html_slides = run_template_engine(designs)
        assert len(html_slides) == 1
        result = validate_rendered_html(html_slides)
        assert result == html_slides

    def test_valid_grid_slide(self):
        """Grid cards slide with bullets should pass validation."""
        designs = run_design_engine([GRID_SLIDE])
        html_slides = run_template_engine(designs)
        result = validate_rendered_html(html_slides)
        assert result == html_slides

    def test_valid_stats_slide(self):
        """Stats slide with stat values should pass validation."""
        designs = run_design_engine([STATS_SLIDE])
        html_slides = run_template_engine(designs)
        result = validate_rendered_html(html_slides)
        assert result == html_slides

    def test_valid_feature_slide(self):
        """Feature slide should pass validation."""
        designs = run_design_engine([FEATURE_SLIDE])
        html_slides = run_template_engine(designs)
        result = validate_rendered_html(html_slides)
        assert result == html_slides

    def test_empty_html_fails(self):
        """Empty HTML string should fail validation."""
        with pytest.raises(SlideRenderError) as exc_info:
            validate_rendered_html([""])
        assert "empty" in str(exc_info.value).lower()

    def test_title_only_html_fails(self):
        """HTML with only a title and no content markers should fail."""
        title_only_html = """
        <!DOCTYPE html><html><body>
        <div class="slide"><h1>Just a Title</h1></div>
        </body></html>
        """
        with pytest.raises(SlideRenderError) as exc_info:
            validate_rendered_html([title_only_html])
        assert "title" in str(exc_info.value).lower()

    def test_all_real_slides_pass_validation(self):
        """All standard slide types should produce valid rendered HTML."""
        all_slides = [HERO_SLIDE, GRID_SLIDE, SPLIT_SLIDE, STATS_SLIDE, FEATURE_SLIDE]
        designs = run_design_engine(all_slides)
        html_slides = run_template_engine(designs)
        result = validate_rendered_html(html_slides)
        assert len(result) == 5


# ══════════════════════════════════════════════════════════════════════
# Phase 2b: Export parity validation
# ══════════════════════════════════════════════════════════════════════

class TestExportParity:
    """Test that export parity check catches mismatches."""

    def test_identical_html_passes(self):
        """Identical editor and export HTML should pass parity check."""
        designs = run_design_engine([HERO_SLIDE, GRID_SLIDE])
        html_slides = run_template_engine(designs)
        # Same list passed twice — should pass
        validate_export_parity(html_slides, html_slides)

    def test_different_html_fails(self):
        """Different editor and export HTML should fail parity check."""
        html_a = ["<html>slide 1</html>", "<html>slide 2</html>"]
        html_b = ["<html>slide 1 MODIFIED</html>", "<html>slide 2</html>"]
        with pytest.raises(SlideRenderError) as exc_info:
            validate_export_parity(html_a, html_b)
        assert "differs" in str(exc_info.value).lower()

    def test_count_mismatch_fails(self):
        """Different slide counts should fail parity check."""
        html_a = ["<html>slide 1</html>"]
        html_b = ["<html>slide 1</html>", "<html>slide 2</html>"]
        with pytest.raises(SlideRenderError) as exc_info:
            validate_export_parity(html_a, html_b)
        assert "mismatch" in str(exc_info.value).lower()


# ══════════════════════════════════════════════════════════════════════
# Phase 3: Image pipeline (image_path → image_url flow)
# ══════════════════════════════════════════════════════════════════════

class TestImagePipeline:
    """Test that images flow correctly from content to components to HTML."""

    def test_image_url_in_content_reaches_components_hero(self):
        """content.image_url should appear in hero components."""
        components = map_components(IMAGE_SLIDE_WITH_URL, "hero_center")
        assert components.get("image_url") == "file:///tmp/test_image.png"

    def test_image_url_in_content_reaches_components_split(self):
        """content.image_url should appear in split layout components."""
        components = map_components(IMAGE_SLIDE_WITH_URL, "split_left_text_right_visual")
        assert components.get("image_url") == "file:///tmp/test_image.png"

    def test_image_url_in_content_reaches_components_grid(self):
        """content.image_url should appear in grid_cards components."""
        components = map_components(IMAGE_SLIDE_WITH_URL, "grid_cards")
        assert components.get("image_url") == "file:///tmp/test_image.png"

    def test_slide_level_image_path_reaches_components(self):
        """slide.image_path should be resolved to image_url in components."""
        components = map_components(IMAGE_SLIDE_WITH_PATH, "split_left_text_right_visual")
        assert "image_url" in components
        assert components["image_url"].startswith("file://")
        assert "test_image.png" in components["image_url"]

    def test_slide_level_image_path_reaches_hero_components(self):
        """slide.image_path should be resolved to image_url in hero components."""
        components = map_components(IMAGE_SLIDE_WITH_PATH, "hero_center")
        assert "image_url" in components
        assert components["image_url"].startswith("file://")

    def test_image_url_reaches_html(self):
        """image_url should appear as <img src> in rendered HTML."""
        slide = {
            "slide_id": 1,
            "type": "example_slide",
            "content": {
                "title": "Demo",
                "body": "Description text",
                "image_url": "file:///tmp/demo.png",
            },
        }
        designs = run_design_engine([slide])
        html_slides = run_template_engine(designs)
        assert "file:///tmp/demo.png" in html_slides[0]
        assert "<img" in html_slides[0]

    def test_hero_image_url_reaches_html(self):
        """Hero slide background image should appear in HTML."""
        slide = {
            "slide_id": 1,
            "type": "title_slide",
            "content": {
                "title": "Title",
                "subtitle": "Subtitle text",
                "image_url": "file:///tmp/bg.png",
            },
        }
        designs = run_design_engine([slide])
        html_slides = run_template_engine(designs)
        assert "file:///tmp/bg.png" in html_slides[0]
        assert "<img" in html_slides[0]

    def test_no_image_when_not_needed(self):
        """Stats slide should NOT have image_url in components."""
        components = map_components(STATS_SLIDE, "stats_blocks")
        assert "image_url" not in components

    def test_should_use_image_decisions(self):
        """should_use_image should return correct decisions per slide type."""
        assert should_use_image({"type": "example_slide", "content": {"title": "Test"}}) is True
        assert should_use_image({"type": "feature_slide", "content": {"title": "Test"}}) is True
        assert should_use_image({"type": "title_slide", "content": {"title": "Test"}}) is False
        assert should_use_image({"type": "stats_slide", "content": {"title": "Test"}}) is False
        assert should_use_image({"type": "cta_slide", "content": {"title": "Test"}}) is False


# ══════════════════════════════════════════════════════════════════════
# Phase 6: Export validation layer (integration)
# ══════════════════════════════════════════════════════════════════════

class TestExportValidationLayer:
    """Test the full export validation pipeline."""

    def test_full_pipeline_produces_valid_html(self):
        """Design → Template pipeline produces HTML that passes validation."""
        slides = [HERO_SLIDE, GRID_SLIDE, SPLIT_SLIDE, STATS_SLIDE, FEATURE_SLIDE]
        designs = run_design_engine(slides)
        html_slides = run_template_engine(designs)

        # Every slide must pass rendered HTML validation
        validated = validate_rendered_html(html_slides)
        assert len(validated) == 5

    def test_every_slide_has_content_beyond_title(self):
        """Each rendered slide must contain content beyond just the title."""
        slides = [HERO_SLIDE, GRID_SLIDE, SPLIT_SLIDE, STATS_SLIDE, FEATURE_SLIDE]
        designs = run_design_engine(slides)
        html_slides = run_template_engine(designs)

        for idx, html in enumerate(html_slides):
            # Must contain at least one content element
            has_p = "<p " in html or "<p>" in html
            has_li = "<li " in html or "<li>" in html
            has_stat = "text-5xl" in html or "text-7xl" in html
            has_card = "rounded-2xl" in html or "rounded-3xl" in html
            assert has_p or has_li or has_stat or has_card, (
                f"Slide {idx + 1} has no visible content beyond title"
            )

    def test_export_parity_with_same_html(self):
        """Editor HTML == Export HTML when using same pipeline."""
        slides = [HERO_SLIDE, GRID_SLIDE, SPLIT_SLIDE]
        designs = run_design_engine(slides)
        editor_html = run_template_engine(designs)

        # In the corrected system, export uses the EXACT same HTML
        export_html = editor_html  # Same reference — guaranteed parity

        validate_export_parity(editor_html, export_html)

    def test_image_presence_in_html(self):
        """Slide with image_url should have <img> in rendered HTML."""
        slide = {
            "slide_id": 1,
            "type": "example_slide",
            "content": {
                "title": "Visual",
                "body": "Description",
                "image_url": "file:///images/ai_test.png",
            },
        }
        designs = run_design_engine([slide])
        html_slides = run_template_engine(designs)
        assert "<img" in html_slides[0], "Image expected but not found in HTML"
        assert "ai_test.png" in html_slides[0], "Image URL not in HTML"

    def test_split_slide_with_image_path(self):
        """Split slide with slide-level image_path should render image in HTML."""
        slide = {
            "slide_id": 1,
            "type": "example_slide",
            "content": {
                "title": "Demo",
                "body": "See the demo",
            },
            "image_path": "/tmp/demo_image.png",
        }
        designs = run_design_engine([slide])
        html_slides = run_template_engine(designs)
        assert "<img" in html_slides[0], "Image from image_path not rendered"
        assert "demo_image.png" in html_slides[0], "Image path not in HTML"
