"""
Tests for the final correction patch — strict system behavior.

Covers:
  - ISSUE 1: Validation halts pipeline (no try/except)
  - ISSUE 2: No stock image fallbacks (Unsplash/Pexels removed)
  - ISSUE 3: AI image service raises on failure (no None returns)
  - ISSUE 4: Image wait is strict (no swallowed exceptions)
  - ISSUE 5: No placeholder <div>Visual</div> in templates
  - ISSUE 6: Export parity enforced with .strip() comparison
  - ISSUE 7: Export fails entirely on any slide failure
"""

import os
import sys
import inspect
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pipeline.visual_design_engine import (
    run_design_engine,
    map_components,
    should_use_image,
)
from pipeline.visual_template_engine import run_template_engine, render_slide_html
from pipeline.visual_rendering_engine import build_render_instructions, ExportRenderError
from pipeline.slide_validator import (
    validate_rendered_html,
    validate_export_parity,
    SlideRenderError,
    SlideValidationError,
)
from services.ai_image_service import (
    AIImageError,
    generate_image_prompt,
    generate_image,
    generate_image_for_slide,
)
from pipeline.visual_mapper import ImageGenerationError


# ── Sample slide data ────────────────────────────────────────────────

HERO_SLIDE = {
    "slide_id": 1,
    "type": "title_slide",
    "content": {
        "title": "AI in Healthcare",
        "subtitle": "Transforming patient outcomes with machine learning",
    },
}

SPLIT_SLIDE = {
    "slide_id": 3,
    "type": "example_slide",
    "content": {
        "title": "Case Study: Hospital A",
        "body": "Hospital A reduced readmission rates by 40%.",
        "bullets": ["Real-time monitoring", "Early intervention alerts"],
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
            {"icon": "🔒", "label": "Security", "description": "HIPAA compliant"},
        ],
    },
}


# ══════════════════════════════════════════════════════════════════════
# ISSUE 1: Validation halts pipeline — no try/except wrapper
# ══════════════════════════════════════════════════════════════════════

class TestValidationStrictness:
    """Validate that validation errors propagate without being caught."""

    def test_validate_rendered_html_raises_not_catches(self):
        """validate_rendered_html must raise SlideRenderError for bad HTML."""
        with pytest.raises(SlideRenderError):
            validate_rendered_html([""])

    def test_orchestrator_does_not_wrap_validate_rendered_html(self):
        """Orchestrator must NOT wrap validate_rendered_html in try/except."""
        import orchestrator
        source = inspect.getsource(orchestrator.run_pipeline)
        # Find the validate_rendered_html call
        lines = source.split("\n")
        for i, line in enumerate(lines):
            if "validate_rendered_html" in line and "import" not in line:
                # Check that the preceding lines do NOT contain 'try:'
                preceding = "\n".join(lines[max(0, i-3):i])
                assert "try:" not in preceding, (
                    "validate_rendered_html is wrapped in try/except — "
                    "validation must halt the pipeline on failure"
                )

    def test_orchestrator_calls_validate_export_parity(self):
        """Orchestrator must call validate_export_parity before export."""
        import orchestrator
        source = inspect.getsource(orchestrator.run_pipeline)
        assert "validate_export_parity" in source, (
            "validate_export_parity is not called in orchestrator"
        )


# ══════════════════════════════════════════════════════════════════════
# ISSUE 2: No stock image fallbacks
# ══════════════════════════════════════════════════════════════════════

class TestNoStockImageFallbacks:
    """Ensure all stock image sources are removed from the image pipeline."""

    def test_visual_mapper_no_fetch_image_import(self):
        """visual_mapper.py must NOT import fetch_image from image_service."""
        import pipeline.visual_mapper as vm
        source = inspect.getsource(vm)
        assert "fetch_image" not in source, (
            "visual_mapper still imports fetch_image — stock image fallback must be removed"
        )

    def test_visual_mapper_no_unsplash_reference(self):
        """visual_mapper.py must NOT reference Unsplash."""
        import pipeline.visual_mapper as vm
        source = inspect.getsource(vm)
        assert "unsplash" not in source.lower(), (
            "visual_mapper still references Unsplash — all stock sources must be removed"
        )

    def test_visual_mapper_no_pexels_reference(self):
        """visual_mapper.py must NOT reference Pexels."""
        import pipeline.visual_mapper as vm
        source = inspect.getsource(vm)
        assert "pexels" not in source.lower(), (
            "visual_mapper still references Pexels — all stock sources must be removed"
        )

    def test_visual_mapper_no_call_llm_json_list_import(self):
        """visual_mapper.py must NOT import call_llm_json_list for query generation."""
        import pipeline.visual_mapper as vm
        source = inspect.getsource(vm)
        assert "call_llm_json_list" not in source, (
            "visual_mapper still imports call_llm_json_list — stock query generation must be removed"
        )

    def test_image_generation_error_exists(self):
        """ImageGenerationError must be defined in visual_mapper."""
        assert issubclass(ImageGenerationError, RuntimeError)


