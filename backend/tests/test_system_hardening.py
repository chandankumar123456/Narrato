"""
Tests for the final system hardening pass.

Covers:
  - Universal schema handling (unknown schemas, mixed/nested structures)
  - Strict validation enforcement (raises on violations, no auto-repair)
  - Content integrity verification
  - Image decision logic (should_use_image)
  - Dynamic item extraction from arbitrary content shapes
"""

import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pipeline.visual_design_engine import (
    run_design_engine,
    select_layout,
    map_components,
    _extract_items,
    _normalize_dict_item,
    _flatten_dict_to_text,
    should_use_image,
)
from pipeline.visual_template_engine import (
    run_template_engine,
    render_slide_html,
)
from pipeline.slide_validator import (
    validate_slide_content,
    validate_design_components,
    SlideValidationError,
    _is_non_empty,
)


# ── Universal Schema Handling Tests ──────────────────────────────────


class TestUnknownSchemaHandling:
    """System must handle ANY schema shape — unknown keys must NOT be dropped."""

    def test_unknown_list_key_extracted(self):
        """An unknown list key (not in known patterns) must still be extracted."""
        content = {
            "title": "Custom Slide",
            "advantages": ["Fast execution", "Low cost", "Scalable"],
        }
        items = _extract_items(content)
        assert len(items) == 3
        assert items[0]["text"] == "Fast execution"

    def test_unknown_dict_list_extracted(self):
        """An unknown list of dicts must be extracted with text synthesis."""
        content = {
            "title": "Analysis",
            "insights": [
                {"finding": "Revenue up 40%", "impact": "High"},
                {"finding": "Churn decreased", "impact": "Medium"},
            ],
        }
        items = _extract_items(content)
        assert len(items) == 2
        # Each item should have synthesized text from finding/impact
        assert items[0]["text"] != ""

    def test_nested_dict_flattened(self):
        """A nested dict value should be flattened into text."""
        content = {
            "title": "System",
            "architecture": {
                "frontend": "React",
                "backend": "FastAPI",
                "database": "PostgreSQL",
            },
        }
        items = _extract_items(content)
        assert len(items) >= 1
        assert "React" in items[0]["text"] or "FastAPI" in items[0]["text"]

    def test_mixed_string_values_fallback(self):
        """Unknown string keys should be extracted as fallback items."""
        content = {
            "title": "Overview",
            "methodology": "Agile sprint-based development",
        }
        items = _extract_items(content)
        assert len(items) == 1
        assert "Agile" in items[0]["text"]

    def test_completely_novel_schema_produces_items(self):
        """A completely novel schema structure must still produce items."""
        content = {
            "title": "Roadmap Q4",
            "milestones": [
                {"name": "Beta launch", "date": "Oct 2024", "status": "planned"},
                {"name": "GA release", "date": "Dec 2024", "status": "planned"},
            ],
        }
        items = _extract_items(content)
        assert len(items) == 2
        assert items[0]["text"] != ""
        assert "Beta launch" in items[0]["text"] or "Beta launch" in items[0].get("name", "")

    def test_unknown_schema_end_to_end(self):
        """Unknown schema must flow through the full pipeline and produce HTML."""
        slide = {
            "type": "custom_slide",
            "content": {
                "title": "Custom Content",
                "recommendations": [
                    "Increase testing coverage",
                    "Add monitoring",
                    "Improve documentation",
                ],
            },
        }
        designs = run_design_engine([slide])
        html_list = run_template_engine(designs)
        assert len(html_list) == 1
        html = html_list[0]
        assert "Custom Content" in html
        # At least some content must appear
        assert "testing" in html.lower() or "monitoring" in html.lower()

    def test_mixed_nested_schema(self):
        """Complex mixed nested schema must be handled."""
        content = {
            "title": "Mixed Data",
            "metrics": {
                "revenue": "$5M",
                "growth": "120%",
                "customers": 500,
            },
        }
        items = _extract_items(content)
        assert len(items) >= 1
        # Should contain flattened dict content
        assert "$5M" in items[0]["text"] or "120%" in items[0]["text"]


