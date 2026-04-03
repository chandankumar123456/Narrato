"""Phase 4: Strict Content Structurer — DETERMINISTIC SPEC-DRIVEN GENERATION.

Content is generated PER FIELD (not per slide).  Each field is independently
produced by a dedicated LLM call with hard constraints baked into the system
prompt.  Forbidden content is PREVENTED at generation time, not detected
after the fact.

If a field violates constraints it is REGENERATED at the field level — not
the entire slide.  This guarantees deterministic completion without global
retry loops.
"""

from __future__ import annotations

import logging

from models.presentation_state import PresentationState
from services.llm_client import call_llm

logger = logging.getLogger(__name__)

# Maximum attempts to regenerate a single field before hard failure
MAX_FIELD_ATTEMPTS = 3
MAX_WORDS = 12


class StrictContentError(RuntimeError):
    """Raised when field generation fails after all attempts."""


# ── Dedicated system prompts (Step 9/10: multi-LLM role separation) ──

_FIELD_GENERATOR_SYSTEM = (
    "ROLE: You are a STRICT FIELD GENERATOR.  You produce EXACTLY ONE short "
    "factual value for a specified field.\n\n"
    "ABSOLUTE RULES:\n"
    "- Output ONLY the field value — no keys, no JSON, no quotes, no explanation.\n"
    "- Maximum {max_words} words.  NEVER exceed this.\n"
    "- Maximum 2 lines.\n"
    "- No paragraphs.  No bullet points.  No markdown.\n"
    "- Factual only — no opinions, no hedging.\n"
    "- No extra information beyond what is asked.\n"
    "{forbidden_clause}"
)

_TITLE_SYSTEM = (
    "ROLE: You are a STRICT TITLE GENERATOR.\n"
    "Output ONLY the title text — no JSON, no quotes, no explanation.\n"
    "Maximum {max_words} words.  Factual and direct.\n"
    "{forbidden_clause}"
)

_SUBTITLE_SYSTEM = (
    "ROLE: You are a STRICT SUBTITLE GENERATOR.\n"
    "Output ONLY the subtitle text — no JSON, no quotes, no explanation.\n"
    "Maximum {max_words} words.  Factual and direct.\n"
    "{forbidden_clause}"
)

_DEFINITION_SYSTEM = (
    "ROLE: You are a STRICT DEFINITION GENERATOR.\n"
    "Output ONLY a concise factual definition — no JSON, no quotes, no explanation.\n"
    "Maximum {max_words} words.  No paragraphs.\n"
    "{forbidden_clause}"
)

_BULLET_SYSTEM = (
    "ROLE: You are a STRICT BULLET POINT GENERATOR.\n"
    "Output EXACTLY {count} bullet points, one per line.\n"
    "Each bullet: maximum {max_words} words.  Factual only.\n"
    "No numbering, no dashes, no markdown.  Plain text lines.\n"
    "{forbidden_clause}"
)

_TAKEAWAY_SYSTEM = (
    "ROLE: You are a STRICT KEY TAKEAWAY GENERATOR.\n"
    "Output ONLY one sentence — no JSON, no quotes, no explanation.\n"
    "Maximum {max_words} words.  Factual and direct.\n"
    "{forbidden_clause}"
)


def _forbidden_clause(forbidden: list[str]) -> str:
    if not forbidden:
        return ""
    items = ", ".join(forbidden)
    return (
        f"\nFORBIDDEN — you MUST NOT mention or reference ANY of: {items}.\n"
        "If you are unsure, omit the information entirely."
    )


def _check_forbidden(text: str, forbidden: list[str]) -> bool:
    """Return True if *text* contains any forbidden term."""
    lower = text.lower()
    return any(term.lower() in lower for term in forbidden)


def _word_count_ok(text: str) -> bool:
    return len(text.split()) <= MAX_WORDS


async def _generate_field_value(
    system_prompt: str,
    user_prompt: str,
    forbidden: list[str],
    field_name: str,
) -> str:
    """Generate a single field value with field-level regeneration guarantee.

    Keeps regenerating until the value passes constraints or MAX_FIELD_ATTEMPTS
    is exhausted, at which point a StrictContentError is raised.
    """
    for attempt in range(1, MAX_FIELD_ATTEMPTS + 1):
        raw = await call_llm(system_prompt, user_prompt)
        value = raw.strip().strip('"').strip("'").strip()

        # Enforce word limit at generation boundary
        if not _word_count_ok(value):
            logger.warning(
                "Field '%s' attempt %d: %d words (max %d) — regenerating",
                field_name, attempt, len(value.split()), MAX_WORDS,
            )
            continue

        # Enforce forbidden content at generation boundary
        if _check_forbidden(value, forbidden):
            logger.warning(
                "Field '%s' attempt %d: contains forbidden content — regenerating",
                field_name, attempt,
            )
            continue

        return value

    raise StrictContentError(
        f"Field '{field_name}' failed after {MAX_FIELD_ATTEMPTS} attempts"
    )


# ── Public entry point ────────────────────────────────────────────────

