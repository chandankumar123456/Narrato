"""AI Image Generation Service — generates images using OpenAI DALL-E.

Provides real AI-generated images for slides that need visual content.
Falls back gracefully when the API key is not configured.

Pipeline:
  1. should_use_image(slide) → decides if image is needed
  2. generate_image_prompt(slide) → creates detailed visual prompt
  3. generate_image(prompt) → calls DALL-E API → returns local file path
"""

import logging
import os
import uuid

from config import settings

logger = logging.getLogger(__name__)


async def generate_image_prompt(slide_data: dict) -> str:
    """Convert slide content into a detailed DALL-E image prompt.

    Rules:
      - Must reflect slide semantics (not generic)
      - Include subject, environment, style
      - Professional presentation quality
      - No text in the image
    """
    content = slide_data.get("content", {})
    slide_type = slide_data.get("type", "")
    title = content.get("title", "")

    # Gather context from slide content
    description = (
        content.get("body", "")
        or content.get("description", "")
        or content.get("summary", "")
        or ""
    )

    # Build semantic prompt from slide content
    prompt_parts = [
        f"Professional presentation visual for: {title}.",
    ]

    if description:
        # Extract key concepts from the description
        prompt_parts.append(f"Context: {description[:200]}.")

    # Add slide-type-specific style guidance
    type_styles = {
        "example_slide": "realistic photograph, case study style",
        "example_detail_slide": "detailed diagram or infographic",
        "image_slide": "high-quality stock photography style",
        "product": "modern product showcase, clean background",
        "feature_slide": "technology concept art, modern design",
    }
    style = type_styles.get(slide_type, "modern professional illustration")
    prompt_parts.append(f"Style: {style}.")
    prompt_parts.append(
        "No text, no watermarks, no logos. Clean composition, "
        "16:9 landscape aspect ratio, suitable for presentation slide background."
    )

    return " ".join(prompt_parts)


async def generate_image(prompt: str, output_dir: str | None = None) -> str | None:
    """Generate an image using OpenAI DALL-E API.

    Args:
        prompt: Detailed image description.
        output_dir: Directory to save the image. Defaults to settings.output_dir.

    Returns:
        Local file path of the generated image, or None if generation fails.
    """
    if not settings.openai_api_key:
        logger.warning(
            "[ai_image] OpenAI API key not configured — cannot generate images. "
            "Set OPENAI_API_KEY in .env"
        )
        return None

    save_dir = output_dir or settings.output_dir
    os.makedirs(save_dir, exist_ok=True)

    try:
        from openai import AsyncOpenAI  # type: ignore
        client = AsyncOpenAI(api_key=settings.openai_api_key)

        response = await client.images.generate(
            model="dall-e-3",
            prompt=prompt,
            size="1792x1024",  # Closest to 16:9 landscape
            quality="standard",
            n=1,
        )

        image_url = response.data[0].url
        if not image_url:
            logger.error("[ai_image] DALL-E returned no URL")
            return None

        # Download the generated image
        import httpx
        async with httpx.AsyncClient(timeout=30) as http_client:
            r = await http_client.get(image_url)
            r.raise_for_status()

            file_name = f"ai_{uuid.uuid4().hex}.png"
            file_path = os.path.join(save_dir, file_name)
            with open(file_path, "wb") as f:
                f.write(r.content)

        logger.info("[ai_image] Generated image: %s", file_path)
        return file_path

    except ImportError:
        logger.warning("[ai_image] openai package not installed — cannot generate images")
        return None
    except Exception as exc:
        logger.warning("[ai_image] Image generation failed: %s", exc)
        return None


async def generate_image_for_slide(slide_data: dict, output_dir: str | None = None) -> str | None:
    """Full pipeline: decide → prompt → generate → return path.

    Args:
        slide_data: Structured slide dict with {type, content}.
        output_dir: Directory to save generated images.

    Returns:
        Local file path of the generated image, or None if not applicable.
    """
    from pipeline.visual_design_engine import should_use_image

    if not should_use_image(slide_data):
        return None

    prompt = await generate_image_prompt(slide_data)
    path = await generate_image(prompt, output_dir)
    return path
