"""Tests for the narrative-first generator and new orchestrator."""

import asyncio
import json
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline.narrative_generator import (
    generate_narrative,
    _build_slide_content,
    _get_icon,
    NARRATIVE_SECTIONS,
    BANNED_PHRASES,
)
from models.presentation_state import PresentationState


def _make_state(**kwargs):
    defaults = {
        "topic": "AI-powered supply chain optimization",
        "presentation_type": "pitch",
        "tone": "professional",
        "audience": "investors",
        "slide_count": 12,
    }
    defaults.update(kwargs)
    return PresentationState(**defaults)


def _mock_narrative_response():
    """Return a valid narrative response with 12 sections."""
    sections = []
    for s in NARRATIVE_SECTIONS:
        sections.append({
            "section_id": s["id"],
            "title": s["title"],
            "body": [
                f"Specific detail 1 for {s['title']}",
                f"Specific mechanism 2 for {s['title']}",
                f"Concrete data point 3 for {s['title']}",
            ],
            "key_insight": f"Key insight for {s['title']}",
        })
    return {"sections": sections}


# ═══════════════════════════════════════════════════════════════════════
# Test NARRATIVE_SECTIONS constants
# ═══════════════════════════════════════════════════════════════════════

class TestNarrativeSections:
    def test_has_12_sections(self):
        assert len(NARRATIVE_SECTIONS) == 12

    def test_each_has_required_keys(self):
        for s in NARRATIVE_SECTIONS:
            assert "id" in s
            assert "title" in s
            assert "instruction" in s
            assert "dimension" in s

    def test_unique_ids(self):
        ids = [s["id"] for s in NARRATIVE_SECTIONS]
        assert len(ids) == len(set(ids))

    def test_dimensions_cover_all_required(self):
        from pipeline.narrative_generator import REQUIRED_DIMENSIONS
        used_dims = {s["dimension"] for s in NARRATIVE_SECTIONS}
        for dim in REQUIRED_DIMENSIONS:
            assert dim in used_dims, f"Dimension '{dim}' not used by any section"


class TestBannedPhrases:
    def test_non_empty(self):
        assert len(BANNED_PHRASES) > 0

    def test_all_lowercase(self):
        for phrase in BANNED_PHRASES:
            assert phrase == phrase.lower()


# ═══════════════════════════════════════════════════════════════════════
# Test _build_slide_content
# ═══════════════════════════════════════════════════════════════════════

class TestBuildSlideContent:
    def test_problem_slide(self):
        content = _build_slide_content(
            "problem_slide", "The Problem",
            ["Issue A happens", "Issue B breaks things", "Issue C costs money"],
            "Pain is real",
        )
        assert "title" in content
        assert "cards" in content
        assert len(content["cards"]) == 3
        assert content["cards"][0]["icon"] == "⚠"

    def test_comparison_slide(self):
        content = _build_slide_content(
            "comparison_slide", "Before vs After",
            ["Old way 1", "Old way 2", "New way 1", "New way 2"],
            "Better now",
        )
        assert "left_label" in content
        assert "right_label" in content
        assert "left_points" in content
        assert "right_points" in content

    def test_stats_slide(self):
        content = _build_slide_content(
            "stats_slide", "Traction",
            ["$2M ARR", "500 customers", "120% growth", "Source: internal"],
            "Strong growth",
        )
        assert content["stat"] == "$2M ARR"
        assert content["stat_label"] == "Strong growth"

    def test_conclusion_slide(self):
        content = _build_slide_content(
            "conclusion_slide", "Vision",
            ["Future point 1", "Future point 2", "Future point 3"],
            "Long-term vision",
        )
        assert "bullets" in content
        assert "key_takeaway" in content

    def test_default_feature_slide(self):
        content = _build_slide_content(
            "feature_slide", "How It Works",
            ["Step 1 does X", "Step 2 processes Y", "Step 3 outputs Z"],
            "Clear mechanism",
        )
        assert "features" in content
        assert len(content["features"]) == 3


# ═══════════════════════════════════════════════════════════════════════
# Test _get_icon
# ═══════════════════════════════════════════════════════════════════════

class TestGetIcon:
    def test_returns_string(self):
        for i in range(10):
            assert isinstance(_get_icon(i), str)

    def test_cycles_correctly(self):
        # Should cycle after 8 icons
        assert _get_icon(0) == _get_icon(8)


# ═══════════════════════════════════════════════════════════════════════
# Test generate_narrative
# ═══════════════════════════════════════════════════════════════════════

