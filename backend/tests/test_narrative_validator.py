from pipeline.narrative_validator import validate_narrative_arc


def test_validate_narrative_arc_repairs_required_causal_fields():
    arc = [
        {
            "role_in_story": "Problem",
            "key_message": "Teams lose deals from slow follow-up",
            "transition_reason": "next step",
            "cause": "",
            "next_trigger": "next step",
        },
        {
            "role_in_story": "Solution",
            "key_message": "Automated outreach closes the speed gap",
            "transition_reason": "logical continuation",
            "cause_from_previous": "",
            "narrative_delta": "",
            "forward_tension": "",
            "tension_level": "bad",
        },
    ]

    repaired = validate_narrative_arc(arc)
    assert len(repaired) == 2
    for slide in repaired:
        assert slide.get("cause_from_previous")
        assert slide.get("narrative_delta")
        assert slide.get("forward_tension")
        assert isinstance(slide.get("tension_level"), int)
        assert 0 <= slide.get("tension_level") <= 10
        assert slide.get("slide_role")


def test_validate_narrative_arc_enforces_tension_curve():
    arc = [
        {"slide_role": "Problem", "key_message": "P", "cause_from_previous": "x x x x x", "narrative_delta": "d", "forward_tension": "f f f f f", "transition_reason": "t t t t t", "tension_level": 1},
        {"slide_role": "Escalation", "key_message": "E", "cause_from_previous": "x x x x x", "narrative_delta": "d", "forward_tension": "f f f f f", "transition_reason": "t t t t t", "tension_level": 1},
        {"slide_role": "Solution", "key_message": "S", "cause_from_previous": "x x x x x", "narrative_delta": "d", "forward_tension": "f f f f f", "transition_reason": "t t t t t", "tension_level": 1},
        {"slide_role": "Proof", "key_message": "Pr", "cause_from_previous": "x x x x x", "narrative_delta": "d", "forward_tension": "f f f f f", "transition_reason": "t t t t t", "tension_level": 10},
    ]

    repaired = validate_narrative_arc(arc)
    assert repaired[0]["narrative_delta"] != "d"
    assert repaired[1]["tension_level"] >= repaired[0]["tension_level"]
    assert repaired[2]["tension_level"] >= repaired[1]["tension_level"]
    assert repaired[3]["tension_level"] <= repaired[2]["tension_level"]
