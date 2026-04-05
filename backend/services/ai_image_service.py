"""AI Image Generation Service — generates images using OpenAI API.

Provides real AI-generated images for slides that need visual content.
STRICT: Raises on failure — no fallbacks, no placeholders, no stock images.

Pipeline:
  1. should_use_image(slide) → decides if image is needed
  2. generate_image_prompt(slide) → creates detailed visual prompt
  3. generate_image(prompt) → calls OpenAI Images API → returns local file path

HARD RULE: If image generation fails → pipeline MUST fail.
"""

import logging
import os
import uuid
import base64

from config import settings

logger = logging.getLogger(__name__)


class AIImageError(RuntimeError):
    """Raised when AI image generation fails."""
    pass


async def generate_image_prompt(slide_data: dict) -> str:
    """Convert slide content into a detailed image prompt.

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

    # Determine intent from slide type
    type_intents = {
        "problem_slide": "problem visualization, challenge",
        "solution_slide": "solution, resolution, innovation",
        "example_slide": "realistic case study, practical example",
        "example_detail_slide": "detailed diagram or infographic",
        "image_slide": "high-quality professional photography",
        "product": "modern product showcase, clean background",
        "feature_slide": "technology concept, feature highlight",
        "future_slide": "futuristic, forward-looking vision",
    }
    intent = type_intents.get(slide_type, "professional business concept")

    # Build semantic prompt from slide content
    prompt_parts = [
        f"Professional presentation visual for: {title}.",
        f"Intent: {intent}.",
    ]

    if description:
        prompt_parts.append(f"Context: {description[:200]}.")

    # Add style guidance
    prompt_parts.append(
        "Style: modern, professional, clean. "
        "Tone: polished, suitable for business presentation. "
        "No text, no watermarks, no logos. Clean composition, "
        "16:9 landscape aspect ratio, suitable for presentation slide background."
    )

    return " ".join(prompt_parts)


async def generate_image(prompt: str, output_dir: str | None = None) -> str:
    """Generate an image using OpenAI Images API.

    STRICT: Raises AIImageError on any failure — no fallbacks.

    Args:
        prompt: Detailed image description.
        output_dir: Directory to save the image. Defaults to settings.output_dir.

    Returns:
        Local file path of the generated image.

    Raises:
        AIImageError: If API key missing, generation fails, or download fails.
    """
    if not settings.openai_api_key:
        raise AIImageError(
            "OpenAI API key not configured — cannot generate images. "
            "Set OPENAI_API_KEY in .env"
        )

    save_dir = output_dir or settings.output_dir
    os.makedirs(save_dir, exist_ok=True)

    try:
        from openai import AsyncOpenAI  # type: ignore
    except ImportError:
        raise AIImageError(
            "openai package not installed — cannot generate images. "
            "Install with: pip install openai"
        )

    try:
        client = AsyncOpenAI(api_key=settings.openai_api_key)

        response = await client.images.generate(
            model="gpt-image-1",
            prompt=prompt,
            size="1024x1024",
            n=1,
        )

        # gpt-image-1 returns base64-encoded image data by default
        image_data = response.data[0]

        file_name = f"ai_{uuid.uuid4().hex}.png"
        file_path = os.path.join(save_dir, file_name)

        if hasattr(image_data, "b64_json") and image_data.b64_json:
            # Decode base64 image data
            image_bytes = base64.b64decode(image_data.b64_json)
            with open(file_path, "wb") as f:
                f.write(image_bytes)
        elif hasattr(image_data, "url") and image_data.url:
            # Download from URL
            import httpx
            async with httpx.AsyncClient(timeout=30) as http_client:
                r = await http_client.get(image_data.url)
                r.raise_for_status()
                with open(file_path, "wb") as f:
                    f.write(r.content)
        else:
            raise AIImageError("OpenAI returned neither base64 data nor URL")

        logger.info("[ai_image] Generated image: %s", file_path)
        return file_path

    except AIImageError:
        raise
    except Exception as exc:
        raise AIImageError(f"AI image generation failed: {exc}") from exc


async def generate_image_for_slide(slide_data: dict, output_dir: str | None = None) -> str:
    """Full pipeline: decide → prompt → generate → return path.

    STRICT: Raises AIImageError if image is needed but generation fails.

    Args:
        slide_data: Structured slide dict with {type, content}.
        output_dir: Directory to save generated images.

    Returns:
        Local file path of the generated image.

    Raises:
        AIImageError: If image generation fails for a slide that requires it.
    """
    from pipeline.visual_design_engine import should_use_image

    if not should_use_image(slide_data):
        return None

    prompt = await generate_image_prompt(slide_data)
    return await generate_image(prompt, output_dir)
