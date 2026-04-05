"""
Tests for the final hardening patch — strict system guarantees.

Covers:
  - ISSUE 1: Playwright is required — no fallback logic
  - ISSUE 2: Split layout requires image_url — raises SlideRenderError
  - ISSUE 3: Export parity uses actual copy, not same object
  - ISSUE 4: Export fails entirely if any slide fails
  - ISSUE 5: Image requirement enforced before template rendering
"""

import os
import sys
import inspect
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pipeline.visual_design_engine import (
    run_design_engine,
    should_use_image,
)
from pipeline.visual_template_engine import run_template_engine, render_slide_html
from pipeline.visual_rendering_engine import (
    build_render_instructions,
    ExportRenderError,
    _require_playwright,
    render_slides_to_images,
    render_slides_to_pdf,
    run_rendering_engine,
    _merge_pdfs,
)
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
        "subtitle": "Transforming outcomes with AI",
    },
}

GRID_SLIDE = {
    "slide_id": 2,
    "type": "problem_slide",
    "content": {
        "title": "Key Challenges",
        "bullets": [
            "Data fragmentation",
            "Compliance concerns",
            "Protocol gaps",
        ],
    },
}

SPLIT_SLIDE_WITH_IMAGE = {
    "slide_id": 3,
    "type": "example_slide",
    "content": {
        "title": "Case Study",
        "body": "Reduced readmission by 40%.",
        "bullets": ["Monitoring", "Alerts"],
        "image_url": "file:///tmp/test_case.png",
    },
}

SPLIT_SLIDE_NO_IMAGE = {
    "slide_id": 4,
    "type": "example_slide",
    "content": {
        "title": "Missing Image Slide",
        "body": "This slide has no image.",
        "bullets": ["Point 1", "Point 2"],
    },
}

FEATURE_SLIDE = {
    "slide_id": 5,
    "type": "feature_slide",
    "content": {
        "title": "Core Features",
        "features": [
            {"icon": "🔬", "label": "Analysis", "description": "Deep learning"},
            {"icon": "📊", "label": "Dashboard", "description": "Real-time"},
        ],
    },
}


# ══════════════════════════════════════════════════════════════════════
# ISSUE 1: Playwright is required — no fallback
# ══════════════════════════════════════════════════════════════════════

class TestPlaywrightRequired:
    """Verify Playwright is mandatory — no fallback logic exists."""

    def test_require_playwright_raises_if_missing(self):
        """_require_playwright must raise RuntimeError if Playwright unavailable."""
        # In test env, Playwright IS unavailable — this should raise
        with pytest.raises(RuntimeError, match="Playwright is required"):
            _require_playwright()

    @pytest.mark.asyncio
    async def test_render_slides_to_images_raises_without_playwright(self):
        """render_slides_to_images must raise RuntimeError without Playwright."""
        with pytest.raises(RuntimeError, match="Playwright is required"):
            await render_slides_to_images(["<html></html>"], "/tmp/test")

    @pytest.mark.asyncio
    async def test_render_slides_to_pdf_raises_without_playwright(self):
        """render_slides_to_pdf must raise RuntimeError without Playwright."""
        with pytest.raises(RuntimeError, match="Playwright is required"):
            await render_slides_to_pdf(["<html></html>"], "/tmp/test")

    @pytest.mark.asyncio
    async def test_run_rendering_engine_raises_without_playwright(self):
        """run_rendering_engine must raise RuntimeError without Playwright."""
        with pytest.raises(RuntimeError, match="Playwright is required"):
            await run_rendering_engine(["<html></html>"], "/tmp/test")

    def test_no_fallback_import_logic_in_rendering_engine(self):
        """Rendering engine must NOT have try/except around Playwright import in render functions."""
        source = inspect.getsource(render_slides_to_images)
        assert "except ImportError" not in source, (
            "render_slides_to_images still has Playwright import fallback"
        )

        source_pdf = inspect.getsource(render_slides_to_pdf)
        assert "except ImportError" not in source_pdf, (
            "render_slides_to_pdf still has Playwright import fallback"
        )

    def test_no_warning_in_rendering_functions(self):
        """Rendering functions must NOT log warnings and continue."""
        for fn in [render_slides_to_images, render_slides_to_pdf, run_rendering_engine]:
            source = inspect.getsource(fn)
            assert "logger.warning" not in source, (
                f"{fn.__name__} still has logger.warning — must raise errors, not warn"
            )

    def test_merge_pdfs_requires_pypdf(self):
        """_merge_pdfs must raise RuntimeError for multi-page without pypdf, not fallback."""
        source = inspect.getsource(_merge_pdfs)
        # Should NOT have fallback "write first slide only" logic
        assert "Fallback" not in source, (
            "_merge_pdfs still has pypdf fallback logic"
        )
        assert "first slide" not in source.lower(), (
            "_merge_pdfs still writes single slide as fallback"
        )


# ══════════════════════════════════════════════════════════════════════
# ISSUE 2: Split layout requires image_url
# ══════════════════════════════════════════════════════════════════════

