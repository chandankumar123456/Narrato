"""Phase 4: Strict Content Structurer.

Generates slide content constrained to ONLY the user-specified fields.
No generic expansion, no forbidden content.
"""

from __future__ import annotations

import logging

from models.presentation_state import PresentationState
from services.llm_client import call_llm_json

logger = logging.getLogger(__name__)


async def generate_strict_content(state: PresentationState) -> PresentationState:
    """Generate structured content for each slide using strict schema rules.

    Every LLM call explicitly lists required fields, word-count limits, and
    forbidden content so the model cannot deviate from the user specification.
    """

    schema = state.user_schema
    if not schema:
        raise ValueError("generate_strict_content requires user_schema on state")

    fields_required: list[str] = schema.get("fields_required", [])
    forbidden: list[str] = schema.get("forbidden_content", [])
    topic: str = schema.get("topic", state.topic)
    n_examples: int = schema.get("examples_required", 0)

    forbidden_clause = ""
    if forbidden:
        forbidden_clause = (
            "\n\nFORBIDDEN — you MUST NOT include ANY of the following topics or "
            "references: " + ", ".join(forbidden) + "."
        )

    structured: list[dict] = []
    example_idx = 0

    for slide in state.slide_plan:
        slide_type = slide["type"]
        content: dict

        if slide_type == "title_slide":
            content = await _generate_title(topic, state.tone, forbidden_clause)

        elif slide_type == "feature_slide" and slide["purpose"] == "Definition of topic":
            content = await _generate_definition(topic, state.tone, forbidden_clause)

        elif slide_type == "example_detail_slide":
            example_idx += 1
            content = await _generate_example(
                topic, example_idx, n_examples, fields_required,
                state.tone, forbidden_clause,
            )

        elif slide_type == "conclusion_slide":
            content = await _generate_summary(
                topic, n_examples, fields_required,
                state.tone, forbidden_clause,
            )

        else:
            else:
            # Fallback for any unexpected type
            logger.warning("Strict mode: unexpected slide type '%s'", slide_type)
            content = {"title": slide.get("purpose", topic), "body": "Content pending"}

        structured.append({
            "slide_id": slide["slide_id"],
            "type": slide_type,
            "content": content,
        })

    return state.model_copy(update={"structured_slides": structured})


# ── per-slide generators ──────────────────────────────────────────────

async def _generate_title(topic: str, tone: str, forbidden_clause: str) -> dict:
    system = (
        "You generate a presentation title slide. Return ONLY valid JSON with "
        "keys: title, subtitle.  Each value MUST be 10 words maximum.  "
        "Be factual and direct." + forbidden_clause
    )
    user = f"Topic: {topic}\nTone: {tone}\nReturn JSON: {{\"title\": \"...\", \"subtitle\": \"...\"}}"
    try:
        return await call_llm_json(system, user)
    except Exception:
        return {"title": topic, "subtitle": f"An overview of {topic}"}


async def _generate_definition(topic: str, tone: str, forbidden_clause: str) -> dict:
    system = (
        "You generate a short definition slide. Return ONLY valid JSON with "
        "keys: title, features.  'features' is a list with exactly 1 item "
        "having keys: icon, label, description.  "
        "The description MUST be 12 words maximum.  Be factual." + forbidden_clause
    )
    user = (
        f"Topic: {topic}\nTone: {tone}\n"
        f"Return JSON: {{\"title\": \"What is {topic}?\", \"features\": "
        f"[{{\"icon\": \"📖\", \"label\": \"Definition\", \"description\": \"...\"}}]}}"
    )
    try:
        return await call_llm_json(system, user)
    except Exception:
        return {
            "title": f"What is {topic}?",
            "features": [{"icon": "📖", "label": "Definition",
                          "description": f"A concise definition of {topic}."}],
        }


async def _generate_example(
    topic: str,
    example_num: int,
    total_examples: int,
    fields: list[str],
    tone: str,
    forbidden_clause: str,
) -> dict:
    """Generate content for a single example slide.

    The JSON schema is built dynamically from *fields* so the LLM can only
    produce the exact fields the user requested.
    """

    fields_schema = ", ".join(f'"{f}": "..."' for f in fields)
    json_template = f'{{"name": "...", {fields_schema}}}'

    system = (
        f"You generate content for example {example_num} of {total_examples} "
        f"about {topic}.  Return ONLY valid JSON matching the schema below.\n"
        f"Schema: {json_template}\n\n"
        f"RULES:\n"
        f"- 'name' is the name of this specific example of {topic}\n"
        f"- Each field value MUST be 12 words maximum\n"
        f"- Be short, factual, and direct — no paragraphs\n"
        f"- Return ONLY the fields specified. No additional fields."
        + forbidden_clause
    )
    user = (
        f"Topic: {topic}\nTone: {tone}\n"
        f"Generate example {example_num} of {total_examples}.\n"
        f"Required fields: name, {', '.join(fields)}\n"
        f"Return JSON matching: {json_template}"
    )
    try:
        content = await call_llm_json(system, user)
        # Ensure 'name' key exists
        if "name" not in content:
            content["name"] = f"Example {example_num}"
        return content
    except Exception:
        fallback = {"name": f"Example {example_num}"}
        for f in fields:
            fallback[f] = f"{f.capitalize()} information unavailable"
        return fallback


async def _generate_summary(
    topic: str,
    n_examples: int,
    fields: list[str],
    tone: str,
    forbidden_clause: str,
) -> dict:
    system = (
        f"You generate a summary slide for a presentation about {topic}.  "
        f"The presentation covered {n_examples} examples, each with fields: "
        f"{', '.join(fields)}.\n"
        f"Return ONLY valid JSON with keys: title, bullets, key_takeaway.\n"
        f"- 'bullets' is a list of {n_examples} short bullet points "
        f"(one per example, max 12 words each)\n"
        f"- 'key_takeaway' is a single sentence, max 12 words\n"
        f"- Be factual and direct."
        + forbidden_clause
    )
    user = f"Topic: {topic}\nTone: {tone}\nReturn the summary JSON."
    try:
        return await call_llm_json(system, user)
    except Exception:
        return {
            "title": f"Summary — {topic}",
            "bullets": [f"Example {i + 1}" for i in range(n_examples)],
            "key_takeaway": f"Key insights about {topic}.",
        }