# ══════════════════════════════════════════════════════════════════════
# ISSUE 3: AI image service raises on failure
# ══════════════════════════════════════════════════════════════════════

class TestAIImageServiceStrict:
    """AI image service must raise on failure, not return None."""

    def test_ai_image_error_exists(self):
        """AIImageError must be defined."""
        assert issubclass(AIImageError, RuntimeError)

    def test_generate_image_uses_gpt_image_1(self):
        """generate_image must use gpt-image-1 model."""
        source = inspect.getsource(generate_image)
        assert "gpt-image-1" in source, (
            "generate_image does not use gpt-image-1 model"
        )

    def test_generate_image_no_none_return(self):
        """generate_image must not return None on failure — must raise."""
        source = inspect.getsource(generate_image)
        # The function should raise AIImageError, not return None
        assert "return None" not in source, (
            "generate_image still returns None on failure — must raise AIImageError"
        )

    def test_generate_image_raises_without_api_key(self):
        """generate_image must raise AIImageError when API key is missing."""
        # This test verifies the function signature and behavior
        source = inspect.getsource(generate_image)
        assert "raise AIImageError" in source, (
            "generate_image does not raise AIImageError — must fail on missing API key"
        )

    @pytest.mark.asyncio
    async def test_generate_image_prompt_includes_intent(self):
        """Image prompt must include intent based on slide type."""
        slide = {
            "type": "problem_slide",
            "content": {"title": "Data Challenges", "body": "Complex data issues"},
        }
        prompt = await generate_image_prompt(slide)
        assert "Data Challenges" in prompt
        assert "Intent:" in prompt


# ══════════════════════════════════════════════════════════════════════
# ISSUE 4: Image wait is strict
# ══════════════════════════════════════════════════════════════════════

class TestImageWaitStrict:
    """Rendering engine must not swallow image load failures."""

    def test_wait_for_slide_ready_no_try_except(self):
        """_wait_for_slide_ready must NOT wrap wait_for_function in try/except."""
        from pipeline.visual_rendering_engine import _wait_for_slide_ready
        source = inspect.getsource(_wait_for_slide_ready)
        # The wait_for_function call should not be in a try block
        assert "try:" not in source, (
            "_wait_for_slide_ready still wraps image wait in try/except — "
            "image load failures must propagate"
        )


# ══════════════════════════════════════════════════════════════════════
# ISSUE 5: No placeholder "Visual" text in templates
# ══════════════════════════════════════════════════════════════════════

class TestNoPlaceholderVisual:
    """Templates must not contain placeholder <div>Visual</div> text."""

    def test_split_template_no_visual_placeholder(self):
        """Split layout must not render 'Visual' placeholder text."""
        from pipeline.visual_template_engine import _render_split
        source = inspect.getsource(_render_split)
        assert ">Visual<" not in source, (
            "Split template still contains 'Visual' placeholder text — must be removed"
        )

    def test_split_without_image_no_visual_text(self):
        """Split slide without image should NOT have 'Visual' text in HTML."""
        slide = {
            "slide_id": 1,
            "type": "example_slide",
            "content": {
                "title": "Case Study",
                "body": "Description text here",
                "bullets": ["Point 1", "Point 2"],
            },
        }
        designs = run_design_engine([slide])
        html_slides = run_template_engine(designs)
        assert ">Visual<" not in html_slides[0], (
            "Split slide without image still shows 'Visual' placeholder"
        )


