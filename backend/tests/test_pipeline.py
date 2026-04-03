"""Tests for the pipeline stages (non-LLM steps)."""
import pytest
from models.presentation_state import PresentationState
from pipeline.state_builder import build_state
from pipeline.slide_planner import plan_slides
from pipeline.slide_type_assigner import assign_slide_types
from pipeline.story_generator import _default_story


def _make_state(**overrides):
    signals = {
        "topic": "AI in Healthcare",
        "presentation_type": "pitch",
        "slide_count": 10,
        "sections": ["intro", "problem", "solution", "benefits", "conclusion"],
        "tone": "professional",
        "audience": "Hospital CTOs",
    }
    signals.update(overrides)
    state = build_state(signals)
    state = state.model_copy(update={"story": _default_story(state)})
    return state


def test_build_state_from_signals():
    state = build_state({"topic": "Test", "tone": "casual"})
    assert state.topic == "Test"
    assert state.tone == "casual"
    assert state.slide_count == 10  # default


def test_build_state_missing_topic_fallback():
    state = build_state({})
    assert state.topic == "Unknown Topic"


def test_slide_planner_creates_slides():
    state = _make_state()
    state = plan_slides(state)
    assert state.slide_plan is not None
    assert len(state.slide_plan) > 0
    # First slide must be title_slide
    assert state.slide_plan[0]["type"] == "title_slide"
    # Last slide must be cta_slide
    assert state.slide_plan[-1]["type"] == "cta_slide"


def test_slide_planner_all_have_section():
    state = _make_state()
    state = plan_slides(state)
    for slide in state.slide_plan:
        assert "section" in slide
        assert "slide_id" in slide


def test_slide_type_assigner_fills_all_types():
    state = _make_state()
    state = plan_slides(state)
    state = assign_slide_types(state)
    for slide in state.slide_plan:
        assert slide.get("type") is not None, f"Slide {slide['slide_id']} has no type"


def test_slide_type_assigner_valid_types():
    valid_types = {
        "title_slide", "section_header", "agenda_slide", "problem_slide",
        "stats_slide", "feature_slide", "comparison_slide", "timeline_slide",
        "example_slide", "quote_slide", "image_slide", "conclusion_slide",
        "cta_slide", "thank_you_slide",
    }
    state = _make_state()
    state = plan_slides(state)
    state = assign_slide_types(state)
    for slide in state.slide_plan:
        assert slide["type"] in valid_types, f"Unknown type: {slide['type']}"


def test_default_story_structure():
    state = PresentationState(topic="Test")
    story = _default_story(state)
    assert "narrative_type" in story
    assert "key_message" in story
    assert "hook" in story
    assert "sections_flow" in story
    assert "call_to_action" in story
    assert len(story["sections_flow"]) > 0
