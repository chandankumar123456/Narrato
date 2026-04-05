from models.presentation_state import PresentationState
from services.ai_image_service import generate_image_for_slide
import asyncio
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

NO_IMAGE_TYPES = {"title_slide", "section_header", "stats_slide", "cta_slide"}


class ImageGenerationError(RuntimeError):
    """Raised when AI image generation fails for a slide that requires an image."""
    pass


async def generate_visual_queries(state: PresentationState) -> PresentationState:
    slides_needing_images = [
        s for s in state.structured_slides
        if s["type"] not in NO_IMAGE_TYPES and state.image_preference
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
    image_paths: list[str] = []
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
        image_paths.append(result)

    # Attach image paths to slides — CRITICAL: store as content.image_url
    # so the design engine can find them (it reads content.get("image_url"))
    query_idx = 0
    updated_slides = []
    for slide in state.structured_slides:
        if slide["type"] not in NO_IMAGE_TYPES and state.image_preference:
            img_path = image_paths[query_idx] if query_idx < len(image_paths) else None
            updated_slide = {**slide, "image_path": img_path}
            if img_path:
                # Convert to absolute file URI for Playwright rendering (cross-platform)
                image_url = Path(os.path.abspath(img_path)).as_uri()
                updated_content = {**slide.get("content", {}), "image_url": image_url}
                updated_slide["content"] = updated_content
                logger.info("[visual_mapper] Slide %s: image_url = %s",
                           slide.get("slide_id", query_idx), image_url)
            query_idx += 1
        else:
            updated_slide = {**slide, "image_path": None}
        updated_slides.append(updated_slide)

    return state.model_copy(update={"structured_slides": updated_slides, "image_queries": []})