class TestNormalizeDictItem:
    """Test the _normalize_dict_item helper for unknown dict structures."""

    def test_label_description(self):
        item = {"label": "Speed", "description": "Very fast"}
        result = _normalize_dict_item(item)
        assert "Speed" in result["text"]
        assert "Very fast" in result["text"]

    def test_name_desc(self):
        item = {"name": "Feature X", "desc": "Powerful feature"}
        result = _normalize_dict_item(item)
        assert "Feature X" in result["text"]

    def test_name_detail(self):
        item = {"name": "Option A", "detail": "Best choice"}
        result = _normalize_dict_item(item)
        assert "Option A" in result["text"]

    def test_name_summary(self):
        item = {"name": "Option B", "summary": "Good choice"}
        result = _normalize_dict_item(item)
        assert "Option B" in result["text"]

    def test_no_known_keys_joins_values(self):
        item = {"foo": "Hello", "bar": "World"}
        result = _normalize_dict_item(item)
        assert result["text"] != ""
        # Should join first 2 values
        assert "Hello" in result["text"] or "World" in result["text"]

    def test_empty_dict(self):
        item = {}
        result = _normalize_dict_item(item)
        assert result["text"] == ""

    def test_has_text_key_preserves(self):
        item = {"text": "Already has text", "extra": "ignored"}
        result = _normalize_dict_item(item)
        assert result["text"] == "Already has text"


class TestFlattenDictToText:
    """Test _flatten_dict_to_text for nested structures."""

    def test_simple_dict(self):
        result = _flatten_dict_to_text({"a": "hello", "b": "world"})
        assert "hello" in result
        assert "world" in result

    def test_nested_dict(self):
        result = _flatten_dict_to_text({"x": {"y": "deep"}})
        assert "deep" in result

    def test_list_in_dict(self):
        result = _flatten_dict_to_text({"tags": ["a", "b", "c"]})
        assert "a" in result

    def test_numbers(self):
        result = _flatten_dict_to_text({"count": 42, "ratio": 3.14})
        assert "42" in result


# ── Strict Validation Tests ──────────────────────────────────────────


class TestStrictValidation:
    """Validation must RAISE on violations — no auto-repair, no silent pass."""

    def test_empty_content_raises_error(self):
        slides = [{"slide_id": 1, "type": "test", "content": {}}]
        with pytest.raises(SlideValidationError) as exc_info:
            validate_slide_content(slides)
        assert len(exc_info.value.violations) == 1

    def test_missing_title_raises_error(self):
        slides = [{"slide_id": 1, "type": "test", "content": {"body": "content"}}]
        with pytest.raises(SlideValidationError) as exc_info:
            validate_slide_content(slides)
        assert "missing title" in exc_info.value.violations[0].lower()

    def test_title_only_raises_error(self):
        slides = [{"slide_id": 1, "type": "test", "content": {"title": "Hello"}}]
        with pytest.raises(SlideValidationError) as exc_info:
            validate_slide_content(slides)
        assert "no content body" in exc_info.value.violations[0].lower()

    def test_valid_slides_no_error(self):
        slides = [
            {"slide_id": 1, "type": "test", "content": {"title": "Hello", "body": "World"}},
        ]
        result = validate_slide_content(slides)
        assert len(result) == 1

    def test_multiple_violations_all_reported(self):
        slides = [
            {"slide_id": 1, "type": "test", "content": {}},
            {"slide_id": 2, "type": "test", "content": {"title": "Only title"}},
            {"slide_id": 3, "type": "test", "content": {"title": "OK", "body": "Valid"}},
        ]
        with pytest.raises(SlideValidationError) as exc_info:
            validate_slide_content(slides)
        # At least 2 violations (slide 1 empty, slide 2 title-only)
        assert len(exc_info.value.violations) >= 2

    def test_design_empty_items_raises(self):
        designs = [{
            "slide_index": 0,
            "layout": "grid_cards",
            "theme": "dark_modern",
            "components": {
                "type": "card_grid",
                "title": "Test",
                "items": [],
            },
        }]
        with pytest.raises(SlideValidationError):
            validate_design_components(designs)

    def test_design_empty_subtitle_raises(self):
        designs = [{
            "slide_index": 0,
            "layout": "hero_center",
            "theme": "dark_modern",
            "components": {
                "type": "hero",
                "title": "Test",
                "subtitle": "",
            },
        }]
        with pytest.raises(SlideValidationError):
            validate_design_components(designs)

    def test_design_valid_passes(self):
        designs = [{
            "slide_index": 0,
            "layout": "hero_center",
            "theme": "dark_modern",
            "components": {
                "type": "hero",
                "title": "Test",
                "subtitle": "Valid subtitle",
            },
        }]
        result = validate_design_components(designs)
        assert len(result) == 1

    def test_design_no_title_raises(self):
        designs = [{
            "slide_index": 0,
            "layout": "grid_cards",
            "theme": "dark_modern",
            "components": {
                "type": "card_grid",
                "title": "",
                "items": [{"text": "item"}],
            },
        }]
        with pytest.raises(SlideValidationError):
            validate_design_components(designs)