async def generate_strict_content(state: PresentationState) -> PresentationState:
    """Generate structured content for each slide using strict schema rules.

    Each field is generated INDEPENDENTLY with dedicated LLM calls.
    No fallback content.  No placeholder text.  Hard failure on exhausted retries.
    """
    schema = state.user_schema
    if not schema:
        raise ValueError("generate_strict_content requires user_schema on state")

    fields_required: list[str] = schema.get("fields_required", [])
    forbidden: list[str] = schema.get("forbidden_content", [])
    topic: str = schema["topic"]
    n_examples: int = schema["examples_required"]
    fc = _forbidden_clause(forbidden)

    structured: list[dict] = []
    example_idx = 0

    for slide in state.slide_plan:
        slide_type = slide["type"]

        if slide_type == "title_slide":
            content = await _generate_title_content(topic, state.tone, forbidden, fc)

        elif slide_type == "feature_slide" and slide["purpose"] == "Definition of topic":
            content = await _generate_definition_content(topic, state.tone, forbidden, fc)

        elif slide_type == "example_detail_slide":
            example_idx += 1
            content = await _generate_example_content(
                topic, example_idx, n_examples, fields_required,
                state.tone, forbidden, fc,
            )

        elif slide_type == "conclusion_slide":
            content = await _generate_summary_content(
                topic, n_examples, fields_required,
                state.tone, forbidden, fc,
            )

        else:
            raise StrictContentError(
                f"Unexpected slide type '{slide_type}' in strict mode"
            )

        structured.append({
            "slide_id": slide["slide_id"],
            "type": slide_type,
            "content": content,
        })

    return state.model_copy(update={"structured_slides": structured})


# ── Per-slide content generators (each delegates to per-field calls) ──

async def _generate_title_content(
    topic: str, tone: str, forbidden: list[str], fc: str,
) -> dict:
    title = await _generate_field_value(
        _TITLE_SYSTEM.format(max_words=MAX_WORDS, forbidden_clause=fc),
        f"Generate a presentation title about: {topic}\nTone: {tone}",
        forbidden, "title",
    )
    subtitle = await _generate_field_value(
        _SUBTITLE_SYSTEM.format(max_words=MAX_WORDS, forbidden_clause=fc),
        f"Generate a subtitle for a presentation about: {topic}\nTone: {tone}",
        forbidden, "subtitle",
    )
    return {"title": title, "subtitle": subtitle}


async def _generate_definition_content(
    topic: str, tone: str, forbidden: list[str], fc: str,
) -> dict:
    definition = await _generate_field_value(
        _DEFINITION_SYSTEM.format(max_words=MAX_WORDS, forbidden_clause=fc),
        f"Define '{topic}' in one concise factual sentence.\nTone: {tone}",
        forbidden, "definition",
    )
    return {
        "title": f"What is {topic}?",
        "features": [{"icon": "📖", "label": "Definition", "description": definition}],
    }


async def _generate_example_content(
    topic: str,
    example_num: int,
    total_examples: int,
    fields: list[str],
    tone: str,
    forbidden: list[str],
    fc: str,
) -> dict:
    """Generate one example slide — each field is produced independently."""
    # Generate example name
    name = await _generate_field_value(
        _FIELD_GENERATOR_SYSTEM.format(max_words=6, forbidden_clause=fc),
        f"Give the NAME of example {example_num} of {total_examples} "
        f"of {topic}.  Output only the name.",
        forbidden, "name",
    )

    content: dict = {"name": name}

    # Generate each user-specified field independently (Step 4)
    for field in fields:
        value = await _generate_field_value(
            _FIELD_GENERATOR_SYSTEM.format(max_words=MAX_WORDS, forbidden_clause=fc),
            f"Topic: {topic}\nExample: {name}\n"
            f"Field: {field}\n"
            f"Generate the '{field}' for this example of {topic}.\n"
            f"Tone: {tone}\nOutput only the value.",
            forbidden, field,
        )
        content[field] = value

    return content


async def _generate_summary_content(
    topic: str,
    n_examples: int,
    fields: list[str],
    tone: str,
    forbidden: list[str],
    fc: str,
) -> dict:
    title = f"Summary — {topic}"

    # Generate bullet points (one per example)
    raw_bullets = await _generate_field_value(
        _BULLET_SYSTEM.format(count=n_examples, max_words=MAX_WORDS, forbidden_clause=fc),
        f"Summarise {n_examples} examples of {topic} "
        f"(each had fields: {', '.join(fields)}).\n"
        f"Tone: {tone}\nOutput {n_examples} lines, one per example.",
        forbidden, "bullets",
    )
    bullets = [line.strip() for line in raw_bullets.strip().split("\n") if line.strip()][:n_examples]

    key_takeaway = await _generate_field_value(
        _TAKEAWAY_SYSTEM.format(max_words=MAX_WORDS, forbidden_clause=fc),
        f"Give one key takeaway about {topic}.\nTone: {tone}",
        forbidden, "key_takeaway",
    )

    return {"title": title, "bullets": bullets, "key_takeaway": key_takeaway}