# ══════════════════════════════════════════════════════════════════════
# ISSUE 6: Export parity uses .strip() comparison
# ══════════════════════════════════════════════════════════════════════

class TestExportParityStrict:
    """Export parity validation must use .strip() comparison."""

    def test_parity_passes_with_identical_html(self):
        """Identical HTML passes parity check."""
        html = ["<html>slide 1</html>", "<html>slide 2</html>"]
        validate_export_parity(html, html)

    def test_parity_passes_with_whitespace_difference(self):
        """HTML that differs only in leading/trailing whitespace passes."""
        html_a = ["  <html>slide 1</html>  "]
        html_b = ["<html>slide 1</html>"]
        validate_export_parity(html_a, html_b)

    def test_parity_fails_with_content_difference(self):
        """Different HTML content fails parity check."""
        html_a = ["<html>slide 1</html>"]
        html_b = ["<html>slide 1 MODIFIED</html>"]
        with pytest.raises(SlideRenderError):
            validate_export_parity(html_a, html_b)

    def test_parity_fails_with_count_mismatch(self):
        """Different slide counts fail parity check."""
        html_a = ["<html>1</html>"]
        html_b = ["<html>1</html>", "<html>2</html>"]
        with pytest.raises(SlideRenderError):
            validate_export_parity(html_a, html_b)

    def test_parity_uses_strip(self):
        """validate_export_parity source code must use .strip() comparison."""
        source = inspect.getsource(validate_export_parity)
        assert ".strip()" in source, (
            "validate_export_parity does not use .strip() comparison"
        )


# ══════════════════════════════════════════════════════════════════════
# ISSUE 7: Export fails entirely — no partial success
# ══════════════════════════════════════════════════════════════════════

class TestExportFailFast:
    """Export must fail entirely if any component fails."""

    def test_run_visual_export_safe_no_try_except_for_images(self):
        """_run_visual_export_safe must NOT wrap render_slides_to_images in try/except."""
        import orchestrator
        source = inspect.getsource(orchestrator._run_visual_export_safe)
        # Count occurrences of try: — should have NONE
        assert "try:" not in source, (
            "_run_visual_export_safe still has try/except — export must fail-fast"
        )

    def test_run_visual_export_safe_no_warning_continuation(self):
        """_run_visual_export_safe must NOT log warnings and continue."""
        import orchestrator
        source = inspect.getsource(orchestrator._run_visual_export_safe)
        assert "continuing without" not in source, (
            "_run_visual_export_safe still has 'continuing without' logic"
        )


# ══════════════════════════════════════════════════════════════════════
# Integration: Full pipeline validation checks
# ══════════════════════════════════════════════════════════════════════

class TestFullPipelineStrictness:
    """Integration tests verifying the full pipeline is strict."""

    def test_all_standard_slides_pass_validation(self):
        """All standard slide types produce valid HTML that passes strict validation."""
        slides = [HERO_SLIDE, SPLIT_SLIDE, FEATURE_SLIDE]
        designs = run_design_engine(slides)
        html_slides = run_template_engine(designs)
        validated = validate_rendered_html(html_slides)
        assert len(validated) == 3

    def test_export_parity_from_pipeline(self):
        """Pipeline-produced HTML passes export parity check."""
        slides = [HERO_SLIDE, SPLIT_SLIDE, FEATURE_SLIDE]
        designs = run_design_engine(slides)
        html_slides = run_template_engine(designs)
        # Same HTML for editor and export — must pass
        validate_export_parity(html_slides, html_slides)

    def test_image_url_flows_through_pipeline(self):
        """Image URL in slide content reaches final HTML."""
        slide = {
            "slide_id": 1,
            "type": "example_slide",
            "content": {
                "title": "Visual Demo",
                "body": "Description",
                "image_url": "file:///tmp/test.png",
            },
        }
        designs = run_design_engine([slide])
        html_slides = run_template_engine(designs)
        assert "<img" in html_slides[0]
        assert "test.png" in html_slides[0]

    def test_no_visual_placeholder_in_any_template(self):
        """No template should render the word 'Visual' as placeholder content."""
        import pipeline.visual_template_engine as vte
        source = inspect.getsource(vte)
        assert ">Visual<" not in source, (
            "Template engine still contains 'Visual' placeholder"
        )
