from models.presentation_state import PresentationState
from services.llm_client import call_llm_json

SCHEMAS = {
    "title_slide": '{"title": "...", "subtitle": "...", "presenter": ""}',
    "section_header": '{"section_title": "...", "tagline": "..."}',
    "agenda_slide": '{"title": "Agenda", "items": ["...", "..."]}',
    "problem_slide": '{"title": "...", "cards": [{"icon": "...", "label": "...", "description": "..."}]}',
    "stats_slide": '{"title": "...", "stat": "...", "stat_label": "...", "description": "...", "source": "..."}',
    "feature_slide": '{"title": "...", "features": [{"icon": "...", "label": "...", "description": "..."}]}',
    "comparison_slide": '{"title": "...", "left_label": "...", "left_points": ["..."], "right_label": "...", "right_points": ["..."]}',
    "timeline_slide": '{"title": "...", "events": [{"year": "...", "label": "..."}]}',
    "example_slide": '{"title": "...", "example_title": "...", "context": "...", "result": "...", "takeaway": "..."}',
    "conclusion_slide": '{"title": "...", "bullets": ["..."], "key_takeaway": "..."}',
    "cta_slide": '{"title": "...", "cta_text": "...", "contact": "..."}',
}

async def generate_structured_content(state: PresentationState) -> PresentationState:
    structured = []
    for slide in state.slide_plan:
        slide_type = slide["type"]
        schema = SCHEMAS.get(slide_type, '{"title": "...", "body": "..."}')

        system = f"You generate structured slide content. Return ONLY valid JSON matching the schema. No extra fields."
        user = f"""
Presentation topic: {state.topic}
Slide section: {slide['section']}
Slide purpose: {slide['purpose']}
Slide type: {slide_type}
Tone: {state.tone}
Audience: {state.audience}
Key message: {state.story.get('key_message', '')}

Fill this JSON schema with real content:
{schema}
"""
        try:
            content = await call_llm_json(system, user)
        except Exception:
            content = {"title": slide["purpose"], "body": "Content unavailable"}

        structured.append({"slide_id": slide["slide_id"], "type": slide_type, "content": content})

    return state.model_copy(update={"structured_slides": structured})