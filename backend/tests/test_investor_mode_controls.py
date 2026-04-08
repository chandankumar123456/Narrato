import pytest

from orchestrator import _detect_presentation_mode
from pipeline.narrative_engine import (
    _apply_investor_importance_weighting,
    _has_high_impact_slide,
    _inject_high_impact_slide,
    validate_narrative_arc,
    TRANSITION_REPAIR_TEXT,
    CAUSE_REPAIR_TEXT,
    NEXT_TRIGGER_REPAIR_TEXT,
)
from pipeline.state_builder import build_state


def test_detect_presentation_mode_investor():
    prompt = "Create a pitch deck for a SaaS startup funding round"
    assert _detect_presentation_mode(prompt) == "investor"


def test_detect_presentation_mode_academic():
    prompt = "Prepare a seminar explanation for subject learning outcomes"
    assert _detect_presentation_mode(prompt) == "academic"


def test_detect_presentation_mode_generic():
    prompt = "Create slides about team onboarding process"
    assert _detect_presentation_mode(prompt) == "generic"


def test_build_state_carries_presentation_mode():
    state = build_state({"topic": "AI", "presentation_mode": "investor"})
    assert state.presentation_mode == "investor"


def test_investor_controls_inject_high_impact_slide():
    slides = [
        {
            "intent": "problem",
            "role_in_story": "Problem",
            "key_message": "Manual reporting causes avoidable losses",
            "transition_reason": "Losses escalate every quarter",
            "emotional_tone": "urgent",
            "cause": "Fragmented workflows",
            "tension": "Costs keep rising",
            "resolution": "",
            "next_trigger": "Need decisive intervention",
        },
        {
            "intent": "closure",
            "role_in_story": "Closure",
            "key_message": "Act now",
            "transition_reason": "Window is narrowing quickly",
            "emotional_tone": "decisive",
            "cause": "Competition is accelerating",
            "tension": "Delay compounds risk",
            "resolution": "",
            "next_trigger": "Move to execution",
        },
    ]

    weighted = _apply_investor_importance_weighting(slides)
    assert all("importance" in s for s in weighted)
    assert not _has_high_impact_slide(weighted)

    injected = _inject_high_impact_slide(weighted)
    assert _has_high_impact_slide(injected)
    assert any(s.get("importance") == "high" for s in injected)


def test_validate_narrative_arc_repairs_weak_fields_without_failure():
    slides = [
        {
            "intent": "context",
            "role_in_story": "Context",
            "key_message": "Opening setup",
            "transition_reason": "",
            "emotional_tone": "neutral",
            "cause": "",
            "tension": "",
            "resolution": "",
            "next_trigger": "next step",
            "importance": "low",
        },
        {
            "intent": "problem",
            "role_in_story": "Problem",
            "key_message": "Core problem",
            "transition_reason": "next step",
            "emotional_tone": "urgent",
            "cause": "follows previous idea",
            "tension": "high pressure",
            "resolution": "",
            "next_trigger": "then we see",
            "importance": "high",
        },
    ]

    repaired = validate_narrative_arc(slides, target_count=2)
    assert len(repaired) == 2
    assert repaired[0]["importance"] == "low"
    assert repaired[1]["importance"] == "high"
    assert repaired[1]["transition_reason"] == TRANSITION_REPAIR_TEXT
    assert repaired[1]["cause"] == CAUSE_REPAIR_TEXT
    assert repaired[1]["next_trigger"] == NEXT_TRIGGER_REPAIR_TEXT
    assert repaired[1]["cause_from_previous"] == CAUSE_REPAIR_TEXT
    assert repaired[1]["forward_tension"] == NEXT_TRIGGER_REPAIR_TEXT
    assert repaired[1]["narrative_delta"]
    assert isinstance(repaired[1]["tension_level"], int)


def test_validate_narrative_arc_fills_required_keys_softly():
    repaired = validate_narrative_arc([{"key_message": "Only one field"}], target_count=1)
    slide = repaired[0]
    for key in {
        "intent",
        "role_in_story",
        "slide_role",
        "key_message",
        "transition_reason",
        "emotional_tone",
        "cause_from_previous",
        "narrative_delta",
        "forward_tension",
        "tension_level",
        "cause",
        "tension",
        "resolution",
        "next_trigger",
    }:
        assert key in slide
