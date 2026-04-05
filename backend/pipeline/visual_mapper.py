from models.presentation_state import PresentationState
from services.ai_image_service import generate_image_for_slide
from pipeline.visual_design_engine import should_use_image
import asyncio
import logging
import os

logger = logging.getLogger(__name__)


class ImageGenerationError(RuntimeError):
    """Raised when AI image generation fails for a slide that requires an image."""
    pass


async def generate_visual_queries(state: PresentationState) -> PresentationState:
    slides_needing_images = [
        s for s in state.structured_slides
        if should_use_image(s) and state.image_preference
    ]

    if not slides_needing_images:
        return state.model_copy(update={"image_queries": []})

    # Generate AI images — STRICT: no fallbacks, no stock photos
    output_dir = os.environ.get("NARRATO_OUTPUT_DIR", "./outputs")
    image_results = await asyncio.gather(
        *[generate_image_for_slide(s, output_dir) for s in slides_needing_images],
        return_exceptions=True,
    )

    # STRICT: if any image generation failed, raise immediately
    image_urls: list[str] = []
    for i, result in enumerate(image_results):
        if isinstance(result, Exception):
            slide_title = slides_needing_images[i].get("content", {}).get("title", "?")
            raise ImageGenerationError(
                f"AI image generation failed for slide '{slide_title}': {result}"
            )
        if result is None:
            slide_title = slides_needing_images[i].get("content", {}).get("title", "?")
            raise ImageGenerationError(
                f"AI image generation returned None for slide '{slide_title}' — "
                f"every image MUST be AI-generated via OpenAI API"
            )
        image_urls.append(result)

    # Attach image URLs to slides — CRITICAL: store as content.image_url
    # so the design engine can find them (it reads content.get("image_url"))
    # generate_image_for_slide already returns file:// URIs
    assert len(image_urls) == len(slides_needing_images), (
        f"Image URL count ({len(image_urls)}) != slide count ({len(slides_needing_images)})"
    )
    query_idx = 0
    updated_slides = []
    for slide in state.structured_slides:
        if should_use_image(slide) and state.image_preference:
            image_url = image_urls[query_idx] if query_idx < len(image_urls) else None
            updated_slide = {**slide}
            if image_url:
                updated_content = {**slide.get("content", {}), "image_url": image_url}
                updated_slide["content"] = updated_content
                logger.info("[visual_mapper] Slide %s: image_url = %s",
                           slide.get("slide_id", query_idx), image_url)
            query_idx += 1
        else:
            updated_slide = {**slide}
        updated_slides.append(updated_slide)

    return state.model_copy(update={"structured_slides": updated_slides, "image_queries": []})