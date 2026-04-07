from models.presentation_state import PresentationState

INVESTOR_SECTIONS = [
    "intro",
    "problem",
    "solution",
    "market",
    "product",
    "business",
    "traction",
    "competition",
    "gtm",
    "team",
    "ask"
]

SECTION_WEIGHTS = {
    "intro": 0.08,
    "problem": 0.12,
    "solution": 0.12,
    "market": 0.10,
    "product": 0.10,
    "business": 0.10,
    "traction": 0.10,
    "competition": 0.08,
    "gtm": 0.08,
    "team": 0.06,
    "ask": 0.06,
}

def plan_slides(state: PresentationState) -> PresentationState:
    # sections_flow = state.story["sections_flow"]
    # Use investor structure if needed
    if getattr(state, "deck_mode", "general") == "investor":
        sections_flow = [{"section": sec, "purpose": sec} for sec in INVESTOR_SECTIONS]
    else:
        sections_flow = state.story["sections_flow"]
    total = state.slide_count
    slides = []
    slide_id = 1

    for i, sec in enumerate(sections_flow):
        section = sec["section"]
        weight = SECTION_WEIGHTS.get(section, 1 / len(sections_flow))
        # count = max(1, round(total * weight))
        remaining = total - len(slides)
        sections_left = len(sections_flow) - i

        count = max(1, remaining // sections_left)

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