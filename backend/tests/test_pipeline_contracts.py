from pipeline.investor_enforcer import REQUIRED_ROLES, enforce_investor_structure
from pipeline.slide_validator import SlideValidationError, validate_pipeline_contract


def _base_slide(role: str, idx: int) -> dict:
    return {
        "slide_id": idx,
        "role": role,
        "role_in_story": role,
        "primary_element": f"{role} headline",
        "supporting_elements": ["Clear supporting point"],
        "cause": "Linked to previous slide evidence",
        "tension": "Pressure increases before resolution",
        "next_trigger": "Forces next section",
    }


def test_enforce_investor_structure_injects_required_roles_and_target_count():
    slides = [_base_slide("Problem", 1), _base_slide("Solution", 2)]
    enforced = enforce_investor_structure(slides, target_count=8)

    assert len(enforced) == 8
    roles = {s.get("role_in_story") for s in enforced}
    for role in REQUIRED_ROLES:
        assert role in roles


def test_validate_pipeline_contract_rejects_missing_contract_fields():
    slides = [_base_slide("Problem", 1)]
    html = ["<html><body><h1>Problem headline</h1></body></html>"]

    try:
        validate_pipeline_contract(slides, html, expected_slide_count=1)
    except SlideValidationError as exc:
        assert "Missing required role" in str(exc)
    else:
        raise AssertionError("validate_pipeline_contract should fail when required roles are missing")
