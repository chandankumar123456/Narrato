from pipeline.narrative_validator import validate_narrative_arc


def test_validate_narrative_arc_marks_weak_causal_fields_invalid():
    arc = [
        {
            "slide_role": "Problem",
            "key_message": "Manual follow-up causes delayed revenue realization",
            "transition_reason": "next step",
            "cause_from_previous": "",
            "narrative_delta": "",
            "forward_tension": "this creates need for action",
        },
        {
            "slide_role": "Solution",
            "key_message": "Automated playbooks close follow-up gaps quickly",
            "transition_reason": "logical continuation",
            "cause_from_previous": "follows logically from previous slide",
            "narrative_delta": "better outcomes",
            "forward_tension": "next step",
        },
    ]

    result = validate_narrative_arc(arc)
    assert result["invalid_slide_indices"] == [0, 1]
    assert any("weak or missing cause_from_previous" in v for v in result["violations"])
    assert any("weak or missing narrative_delta" in v for v in result["violations"])
    assert any("weak or missing forward_tension" in v for v in result["violations"])
    assert any("weak or missing transition_reason" in v for v in result["violations"])


def test_validate_narrative_arc_requires_previous_key_message_reference():
    arc = [
        {
            "slide_role": "Problem",
            "key_message": "Onboarding delays increase customer churn",
            "transition_reason": "Delays expose compounding churn risk each month",
            "cause_from_previous": "Initial conditions reveal accelerating onboarding failures",
            "narrative_delta": "The problem shifts from inefficiency to retention damage",
            "forward_tension": "Retention losses force an intervention decision now",
        },
        {
            "slide_role": "Consequence",
            "key_message": "Revenue volatility blocks predictable planning",
            "transition_reason": "Churn volatility makes growth forecasts unreliable for investors",
            "cause_from_previous": "Market seasonality creates uncertainty in planning assumptions",
            "narrative_delta": "The narrative moves from churn to forecast instability",
            "forward_tension": "Planning instability forces a structural response",
        },
    ]

    result = validate_narrative_arc(arc)
    assert result["invalid_slide_indices"] == [1]
    assert any("does not reference previous key_message" in v for v in result["violations"])
