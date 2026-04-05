from models.presentation_state import PresentationState
from services.llm_client import call_llm_json_list
from services.image_service import fetch_image
from services.ai_image_service import generate_image_for_slide
import asyncio
import logging
import os

logger = logging.getLogger(__name__)

NO_IMAGE_TYPES = {"title_slide", "section_header", "stats_slide", "cta_slide"}

async def generate_visual_queries(state: PresentationState) -> PresentationState:
    slides_needing_images = [
        s for s in state.structured_slides
        if s["type"] not in NO_IMAGE_TYPES and state.image_preference
    ]

    if not slides_needing_images:
        return state.model_copy(update={"image_queries": []})

    # Step 1: Try AI image generation (DALL-E) first
    output_dir = os.environ.get("NARRATO_OUTPUT_DIR", "./outputs")
    image_results = await asyncio.gather(
        *[generate_image_for_slide(s, output_dir) for s in slides_needing_images],
        return_exceptions=True,
    )
    # Convert exceptions to None
    image_paths = [
        r if isinstance(r, str) else None
        for r in image_results
    ]

    # Step 2: For slides where AI generation failed, fall back to stock photos
    queries: list[str] = []
    needs_stock = any(p is None for p in image_paths)
    if needs_stock:
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

        # Fetch stock images for slides that don't have AI images
        for i, path in enumerate(image_paths):
            if path is None and i < len(queries):
                try:
                    stock_path = await fetch_image(queries[i])
                    if stock_path:
                        image_paths[i] = stock_path
                except Exception:
                    pass

    # Step 3: Attach image paths to slides — CRITICAL: store as content.image_url
    # so the design engine can find them (it reads content.get("image_url"))
    query_idx = 0
    updated_slides = []
    for slide in state.structured_slides:
        if slide["type"] not in NO_IMAGE_TYPES and state.image_preference:
            img_path = image_paths[query_idx] if query_idx < len(image_paths) else None
            # Store image path in BOTH locations for full pipeline compatibility:
            # - slide["image_path"] for backward compatibility
            # - slide["content"]["image_url"] for design engine → template engine flow
            updated_slide = {**slide, "image_path": img_path}
            if img_path:
                # Convert to absolute file:// URI for Playwright rendering
                abs_path = os.path.abspath(img_path)
                image_url = f"file://{abs_path}"
                updated_content = {**slide.get("content", {}), "image_url": image_url}
                updated_slide["content"] = updated_content
                logger.info("[visual_mapper] Slide %s: image_url = %s",
                           slide.get("slide_id", query_idx), image_url)
            query_idx += 1
        else:
            updated_slide = {**slide, "image_path": None}
        updated_slides.append(updated_slide)

    return state.model_copy(update={"structured_slides": updated_slides, "image_queries": queries})