# ── Image Decision Logic Tests ───────────────────────────────────────


class TestImageDecisionLogic:
    """Test that images are only used when they improve understanding."""

    def test_abstract_slides_no_image(self):
        """Abstract slides (stats, CTA, conclusion) should NOT use images."""
        for slide_type in ["title_slide", "cta_slide", "conclusion_slide",
                          "stats_slide", "comparison_slide"]:
            slide = {"type": slide_type, "content": {"title": "Test"}}
            assert should_use_image(slide) is False, f"{slide_type} should not use image"

    def test_visual_slides_use_image(self):
        """Visual/concrete slides should use images."""
        for slide_type in ["example_slide", "image_slide", "product"]:
            slide = {"type": slide_type, "content": {"title": "Test"}}
            assert should_use_image(slide) is True, f"{slide_type} should use image"

    def test_unknown_type_conservative(self):
        """Unknown slide types should default to no image."""
        slide = {"type": "random_unknown_type", "content": {"title": "Test"}}
        assert should_use_image(slide) is False

    def test_visual_keyword_in_title(self):
        """Slides with visual keywords in title should use images."""
        slide = {"type": "unknown", "content": {"title": "System Architecture Diagram"}}
        assert should_use_image(slide) is True

    def test_no_keyword_no_image(self):
        """Slides without visual keywords should not use images."""
        slide = {"type": "unknown", "content": {"title": "Revenue Analysis"}}
        assert should_use_image(slide) is False

    def test_empty_type_no_image(self):
        slide = {"type": "", "content": {"title": "Test"}}
        assert should_use_image(slide) is False

    def test_feature_slide_uses_image(self):
        slide = {"type": "feature_slide", "content": {"title": "Key Features"}}
        assert should_use_image(slide) is True


# ── Content Integrity: End-to-End Verification ──────────────────────


