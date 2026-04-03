from models.presentation_state import PresentationState

PURPOSE_TO_TYPE = {
    "section_header": "section_header",
    "Title slide": "title_slide",
    "Call to action": "cta_slide",
    "Problem statement": "problem_slide",
    "stats": "stats_slide",
    "feature": "feature_slide",
    "comparison": "comparison_slide",
    "timeline": "timeline_slide",
    "example": "example_slide",
    "summary": "conclusion_slide",
}

SECTION_DEFAULTS = {
    "intro": ["agenda_slide"],
    "problem": ["problem_slide", "stats_slide"],
    "solution": ["feature_slide", "comparison_slide"],
    "benefits": ["feature_slide", "example_slide", "stats_slide"],
    "conclusion": ["conclusion_slide"],
}

def assign_slide_types(state: PresentationState) -> PresentationState:
    section_counters = {}
    updated = []

    for slide in state.slide_plan:
        if slide.get("type"):
            updated.append(slide)
            continue

        section = slide["section"]
        defaults = SECTION_DEFAULTS.get(section, ["feature_slide"])
        idx = section_counters.get(section, 0)
        slide_type = defaults[idx % len(defaults)]
        section_counters[section] = idx + 1

        updated.append({**slide, "type": slide_type})

    return state.model_copy(update={"slide_plan": updated})