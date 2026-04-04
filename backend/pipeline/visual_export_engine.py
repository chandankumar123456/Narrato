"""
Stage 4: Export Engine

Export paths:
  - HTML slides (standalone per slide)
  - PNG images (from rendering engine)
  - PDF (combined document)
"""

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)


def save_html_slides(
    html_slides: list[str],
    output_dir: str,
) -> list[str]:
    """Save individual HTML slides to disk."""
    os.makedirs(output_dir, exist_ok=True)
    paths = []
    for idx, slide_html in enumerate(html_slides):
        path = os.path.join(output_dir, f"slide_{idx + 1}.html")
        with open(path, "w", encoding="utf-8") as f:
            f.write(slide_html)
        paths.append(path)
    logger.info("[export_engine] Saved %d HTML slides", len(paths))
    return paths


def run_export_engine(
    html_slides: list[str],
    image_paths: list[str],
    pdf_path: Optional[str],
    output_dir: str,
) -> dict:
    """
    Stage 4 entry point.

    Produces all export artifacts:
      - HTML slide files
      - Image paths (passed through from rendering engine)
      - PDF path (passed through from rendering engine)

    Returns:
        {
            "html_paths": [...],
            "image_paths": [...],
            "pdf_path": str | None,
        }
    """
    # Save HTML slides to disk
    html_paths = save_html_slides(html_slides, output_dir)

    return {
        "html_paths": html_paths,
        "image_paths": image_paths,
        "pdf_path": pdf_path,
    }
