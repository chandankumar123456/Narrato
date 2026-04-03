from models.presentation_state import PresentationState

SECTION_WEIGHTS = {
    "intro": 0.10,
    "problem": 0.20,
    "solution": 0.25,
    "benefits": 0.30,
    "conclusion": 0.15,
}

def plan_slides(state: PresentationState) -> PresentationState:
    sections_flow = state.story["sections_flow"]
    total = state.slide_count
    slides = []
    slide_id = 1

    for i, sec in enumerate(sections_flow):
        section = sec["section"]
        weight = SECTION_WEIGHTS.get(section, 1 / len(sections_flow))
        count = max(1, round(total * weight))

        # Section header (except for intro)
        if i > 0:
            slides.append({"slide_id": slide_id, "section": section, "purpose": "section_header", "type": "section_header"})
            slide_id += 1

        for j in range(count):
            slides.append({"slide_id": slide_id, "section": section, "purpose": sec["purpose"], "type": None})
            slide_id += 1

    # Always start with title slide
    slides.insert(0, {"slide_id": 0, "section": "intro", "purpose": "Title slide", "type": "title_slide"})

    # Always end with CTA + thank you
    slides.append({"slide_id": slide_id, "section": "conclusion", "purpose": "Call to action", "type": "cta_slide"})

    return state.model_copy(update={"slide_plan": slides})