"""Tests for PresentationState model."""
import pytest
from models.presentation_state import PresentationState


def test_state_defaults():
    state = PresentationState(topic="Test Topic")
    assert state.topic == "Test Topic"
    assert state.slide_count == 10
    assert state.tone == "professional"
    assert state.presentation_type == "general"
    assert state.language == "en"
    assert state.theme == "modern"


def test_state_slide_count_clamped_low():
    state = PresentationState(topic="Test", slide_count=2)
    assert state.slide_count == 5


def test_state_slide_count_clamped_high():
    state = PresentationState(topic="Test", slide_count=100)
    assert state.slide_count == 30


def test_state_optional_fields():
    state = PresentationState(topic="Test")
    assert state.story is None
    assert state.slide_plan is None
    assert state.structured_slides is None
    assert state.speaker_notes is None
    assert state.output_path is None


def test_state_model_copy():
    state = PresentationState(topic="Test")
    updated = state.model_copy(update={"tone": "casual", "slide_count": 15})
    assert updated.tone == "casual"
    assert updated.slide_count == 15
    assert state.tone == "professional"  # original unchanged