class TestContentIntegrity:
    """Verify content is preserved at every pipeline stage."""

    def test_title_preserved_through_pipeline(self):
        """Title must appear unchanged in final HTML."""
        title = "Unique Title XYZ123"
        slide = {
            "type": "feature_slide",
            "content": {
                "title": title,
                "features": [
                    {"icon": "🔹", "label": "A", "description": "First feature"},
                    {"icon": "🔸", "label": "B", "description": "Second feature"},
                ],
            },
        }
        designs = run_design_engine([slide])
        assert designs[0]["components"]["title"] == title
        html_list = run_template_engine(designs)
        assert title in html_list[0]

    def test_all_items_preserved(self):
        """All items must be present in final HTML."""
        slide = {
            "type": "problem_slide",
            "content": {
                "title": "Issues",
                "cards": [
                    {"icon": "⚠", "label": "Issue Alpha", "description": "First issue"},
                    {"icon": "⚠", "label": "Issue Beta", "description": "Second issue"},
                ],
            },
        }
        designs = run_design_engine([slide])
        components = designs[0]["components"]
        assert len(components["items"]) == 2

        html_list = run_template_engine(designs)
        html = html_list[0]
        assert "Issue Alpha" in html
        assert "Issue Beta" in html

    def test_stats_values_preserved(self):
        """Stat values must appear in final HTML."""
        slide = {
            "type": "stats_slide",
            "content": {
                "title": "Metrics",
                "stat": "99.9%",
                "stat_label": "Uptime SLA",
                "description": "Enterprise grade",
                "source": "Internal",
            },
        }
        designs = run_design_engine([slide])
        html_list = run_template_engine(designs)
        html = html_list[0]
        assert "99.9%" in html
        assert "Uptime SLA" in html

    def test_comparison_points_preserved(self):
        """Comparison points must appear in final HTML."""
        slide = {
            "type": "comparison_slide",
            "content": {
                "title": "Before vs After",
                "left_label": "Before",
                "left_points": ["Slow processing", "Manual tasks"],
                "right_label": "After",
                "right_points": ["Fast pipeline", "Automated"],
            },
        }
        designs = run_design_engine([slide])
        html_list = run_template_engine(designs)
        html = html_list[0]
        assert "Slow processing" in html
        assert "Fast pipeline" in html

    def test_timeline_events_preserved(self):
        """Timeline events must appear in HTML."""
        slide = {
            "type": "timeline_slide",
            "content": {
                "title": "History",
                "events": [
                    {"date": "2020", "description": "Founded"},
                    {"date": "2023", "description": "Series A"},
                ],
            },
        }
        designs = run_design_engine([slide])
        html_list = run_template_engine(designs)
        html = html_list[0]
        assert "2020" in html
        assert "Founded" in html

    def test_unknown_schema_content_preserved(self):
        """Even unknown schemas must produce non-empty HTML with content."""
        slide = {
            "type": "custom",
            "content": {
                "title": "Custom Analysis",
                "findings": ["Revenue up", "Costs down", "Profit stable"],
            },
        }
        designs = run_design_engine([slide])
        html_list = run_template_engine(designs)
        html = html_list[0]
        assert "Custom Analysis" in html
        assert "Revenue up" in html


# ── Empty Content Rejection Tests ────────────────────────────────────


class TestEmptyContentRejection:
    """Empty content must ALWAYS be rejected — never silently passed."""

    def test_content_none_rejected(self):
        with pytest.raises(SlideValidationError):
            validate_slide_content([{"slide_id": 1, "type": "test", "content": None}])

    def test_content_not_dict_rejected(self):
        with pytest.raises(SlideValidationError):
            validate_slide_content([{"slide_id": 1, "type": "test", "content": "string"}])

    def test_content_empty_dict_rejected(self):
        with pytest.raises(SlideValidationError):
            validate_slide_content([{"slide_id": 1, "type": "test", "content": {}}])

    def test_content_title_only_rejected(self):
        with pytest.raises(SlideValidationError):
            validate_slide_content([{"slide_id": 1, "type": "test", "content": {"title": "Test"}}])

    def test_content_with_empty_strings_rejected(self):
        with pytest.raises(SlideValidationError):
            validate_slide_content([{
                "slide_id": 1, "type": "test",
                "content": {"title": "Test", "body": "", "description": ""},
            }])

    def test_content_with_empty_list_rejected(self):
        with pytest.raises(SlideValidationError):
            validate_slide_content([{
                "slide_id": 1, "type": "test",
                "content": {"title": "Test", "items": []},
            }])

    def test_valid_content_passes(self):
        result = validate_slide_content([{
            "slide_id": 1, "type": "test",
            "content": {"title": "Test", "body": "Non-empty content"},
        }])
        assert len(result) == 1
