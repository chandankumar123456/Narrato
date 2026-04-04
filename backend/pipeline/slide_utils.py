"""Shared utilities for slide content analysis.

Common helpers used across slide_evaluator.py and deck_consistency_optimizer.py.
"""

from __future__ import annotations

from models.presentation_state import PresentationState


def flatten_content(content: dict) -> str:
    """Flatten a slide content dict into a human-readable string."""
    parts: list[str] = []
    for key, val in content.items():
        if isinstance(val, str):
            parts.append(f"{key}: {val}")
        elif isinstance(val, list):
            for item in val:
                if isinstance(item, str):
                    parts.append(f"- {item}")
                elif isinstance(item, dict):
                    parts.append(
                        "- " + ", ".join(f"{k}: {v}" for k, v in item.items())
                    )
        elif isinstance(val, dict):
            parts.append(
                f"{key}: " + ", ".join(f"{k}: {v}" for k, v in val.items())
            )
    return "\n".join(parts)


def extract_bullets(content: dict) -> list[str]:
    """Extract descriptive text items from slide content for quality checks.

    Only extracts descriptions and body-like text — NOT short label/heading fields
    which are expected to be concise.
    """
    bullets: list[str] = []
    for key, val in content.items():
        if key in ("title", "section_title", "presenter", "contact", "attribution",
                    "icon", "stat", "stat_label", "source", "year", "cta_text",
                    "label", "left_label", "right_label"):
            continue  # Skip non-bullet / heading fields
        if isinstance(val, str) and key in ("body", "subtitle", "description",
                                             "tagline", "context", "result",
                                             "takeaway", "key_takeaway", "message",
                                             "quote", "caption"):
            if val.strip():
                bullets.append(val)
        elif isinstance(val, list):
            for item in val:
                if isinstance(item, str):
                    if item.strip():
                        bullets.append(item)
                elif isinstance(item, dict):
                    # Only extract description fields from list items —
                    # labels are short headings, not descriptive bullets
                    desc = item.get("description", "")
                    if desc and desc.strip():
                        bullets.append(desc)
    return bullets


def find_plan_entry(state: PresentationState, slide_id: int) -> dict:
    """Find the slide plan entry matching a slide_id."""
    if state.slide_plan:
        for entry in state.slide_plan:
            if entry.get("slide_id") == slide_id:
                return entry
    return {"section": "unknown", "purpose": "unknown", "type": "unknown", "slide_id": slide_id}
