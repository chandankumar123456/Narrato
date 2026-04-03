from models.presentation_state import PresentationState
from services.llm_client import call_llm_json_list
from services.image_service import fetch_image
import asyncio

NO_IMAGE_TYPES = {"title_slide", "section_header", "stats_slide", "cta_slide"}

async def generate_visual_queries(state: PresentationState) -> PresentationState:
    slides_needing_images = [
        s for s in state.structured_slides
        if s["type"] not in NO_IMAGE_TYPES and state.image_preference
    ]

    if not slides_needing_images:
        return state.model_copy(update={"image_queries": []})

    system = "Generate concise Unsplash/Pexels image search queries for presentation slides. Return JSON array of strings."
    user = f"""
Topic: {state.topic}
Generate one image query per slide below:
{[{"type": s["type"], "title": s["content"].get("title", "")} for s in slides_needing_images]}

Return: ["query1", "query2", ...]
"""
    try:
        queries = await call_llm_json_list(system, user)
    except Exception:
        queries = [state.topic] * len(slides_needing_images)

    # Fetch images concurrently
    image_paths = await asyncio.gather(*[fetch_image(q) for q in queries])

    # Attach paths back to slides
    query_idx = 0
    updated_slides = []
    for slide in state.structured_slides:
        if slide["type"] not in NO_IMAGE_TYPES and state.image_preference:
            slide = {**slide, "image_path": image_paths[query_idx]}
            query_idx += 1
        else:
            slide = {**slide, "image_path": None}
        updated_slides.append(slide)

    return state.model_copy(update={"structured_slides": updated_slides, "image_queries": queries})