class TestSplitLayoutRequiresImage:
    """Split layout must raise if image_url is missing."""

    def test_split_without_image_raises(self):
        """Split slide without image_url must raise SlideRenderError."""
        designs = run_design_engine([SPLIT_SLIDE_NO_IMAGE])
        with pytest.raises(SlideRenderError, match="Split layout requires image_url"):
            run_template_engine(designs)

    def test_split_with_image_renders_successfully(self):
        """Split slide with image_url must render without error."""
        designs = run_design_engine([SPLIT_SLIDE_WITH_IMAGE])
        html_slides = run_template_engine(designs)
        assert len(html_slides) == 1
        assert "<img" in html_slides[0]
        assert "test_case.png" in html_slides[0]

    def test_no_empty_panel_in_split_template(self):
        """Split template source must NOT have empty styled panel fallback."""
        from pipeline.visual_template_engine import _render_split
        source = inspect.getsource(_render_split)
        assert "opacity-[0.03]" not in source, (
            "Split template still has empty styled panel fallback"
        )
        assert ">Visual<" not in source, (
            "Split template still has Visual placeholder text"
        )


# ══════════════════════════════════════════════════════════════════════
# ISSUE 3: Export parity with actual copy
# ══════════════════════════════════════════════════════════════════════

class TestExportParityCopy:
    """Export parity validation must compare independent copies."""

    def test_parity_with_list_copy_passes(self):
        """Parity check with actual copy of same data must pass."""
        designs = run_design_engine([HERO_SLIDE, GRID_SLIDE])
        html_slides = run_template_engine(designs)
        export_copy = list(html_slides)
        validate_export_parity(html_slides, export_copy)

    def test_parity_with_modified_copy_fails(self):
        """Parity check with modified copy must fail."""
        html_a = ["<html>slide 1</html>"]
        html_b = ["<html>slide 1 CHANGED</html>"]
        with pytest.raises(SlideRenderError, match="differs"):
            validate_export_parity(html_a, html_b)

    def test_orchestrator_uses_list_copy_for_parity(self):
        """Orchestrator must create list copy before parity validation."""
        import orchestrator
        source = inspect.getsource(orchestrator.run_pipeline)
        assert "list(all_html_slides)" in source or "list(html_slides)" in source, (
            "Orchestrator must use list() copy for export parity, not same object"
        )


# ══════════════════════════════════════════════════════════════════════
# ISSUE 4: No partial export — all-or-nothing
# ══════════════════════════════════════════════════════════════════════

class TestNoPartialExport:
    """Export must fail entirely if any component fails."""

    def test_rendering_engine_no_per_slide_try_except(self):
        """render_slides_to_images must NOT have per-slide try/except."""
        source = inspect.getsource(render_slides_to_images)
        assert "except" not in source, (
            "render_slides_to_images still has try/except — must be all-or-nothing"
        )

    def test_run_rendering_engine_no_fallback_try_except(self):
        """run_rendering_engine must NOT wrap calls in try/except fallback."""
        source = inspect.getsource(run_rendering_engine)
        assert "except" not in source, (
            "run_rendering_engine still has try/except fallback — must propagate errors"
        )


# ══════════════════════════════════════════════════════════════════════
# ISSUE 5: Image requirement enforcement
# ══════════════════════════════════════════════════════════════════════

class TestImageRequirementEnforced:
    """Image requirement must be enforced before template rendering."""

    def test_should_use_image_for_visual_types(self):
        """should_use_image returns True for visual slide types."""
        assert should_use_image({"type": "example_slide", "content": {"title": "Demo"}}) is True
        assert should_use_image({"type": "feature_slide", "content": {"title": "Features"}}) is True

    def test_should_use_image_false_for_abstract_types(self):
        """should_use_image returns False for abstract slide types."""
        assert should_use_image({"type": "title_slide", "content": {"title": "Title"}}) is False
        assert should_use_image({"type": "stats_slide", "content": {"title": "Stats"}}) is False
        assert should_use_image({"type": "cta_slide", "content": {"title": "CTA"}}) is False

    def test_orchestrator_enforces_image_requirement(self):
        """Orchestrator must check should_use_image + image_url presence."""
        import orchestrator
        source = inspect.getsource(orchestrator.run_pipeline)
        assert "should_use_image" in source, (
            "Orchestrator does not check should_use_image() — image requirement not enforced"
        )
        assert "image required but missing" in source.lower() or "image_url" in source, (
            "Orchestrator does not raise error for missing required images"
        )


# ══════════════════════════════════════════════════════════════════════
# Integration: Full pipeline with strict rules
# ══════════════════════════════════════════════════════════════════════

class TestStrictPipelineIntegration:
    """Integration tests verifying all strict rules work together."""

    def test_slides_with_images_pass_full_validation(self):
        """Slides that include required images pass all validation."""
        slides = [HERO_SLIDE, GRID_SLIDE, SPLIT_SLIDE_WITH_IMAGE, FEATURE_SLIDE]
        designs = run_design_engine(slides)
        html_slides = run_template_engine(designs)
        validated = validate_rendered_html(html_slides)
        assert len(validated) == 4

    def test_export_parity_with_copy(self):
        """Export parity with list() copy passes for valid slides."""
        slides = [HERO_SLIDE, GRID_SLIDE, FEATURE_SLIDE]
        designs = run_design_engine(slides)
        html_slides = run_template_engine(designs)
        export_copy = list(html_slides)
        validate_export_parity(html_slides, export_copy)

    def test_split_slide_image_in_html(self):
        """Split slide with image_url has <img> in rendered HTML."""
        designs = run_design_engine([SPLIT_SLIDE_WITH_IMAGE])
        html_slides = run_template_engine(designs)
        assert "<img" in html_slides[0]
        assert "test_case.png" in html_slides[0]
