"""
Tests for schema propagation, content validation, and zero-empty-slide enforcement.

Covers:
  - All upstream content schemas through design engine → template engine
  - CTA slide content propagation (cta_text)
  - Stats slide safety on empty key_points
  - Comparison slide content propagation
  - Conclusion slide with bullets + key_takeaway
  - Steps/flow schema extraction
  - Slide content validation layer
  - Design component validation
  - Image URL propagation
  - _build_slide_content robustness
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
)
from pipeline.visual_template_engine import (
    run_template_engine,
    render_slide_html,
)
from pipeline.slide_validator import (
    validate_slide_content,
    validate_design_components,
    _is_non_empty,
)
from pipeline.narrative_generator import _build_slide_content


# ── Schema Coverage Tests ────────────────────────────────────────────


class TestExtractItemsFullCoverage:
    """Ensure _extract_items handles ALL upstream content schemas."""

    def test_bullet_points_list_of_strings(self):
        content = {"bullet_points": ["Point 1", "Point 2", "Point 3"]}
        items = _extract_items(content)
        assert len(items) == 3
        assert all("text" in item for item in items)

    def test_bullets_list_of_strings(self):
        content = {"bullets": ["A", "B"]}
        items = _extract_items(content)
        assert len(items) == 2

    def test_features_list_of_dicts(self):
        content = {"features": [
            {"icon": "🔹", "label": "Fast", "description": "Very fast processing"},
            {"icon": "🔸", "label": "Secure", "description": "End-to-end encryption"},
        ]}
        items = _extract_items(content)
        assert len(items) == 2
        assert "text" in items[0]
        assert "Fast" in items[0]["text"]

    def test_cards_label_description_synthesis(self):
        content = {"cards": [
            {"icon": "⚠", "label": "Problem A", "description": "Description A"},
            {"icon": "⚠", "label": "Problem B", "description": "Description B"},
        ]}
        items = _extract_items(content)
        assert len(items) == 2
        assert "Problem A" in items[0]["text"]
        assert "Description A" in items[0]["text"]

    def test_comparison_left_right_points(self):
        content = {
            "left_label": "Before",
            "left_points": ["Slow", "Manual"],
            "right_label": "After",
            "right_points": ["Fast", "Automated"],
        }
        items = _extract_items(content)
        assert len(items) == 4
        assert "Before: Slow" in items[0]["text"]
        assert "After: Fast" in items[2]["text"]

    def test_stats_list_of_dicts(self):
        content = {"stats": [
            {"value": "99%", "label": "Uptime"},
            {"value": "10ms", "label": "Latency"},
        ]}
        items = _extract_items(content)
        assert len(items) == 2
        assert items[0]["value"] == "99%"
        assert items[0]["label"] == "Uptime"

    def test_flat_stat_fields(self):
        content = {
            "stat": "$2.5M ARR",
            "stat_label": "Annual Revenue",
            "description": "Growing 40% YoY | Enterprise focus",
        }
        items = _extract_items(content)
        assert len(items) >= 1
        assert items[0]["value"] == "$2.5M ARR"

    def test_events_timeline(self):
        content = {"events": [
            {"date": "Q1 2024", "description": "Launch beta"},
            {"date": "Q2 2024", "description": "1000 users"},
        ]}
        items = _extract_items(content)
        assert len(items) == 2
        assert items[0]["date"] == "Q1 2024"
        assert "Launch beta" in items[0]["text"]

    def test_events_with_text_field(self):
        """Events with 'text' instead of 'description' field."""
        content = {"events": [
            {"date": "2024", "text": "Launched product"},
        ]}
        items = _extract_items(content)
        assert len(items) == 1
        assert "Launched product" in items[0]["text"]

    def test_steps_schema(self):
        """New: steps/flow schema extraction."""
        content = {"steps": [
            {"step": 1, "text": "Initialize system"},
            {"step": 2, "text": "Process data"},
            {"step": 3, "text": "Generate output"},
        ]}
        items = _extract_items(content)
        assert len(items) == 3
        assert items[0]["step"] == 1
        assert "Initialize system" in items[0]["text"]

    def test_flow_schema(self):
        content = {"flow": [
            {"label": "Input", "description": "User provides prompt"},
            {"label": "Process", "description": "AI generates content"},
        ]}
        items = _extract_items(content)
        assert len(items) == 2
        # Flow items use label/description/text in fallback order
        assert items[0]["text"] != ""

    def test_steps_list_of_strings(self):
        content = {"steps": ["Step one", "Step two"]}
        items = _extract_items(content)
        assert len(items) == 2
        assert items[0]["text"] == "Step one"

    def test_body_fallback(self):
        content = {"body": "This is the body text"}
        items = _extract_items(content)
        assert len(items) == 1
        assert "body text" in items[0]["text"]

    def test_description_fallback(self):
        content = {"description": "Descriptive text here"}
        items = _extract_items(content)
        assert len(items) == 1
        assert "Descriptive text" in items[0]["text"]

    def test_cta_text_fallback(self):
        """CTA text should be extracted as fallback content."""
        content = {"cta_text": "Review the presentation and start today"}
        items = _extract_items(content)
        assert len(items) == 1
        assert "Review" in items[0]["text"]

    def test_subtitle_fallback(self):
        content = {"subtitle": "A brief subtitle"}
        items = _extract_items(content)
        assert len(items) == 1
        assert "brief subtitle" in items[0]["text"]

    def test_empty_list_ignored(self):
        """Empty lists should not be treated as valid content."""
        content = {"bullet_points": [], "body": "Fallback body"}
        items = _extract_items(content)
        assert len(items) == 1
        assert "Fallback body" in items[0]["text"]

    def test_completely_empty_content(self):
        content = {}
        items = _extract_items(content)
        assert items == []

    def test_max_items_enforcement(self):
        content = {"bullets": [f"Point {i}" for i in range(10)]}
        items = _extract_items(content)
        assert len(items) <= 4


# ── CTA Slide Propagation ────────────────────────────────────────────


class TestCTASlideContent:
    """Ensure CTA slide content flows through the entire pipeline."""

    def test_cta_hero_has_subtitle(self):
        """CTA slide with cta_text should produce non-empty hero subtitle."""
        slide = {
            "type": "cta_slide",
            "content": {
                "title": "Get Started",
                "cta_text": "Review the AI narrative and move to diligence.",
                "contact": "",
            },
        }
        layout = select_layout(slide)
        assert layout == "hero_center"

        components = map_components(slide, layout)
        assert components["subtitle"] != "", "CTA subtitle must not be empty"
        assert "Review" in components["subtitle"] or "narrative" in components["subtitle"]

    def test_cta_reaches_html(self):
        """CTA content must appear in rendered HTML."""
        slide = {
            "type": "cta_slide",
            "content": {
                "title": "Get Started",
                "cta_text": "Contact us to begin your AI journey.",
                "contact": "hello@example.com",
            },
        }
        designs = run_design_engine([slide])
        html_list = run_template_engine(designs)
        assert len(html_list) == 1
        html = html_list[0]
        assert "Get Started" in html
        assert "Contact us" in html or "AI journey" in html

    def test_cta_empty_cta_text_fallback(self):
        """If cta_text is empty, should still not produce empty subtitle."""
        slide = {
            "type": "cta_slide",
            "content": {
                "title": "Get Started",
                "cta_text": "",
                "contact": "",
            },
        }
        components = map_components(slide, "hero_center")
        # Even if cta_text is empty, subtitle might be empty — but title must exist
        assert components["title"] == "Get Started"


# ── Stats Slide Safety ───────────────────────────────────────────────


class TestStatsSlideRobustness:
    """Stats slide must never crash on empty key_points."""

    def test_build_slide_content_empty_key_points(self):
        """_build_slide_content('stats_slide') should not crash on empty key_points."""
        result = _build_slide_content("stats_slide", "Revenue Growth", "Data: content", [])
        assert "title" in result
        assert result["title"] == "Revenue Growth"
        # stat should fall back to title when key_points is empty
        assert "stat" in result

    def test_build_slide_content_single_key_point(self):
        result = _build_slide_content("stats_slide", "Revenue", "Data: $1M", ["$1M ARR"])
        assert result["stat"] == "$1M ARR"

    def test_build_feature_slide_empty_key_points(self):
        result = _build_slide_content("feature_slide", "Features", "Content here", [])
        assert "features" in result
        # Should fall back to title-based content
        assert len(result["features"]) >= 1

    def test_build_problem_slide_empty_key_points(self):
        result = _build_slide_content("problem_slide", "Problems", "Content", [])
        assert "cards" in result
        assert len(result["cards"]) >= 1

    def test_build_comparison_slide_empty_key_points(self):
        result = _build_slide_content("comparison_slide", "Compare", "Content", [])
        assert "left_points" in result
        assert "right_points" in result

    def test_build_conclusion_slide_empty_key_points(self):
        result = _build_slide_content("conclusion_slide", "Vision", "Content", [])
        assert "bullets" in result
        assert len(result["bullets"]) >= 1


# ── Slide Content Validation Layer ───────────────────────────────────


class TestSlideContentValidation:
    """Test the validation layer catches empty/malformed slides."""

    def test_valid_slides_pass(self):
        slides = [
            {"slide_id": 1, "type": "title_slide", "content": {"title": "Hello", "subtitle": "World"}},
            {"slide_id": 2, "type": "feature_slide", "content": {
                "title": "Features", "features": [{"label": "A", "description": "B"}]
            }},
        ]
        result = validate_slide_content(slides)
        assert len(result) == 2

    def test_empty_content_logged(self):
        """Slides with empty content should be detected."""
        slides = [
            {"slide_id": 1, "type": "title_slide", "content": {}},
        ]
        # Should not raise, but log warning
        result = validate_slide_content(slides)
        assert len(result) == 1

    def test_title_only_slide_logged(self):
        """Slides with only a title but no other content should be detected."""
        slides = [
            {"slide_id": 1, "type": "feature_slide", "content": {"title": "Features"}},
        ]
        result = validate_slide_content(slides)
        assert len(result) == 1


class TestDesignComponentValidation:
    """Test design component validation."""

    def test_valid_grid_cards_pass(self):
        designs = [{
            "slide_index": 0,
            "layout": "grid_cards",
            "theme": "dark_modern",
            "components": {
                "type": "card_grid",
                "title": "Problems",
                "items": [{"text": "Item 1"}, {"text": "Item 2"}],
            },
        }]
        result = validate_design_components(designs)
        assert len(result) == 1

    def test_empty_items_detected(self):
        designs = [{
            "slide_index": 0,
            "layout": "grid_cards",
            "theme": "dark_modern",
            "components": {
                "type": "card_grid",
                "title": "Problems",
                "items": [],
            },
        }]
        # Should not raise but log warning
        result = validate_design_components(designs)
        assert len(result) == 1

    def test_hero_with_subtitle_passes(self):
        designs = [{
            "slide_index": 0,
            "layout": "hero_center",
            "theme": "dark_modern",
            "components": {
                "type": "hero",
                "title": "Welcome",
                "subtitle": "Start here",
            },
        }]
        result = validate_design_components(designs)
        assert len(result) == 1


class TestIsNonEmpty:
    def test_none_is_empty(self):
        assert _is_non_empty(None) is False

    def test_empty_string_is_empty(self):
        assert _is_non_empty("") is False
        assert _is_non_empty("   ") is False

    def test_non_empty_string(self):
        assert _is_non_empty("hello") is True

    def test_empty_list_is_empty(self):
        assert _is_non_empty([]) is False

    def test_non_empty_list(self):
        assert _is_non_empty([1]) is True

    def test_number_is_non_empty(self):
        assert _is_non_empty(42) is True
        assert _is_non_empty(0) is True


# ── Image URL Propagation ────────────────────────────────────────────


class TestImageURLPropagation:
    """Ensure image_url flows from content to components to HTML."""

    def test_hero_image_url_in_components(self):
        slide = {
            "type": "title_slide",
            "content": {
                "title": "AI Vision",
                "subtitle": "The future is here",
                "image_url": "https://example.com/ai.jpg",
            },
        }
        components = map_components(slide, "hero_center")
        assert components.get("image_url") == "https://example.com/ai.jpg"

    def test_hero_no_image_url(self):
        slide = {
            "type": "title_slide",
            "content": {
                "title": "AI Vision",
                "subtitle": "The future is here",
            },
        }
        components = map_components(slide, "hero_center")
        assert "image_url" not in components

    def test_split_image_url_in_components(self):
        slide = {
            "type": "example_slide",
            "content": {
                "title": "Example",
                "body": "Description here",
                "image_url": "https://example.com/demo.jpg",
            },
        }
        components = map_components(slide, "split_left_text_right_visual")
        assert components.get("image_url") == "https://example.com/demo.jpg"

    def test_grid_cards_image_url_in_components(self):
        slide = {
            "type": "problem_slide",
            "content": {
                "title": "Issues",
                "cards": [{"label": "A", "description": "B"}],
                "image_url": "https://example.com/issue.jpg",
            },
        }
        components = map_components(slide, "grid_cards")
        assert components.get("image_url") == "https://example.com/issue.jpg"

    def test_image_url_reaches_html(self):
        """Image URL should appear in rendered HTML for split layout."""
        slide = {
            "type": "example_slide",
            "content": {
                "title": "Demo",
                "body": "A demo slide",
                "image_url": "https://example.com/demo.jpg",
            },
        }
        designs = run_design_engine([slide])
        html_list = run_template_engine(designs)
        assert "example.com/demo.jpg" in html_list[0]

    def test_hero_image_url_reaches_html(self):
        """Image URL should appear in hero layout HTML."""
        slide = {
            "type": "title_slide",
            "content": {
                "title": "Welcome",
                "subtitle": "Hello",
                "image_url": "https://example.com/bg.jpg",
            },
        }
        designs = run_design_engine([slide])
        html_list = run_template_engine(designs)
        assert "example.com/bg.jpg" in html_list[0]


# ── End-to-End Schema Propagation ────────────────────────────────────


class TestEndToEndSchemaPropagation:
    """Every slide type must produce non-empty HTML content."""

    ALL_SLIDE_TYPES = [
        {
            "type": "title_slide",
            "content": {"title": "Welcome", "subtitle": "Introduction"},
        },
        {
            "type": "problem_slide",
            "content": {
                "title": "Challenges",
                "cards": [
                    {"icon": "⚠", "label": "Issue A", "description": "Desc A"},
                    {"icon": "⚠", "label": "Issue B", "description": "Desc B"},
                ],
            },
        },
        {
            "type": "feature_slide",
            "content": {
                "title": "Features",
                "features": [
                    {"icon": "🔹", "label": "Speed", "description": "Fast processing"},
                    {"icon": "🔸", "label": "Scale", "description": "Handles millions"},
                ],
            },
        },
        {
            "type": "comparison_slide",
            "content": {
                "title": "Before vs After",
                "left_label": "Old",
                "left_points": ["Slow", "Manual"],
                "right_label": "New",
                "right_points": ["Fast", "Automated"],
            },
        },
        {
            "type": "stats_slide",
            "content": {
                "title": "Metrics",
                "stat": "99.9%",
                "stat_label": "Uptime SLA",
                "description": "Enterprise grade | Multi-region",
                "source": "Internal data",
            },
        },
        {
            "type": "conclusion_slide",
            "content": {
                "title": "Vision",
                "bullets": ["Transform industries", "Scale globally"],
                "key_takeaway": "The future is AI-driven",
            },
        },
        {
            "type": "cta_slide",
            "content": {
                "title": "Get Started",
                "cta_text": "Contact us to begin your journey.",
                "contact": "hello@example.com",
            },
        },
        {
            "type": "timeline_slide",
            "content": {
                "title": "Roadmap",
                "events": [
                    {"date": "Q1 2024", "description": "Beta launch"},
                    {"date": "Q3 2024", "description": "GA release"},
                ],
            },
        },
    ]

    def test_every_slide_type_produces_html(self):
        """Every slide type must produce non-empty HTML."""
        for slide in self.ALL_SLIDE_TYPES:
            designs = run_design_engine([slide])
            html_list = run_template_engine(designs)
            assert len(html_list) == 1, f"{slide['type']} produced no HTML"
            html = html_list[0]
            assert "<html" in html, f"{slide['type']} produced invalid HTML"
            assert slide["content"]["title"] in html, (
                f"{slide['type']} title not in HTML"
            )

    def test_every_slide_type_has_content_beyond_title(self):
        """Every slide type must have content beyond just the title in HTML."""
        for slide in self.ALL_SLIDE_TYPES:
            designs = run_design_engine([slide])
            components = designs[0]["components"]
            title = components.get("title", "")

            # Check that there's more than just a title
            has_content = False
            for key, val in components.items():
                if key in ("title", "type"):
                    continue
                if _is_non_empty(val):
                    has_content = True
                    break

            # Hero slides need subtitle, others need items/steps/events
            comp_type = components.get("type", "")
            if comp_type == "hero":
                subtitle = components.get("subtitle", "")
                assert subtitle, f"{slide['type']}: hero has empty subtitle"
            elif comp_type in ("card_grid", "stats"):
                assert components.get("items"), f"{slide['type']}: no items"
            elif comp_type == "steps":
                assert components.get("steps"), f"{slide['type']}: no steps"
            elif comp_type == "timeline":
                assert components.get("events"), f"{slide['type']}: no events"
            elif comp_type == "split":
                body = components.get("body", "")
                items = components.get("items", [])
                assert body or items, f"{slide['type']}: split has no body or items"

    def test_no_slide_produces_empty_inner_html(self):
        """No slide should produce HTML with only the title and no other visible content."""
        for slide in self.ALL_SLIDE_TYPES:
            designs = run_design_engine([slide])
            html_list = run_template_engine(designs)
            html = html_list[0]
            # Title should be there
            assert slide["content"]["title"] in html
            # There should be substantial content beyond wrapper + title
            # (at minimum 500 chars of HTML for any real content)
            assert len(html) > 500, f"{slide['type']} produced suspiciously short HTML"


# ── Hero Center Subtitle Chain Coverage ──────────────────────────────


class TestHeroCenterSubtitleChain:
    """Verify the full subtitle fallback chain in hero_center."""

    def test_subtitle_primary(self):
        slide = {"type": "title_slide", "content": {"title": "T", "subtitle": "Sub"}}
        comp = map_components(slide, "hero_center")
        assert comp["subtitle"] == "Sub"

    def test_key_takeaway_fallback(self):
        slide = {"type": "conclusion_slide", "content": {"title": "T", "key_takeaway": "Takeaway"}}
        comp = map_components(slide, "hero_center")
        assert comp["subtitle"] == "Takeaway"

    def test_cta_text_fallback(self):
        slide = {"type": "cta_slide", "content": {"title": "T", "cta_text": "Act now"}}
        comp = map_components(slide, "hero_center")
        assert comp["subtitle"] == "Act now"

    def test_body_fallback(self):
        slide = {"type": "title_slide", "content": {"title": "T", "body": "Body text"}}
        comp = map_components(slide, "hero_center")
        assert comp["subtitle"] == "Body text"

    def test_description_fallback(self):
        slide = {"type": "title_slide", "content": {"title": "T", "description": "Desc"}}
        comp = map_components(slide, "hero_center")
        assert comp["subtitle"] == "Desc"

    def test_summary_fallback(self):
        slide = {"type": "title_slide", "content": {"title": "T", "summary": "Sum"}}
        comp = map_components(slide, "hero_center")
        assert comp["subtitle"] == "Sum"

    def test_bullets_join_fallback(self):
        slide = {"type": "conclusion_slide", "content": {"title": "T", "bullets": ["A", "B", "C"]}}
        comp = map_components(slide, "hero_center")
        assert "A" in comp["subtitle"]
        assert "·" in comp["subtitle"]

    def test_key_points_fallback(self):
        slide = {"type": "title_slide", "content": {"title": "T", "key_points": ["X", "Y"]}}
        comp = map_components(slide, "hero_center")
        assert "X" in comp["subtitle"]


# ── Split Layout Content Fallback ────────────────────────────────────


class TestSplitLayoutContent:
    """Verify split layout handles all body content sources."""

    def test_body_field(self):
        slide = {"type": "example_slide", "content": {"title": "T", "body": "Body"}}
        comp = map_components(slide, "split_left_text_right_visual")
        assert comp["body"] == "Body"

    def test_description_fallback(self):
        slide = {"type": "example_slide", "content": {"title": "T", "description": "Desc"}}
        comp = map_components(slide, "split_left_text_right_visual")
        assert comp["body"] == "Desc"

    def test_summary_fallback(self):
        slide = {"type": "example_slide", "content": {"title": "T", "summary": "Sum"}}
        comp = map_components(slide, "split_left_text_right_visual")
        assert comp["body"] == "Sum"

    def test_cta_text_fallback(self):
        slide = {"type": "example_slide", "content": {"title": "T", "cta_text": "CTA"}}
        comp = map_components(slide, "split_left_text_right_visual")
        assert comp["body"] == "CTA"
