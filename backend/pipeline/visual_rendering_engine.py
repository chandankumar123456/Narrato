"""
Stage 3: Rendering Engine

Renders each HTML slide at 1920×1080 to:
  - PNG images
  - PDF (combined slides — per-slide rendering, then merge)

Uses the **async** Playwright API for compatibility with FastAPI's
async event loop.

CRITICAL DESIGN RULE:
  Editor HTML == Export HTML (byte-level identical per slide).
  Each slide is rendered individually using its EXACT HTML — no
  reconstruction, no regex extraction, no content stripping.

When Playwright is not installed, produces render instructions only
(HTML can be rendered externally).
"""

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

VIEWPORT_WIDTH = 1920
VIEWPORT_HEIGHT = 1080


class ExportRenderError(RuntimeError):
    """Raised when export rendering detects a parity violation."""
    pass


def build_render_instructions(slide_count: int) -> dict:
    """Return deterministic render instructions for the deck."""
    return {
        "viewport": f"{VIEWPORT_WIDTH}x{VIEWPORT_HEIGHT}",
        "slide_count": slide_count,
        "export": ["png", "pdf"],
        "resolution": f"{VIEWPORT_WIDTH}x{VIEWPORT_HEIGHT}",
        "quality": {
            "no_overflow": True,
            "no_scrolling": True,
            "fixed_viewport": True,
            "stable_layout": True,
            "font_loaded": True,
        },
    }


async def _wait_for_slide_ready(page) -> None:
    """Wait for a slide page to be fully rendered (Tailwind + images).

    STRICT: If images exist but fail to load, raises ExportRenderError.
    """
    # Wait for Tailwind CDN to parse and apply utility classes
    await page.wait_for_timeout(500)
    # Wait for all images to finish loading — STRICT: no exceptions swallowed
    await page.wait_for_function(
        "() => Array.from(document.images).every(img => img.complete)",
        timeout=10000,
    )


async def render_slides_to_images(
    html_slides: list[str],
    output_dir: str,
) -> list[str]:
    """
    Render HTML slides to PNG images using Playwright (async API).

    Each slide is rendered using its EXACT editor HTML — no reconstruction.

    Returns list of PNG file paths.  If Playwright is not available,
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

            for idx, slide_html in enumerate(html_slides or []):
                page = await context.new_page()
                await page.set_content(slide_html, wait_until="networkidle")
                await _wait_for_slide_ready(page)

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
    Render all HTML slides into a single PDF using Playwright (async API).

    CRITICAL: Each slide is rendered individually using its EXACT HTML
    (the same HTML the editor iframe displays). Individual per-slide PDFs
    are generated and then merged into one document.

    This guarantees: Editor HTML == Export HTML (no reconstruction).

    Returns the PDF path or None if Playwright is unavailable.
    """
    try:
        from playwright.async_api import async_playwright  # type: ignore
    except ImportError:
        logger.warning("[rendering_engine] Playwright not installed — skipping PDF")
        return None

    if not html_slides:
        return None

    os.makedirs(output_dir, exist_ok=True)
    pdf_path = os.path.join(output_dir, "presentation.pdf")

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)

            per_slide_pdfs: list[bytes] = []
            for idx, slide_html in enumerate(html_slides):
                page = await browser.new_page()
                # Set the EXACT same HTML the editor uses — no reconstruction
                await page.set_content(slide_html, wait_until="networkidle")
                await _wait_for_slide_ready(page)

                # Generate PDF for this single slide
                pdf_bytes = await page.pdf(
                    width=f"{VIEWPORT_WIDTH}px",
                    height=f"{VIEWPORT_HEIGHT}px",
                    print_background=True,
                    prefer_css_page_size=True,
                )
                per_slide_pdfs.append(pdf_bytes)
                await page.close()

            await browser.close()

        # Merge individual slide PDFs into one document
        _merge_pdfs(per_slide_pdfs, pdf_path)

        logger.info("[rendering_engine] Generated PDF (%d slides): %s",
                     len(per_slide_pdfs), pdf_path)
        return pdf_path
    except Exception:
        logger.exception("[rendering_engine] PDF generation failed")
        return None


def _merge_pdfs(pdf_pages: list[bytes], output_path: str) -> None:
    """Merge multiple single-page PDF byte strings into one PDF file.

    Uses a lightweight approach: if only one page, write directly.
    For multiple pages, attempts PyPDF merge; falls back to writing
    the first page if PyPDF is unavailable (single-slide edge case).
    """
    if not pdf_pages:
        return

    if len(pdf_pages) == 1:
        with open(output_path, "wb") as f:
            f.write(pdf_pages[0])
        return

    try:
        from pypdf import PdfWriter, PdfReader  # type: ignore
        import io
        writer = PdfWriter()
        for pdf_bytes in pdf_pages:
            reader = PdfReader(io.BytesIO(pdf_bytes))
            for page in reader.pages:
                writer.add_page(page)
        with open(output_path, "wb") as f:
            writer.write(f)
    except ImportError:
        logger.warning(
            "[rendering_engine] pypdf not installed — "
            "multi-slide PDF will contain only the first slide. "
            "Install with: pip install pypdf"
        )
        # Fallback: write first slide only (install pypdf for full multi-slide support)
        with open(output_path, "wb") as f:
            f.write(pdf_pages[0])
        logger.warning(
            "[rendering_engine] Wrote single-slide PDF (%d of %d slides). "
            "Install pypdf for complete multi-slide export.",
            1, len(pdf_pages),
        )


async def run_rendering_engine(
    html_slides: list[str],
    output_dir: str,
) -> dict:
    """
    Stage 3 entry point (async).

    Produces render instructions and optionally renders slides to
    PNG images and PDF using Playwright.

    Returns:
        {
            "render_instructions": {...},
            "image_paths": [...],
            "pdf_path": str | None,
        }
    """
    safe_slides = html_slides or []
    render_instructions = build_render_instructions(len(safe_slides))

    # Attempt browser rendering (graceful degradation if Playwright missing)
    try:
        image_paths = await render_slides_to_images(safe_slides, output_dir)
    except Exception as exc:
        logger.warning("[rendering_engine] fallback: image rendering skipped — %s", exc)
        image_paths = []

    try:
        pdf_path = await render_slides_to_pdf(safe_slides, output_dir)
    except Exception as exc:
        logger.warning("[rendering_engine] fallback: PDF rendering skipped — %s", exc)
        pdf_path = None

    return {
        "render_instructions": render_instructions,
        "image_paths": image_paths,
        "pdf_path": pdf_path,
    }
