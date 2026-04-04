"""
Stage 3: Rendering Engine

Prepares browser-based rendering instructions and executes Playwright-based
screenshot capture when Playwright is available.

Renders each HTML slide at 1920×1080 to:
  - PNG images
  - PDF (combined slides)

When Playwright is not installed, produces render instructions only
(HTML can be rendered externally).
"""

import asyncio
import logging
import os
import uuid
from typing import Optional

logger = logging.getLogger(__name__)

VIEWPORT_WIDTH = 1920
VIEWPORT_HEIGHT = 1080


def build_render_instructions(slide_count: int) -> dict:
    """Return deterministic render instructions for the deck."""
    return {
        "viewport": f"{VIEWPORT_WIDTH}x{VIEWPORT_HEIGHT}",
        "slide_count": slide_count,
        "export": ["png", "pdf", "ppt"],
        "resolution": f"{VIEWPORT_WIDTH}x{VIEWPORT_HEIGHT}",
        "quality": {
            "no_overflow": True,
            "no_scrolling": True,
            "fixed_viewport": True,
            "stable_layout": True,
            "font_loaded": True,
        },
    }


async def render_slides_to_images(
    html_slides: list[str],
    output_dir: str,
) -> list[str]:
    """
    Render HTML slides to PNG images using Playwright.

    Returns list of PNG file paths. If Playwright is not available,
    returns an empty list (caller should fall back to HTML-only export).
    """
    try:
        from playwright.async_api import async_playwright  # type: ignore
    except ImportError:
        logger.warning(
            "[rendering_engine] Playwright not installed — "
            "skipping browser-based rendering. "
            "Install with: pip install playwright && playwright install chromium"
        )
        return []

    os.makedirs(output_dir, exist_ok=True)
    image_paths: list[str] = []

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                viewport={"width": VIEWPORT_WIDTH, "height": VIEWPORT_HEIGHT},
                device_scale_factor=1,
            )

            for idx, slide_html in enumerate(html_slides):
                page = await context.new_page()
                await page.set_content(slide_html, wait_until="networkidle")
                # Wait for Tailwind CDN to process
                await page.wait_for_timeout(500)

                png_path = os.path.join(output_dir, f"slide_{idx + 1}.png")
                await page.screenshot(path=png_path, full_page=False)
                image_paths.append(png_path)
                await page.close()

            await browser.close()

        logger.info(
            "[rendering_engine] Rendered %d slides to PNG", len(image_paths)
        )
    except Exception:
        logger.exception("[rendering_engine] Browser rendering failed")

    return image_paths


async def render_slides_to_pdf(
    html_slides: list[str],
    output_dir: str,
) -> Optional[str]:
    """
    Render all HTML slides into a single PDF.

    Returns the PDF path or None if Playwright is unavailable.
    """
    try:
        from playwright.async_api import async_playwright  # type: ignore
    except ImportError:
        logger.warning("[rendering_engine] Playwright not installed — skipping PDF")
        return None

    os.makedirs(output_dir, exist_ok=True)

    # Build a combined HTML document with page breaks between slides
    combined_html = _build_combined_html(html_slides)
    pdf_path = os.path.join(output_dir, "presentation.pdf")

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.set_content(combined_html, wait_until="networkidle")
            await page.wait_for_timeout(500)
            await page.pdf(
                path=pdf_path,
                width=f"{VIEWPORT_WIDTH}px",
                height=f"{VIEWPORT_HEIGHT}px",
                print_background=True,
                prefer_css_page_size=True,
            )
            await browser.close()

        logger.info("[rendering_engine] Generated PDF: %s", pdf_path)
        return pdf_path
    except Exception:
        logger.exception("[rendering_engine] PDF generation failed")
        return None


def _build_combined_html(html_slides: list[str]) -> str:
    """Combine individual slide HTML into one document with page breaks."""
    # Extract the inner body content from each slide
    import re
    bodies = []
    for slide_html in html_slides:
        # Extract the <div class="slide ..."> element
        match = re.search(
            r'(<div class="slide .*?</div>)\s*</body>',
            slide_html,
            re.DOTALL,
        )
        if match:
            bodies.append(match.group(1))
        else:
            bodies.append('<div class="slide">Slide</div>')

    pages = ""
    for i, body in enumerate(bodies):
        page_break = 'style="page-break-after: always;"' if i < len(bodies) - 1 else ""
        pages += f'<div {page_break}>\n{body}\n</div>\n'

    return f"""\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<script src="https://cdn.tailwindcss.com"></script>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
  body {{ margin:0; padding:0; font-family:'Inter',sans-serif; }}
  .slide {{ width:{VIEWPORT_WIDTH}px; height:{VIEWPORT_HEIGHT}px; overflow:hidden; }}
  @media print {{
    .slide {{ page-break-after: always; }}
  }}
</style>
</head>
<body>
{pages}
</body>
</html>"""


async def run_rendering_engine(
    html_slides: list[str],
    output_dir: str,
) -> dict:
    """
    Stage 3 entry point.

    Produces render instructions and optionally renders slides to
    PNG images and PDF using Playwright.

    Returns:
        {
            "render_instructions": {...},
            "image_paths": [...],
            "pdf_path": str | None,
        }
    """
    render_instructions = build_render_instructions(len(html_slides))

    # Attempt browser rendering (graceful degradation if Playwright missing)
    image_paths = await render_slides_to_images(html_slides, output_dir)
    pdf_path = await render_slides_to_pdf(html_slides, output_dir)

    return {
        "render_instructions": render_instructions,
        "image_paths": image_paths,
        "pdf_path": pdf_path,
    }