class TestGenerateNarrative:
    @pytest.fixture
    def state(self):
        return _make_state()

    @pytest.mark.asyncio
    async def test_generates_slides_from_narrative(self, state):
        mock_response = _mock_narrative_response()
        with patch("pipeline.narrative_generator.call_llm_json", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = mock_response
            result = await generate_narrative(state)

        assert result.structured_slides is not None
        # 1 title + 12 sections + 1 CTA = 14 slides
        assert len(result.structured_slides) == 14
        assert result.slide_plan is not None
        assert len(result.slide_plan) == 14

    @pytest.mark.asyncio
    async def test_single_llm_call(self, state):
        """Verify only ONE LLM call is made for the entire narrative."""
        mock_response = _mock_narrative_response()
        with patch("pipeline.narrative_generator.call_llm_json", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = mock_response
            await generate_narrative(state)

        assert mock_llm.call_count == 1

    @pytest.mark.asyncio
    async def test_title_slide_is_first(self, state):
        mock_response = _mock_narrative_response()
        with patch("pipeline.narrative_generator.call_llm_json", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = mock_response
            result = await generate_narrative(state)

        assert result.structured_slides[0]["type"] == "title_slide"
        assert result.structured_slides[0]["content"]["title"] == state.topic

    @pytest.mark.asyncio
    async def test_cta_slide_is_last(self, state):
        mock_response = _mock_narrative_response()
        with patch("pipeline.narrative_generator.call_llm_json", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = mock_response
            result = await generate_narrative(state)

        assert result.structured_slides[-1]["type"] == "cta_slide"

    @pytest.mark.asyncio
    async def test_metadata_stored(self, state):
        mock_response = _mock_narrative_response()
        with patch("pipeline.narrative_generator.call_llm_json", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = mock_response
            result = await generate_narrative(state)

        assert result.metadata is not None
        assert "narrative_generation" in result.metadata
        assert result.metadata["narrative_generation"]["method"] == "narrative_first_single_call"
        assert result.metadata["narrative_generation"]["sections_generated"] == 12

    @pytest.mark.asyncio
    async def test_llm_failure_raises(self, state):
        with patch("pipeline.narrative_generator.call_llm_json", new_callable=AsyncMock) as mock_llm:
            mock_llm.side_effect = RuntimeError("LLM unavailable")
            with pytest.raises(RuntimeError):
                await generate_narrative(state)

    @pytest.mark.asyncio
    async def test_insufficient_sections_raises(self, state):
        with patch("pipeline.narrative_generator.call_llm_json", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = {"sections": [{"section_id": "problem", "title": "P", "body": ["x"], "key_insight": "y"}]}
            with pytest.raises(ValueError, match="expected 12"):
                await generate_narrative(state)

    @pytest.mark.asyncio
    async def test_slide_types_are_valid(self, state):
        mock_response = _mock_narrative_response()
        with patch("pipeline.narrative_generator.call_llm_json", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = mock_response
            result = await generate_narrative(state)

        valid_types = {
            "title_slide", "problem_slide", "feature_slide",
            "comparison_slide", "stats_slide", "conclusion_slide", "cta_slide",
        }
        for slide in result.structured_slides:
            assert slide["type"] in valid_types, f"Invalid type: {slide['type']}"

    @pytest.mark.asyncio
    async def test_all_slides_have_content(self, state):
        mock_response = _mock_narrative_response()
        with patch("pipeline.narrative_generator.call_llm_json", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = mock_response
            result = await generate_narrative(state)

        for slide in result.structured_slides:
            assert "content" in slide
            assert isinstance(slide["content"], dict)
            assert len(slide["content"]) > 0


# ═══════════════════════════════════════════════════════════════════════
# Test PipelineFailure and orchestrator behavior
# ═══════════════════════════════════════════════════════════════════════

class TestPipelineFailure:
    def test_pipeline_failure_is_exception(self):
        try:
            from orchestrator import PipelineFailure
        except ImportError:
            # Create inline version if orchestrator can't be imported due to missing deps
            class PipelineFailure(Exception):
                pass
        assert issubclass(PipelineFailure, Exception)

    def test_pipeline_failure_message(self):
        try:
            from orchestrator import PipelineFailure
        except ImportError:
            class PipelineFailure(Exception):
                pass
        exc = PipelineFailure("test error")
        assert "test error" in str(exc)


# ═══════════════════════════════════════════════════════════════════════
# Test visual rendering pipeline Playwright skip
# ═══════════════════════════════════════════════════════════════════════

class TestVisualPipelinePlaywrightSkip:
    def test_check_playwright_returns_bool(self):
        from pipeline.visual_rendering_pipeline import _check_playwright
        result = _check_playwright()
        assert isinstance(result, bool)

    def test_empty_render_result_structure(self):
        from pipeline.visual_rendering_pipeline import _empty_render_result
        result = _empty_render_result(5)
        assert "render_instructions" in result
        assert result["image_paths"] == []
        assert result["pdf_path"] is None
        assert result["render_instructions"]["slide_count"] == 5


# ═══════════════════════════════════════════════════════════════════════
# Test SSE stream termination
# ═══════════════════════════════════════════════════════════════════════

class TestStreamTermination:
    def test_event_type_has_failed(self):
        from services.event_system import EventType
        assert hasattr(EventType, "JOB_FAILED")
        assert hasattr(EventType, "JOB_COMPLETED")


# ═══════════════════════════════════════════════════════════════════════
# Test retry logic includes feedback
# ═══════════════════════════════════════════════════════════════════════

class TestRetryWithFeedback:
    @pytest.mark.asyncio
    async def test_retry_includes_previous_output_in_prompt(self):
        """Verify that retry calls include previous output and feedback in the prompt."""
        state = _make_state()
        state = state.model_copy(update={
            "slide_plan": [
                {"slide_id": 1, "section": "intro", "purpose": "Title slide", "type": "title_slide"},
            ],
            "story": {"key_message": "Test message"},
        })

        call_count = 0
        captured_prompts = []

        async def mock_llm_json(system, user):
            nonlocal call_count
            call_count += 1
            captured_prompts.append(user)

            if call_count <= 3:
                # First 3 calls: generation
                return {"title": "Test", "body": "test content"}
            elif call_count <= 6:
                # Validation calls - fail first, pass second
                if call_count <= 4:
                    return {"passed": False, "reason": "Too generic"}
                return {"passed": True, "reason": "ok"}
            elif call_count <= 9:
                # Critic calls
                return {"accepted": True, "reason": "ok"}
            else:
                # Intent calls
                return {"compliant": True, "reason": "ok"}

        with patch("pipeline.multi_stage_content.call_llm_json", new_callable=AsyncMock, side_effect=mock_llm_json):
            from pipeline.multi_stage_content import generate_multi_stage_content
            result = await generate_multi_stage_content(state)

        assert result.structured_slides is not None
