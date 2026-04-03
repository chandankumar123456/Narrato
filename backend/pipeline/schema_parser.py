"""Phase 1: User Input Schema Parser.

Parses user input into a rigid specification schema that drives strict-mode
pipeline stages.  Returns ``None`` for generic/unstructured prompts so the
default pipeline handles them.

Uses a dedicated SYSTEM PROMPT for high-precision extraction — the LLM acts
as a controlled specification parser, NOT a creative writer.
"""

from __future__ import annotations

import logging
from typing import Optional

from pydantic import BaseModel, Field
from services.llm_client import call_llm_json

logger = logging.getLogger(__name__)

# ── Dedicated system prompt for the Schema Parser LLM role ────────────
SCHEMA_PARSER_SYSTEM_PROMPT = (
    "ROLE: You are a STRICT SPECIFICATION PARSER. You extract structured "
    "requirements from a user prompt. You are NOT a writer.\n\n"
    "RULES:\n"
    "1. Extract ONLY what the user explicitly states.\n"
    "2. Do NOT infer, expand, guess, or add fields the user did not request.\n"
    "3. Do NOT add explanatory text.\n"
    "4. Return ONLY valid JSON — no markdown, no commentary.\n\n"
    "OUTPUT SCHEMA (all fields required):\n"
    "{\n"
    '  "topic": "<core subject as stated by user>",\n'
    '  "examples_required": <exact integer count of examples requested, 0 if none>,\n'
    '  "fields_required": ["<field1>", "<field2>"],  // ONLY user-specified per-example fields\n'
    '  "forbidden_content": ["<topic1>", "<topic2>"],  // off-topic categories derived from domain\n'
    '  "is_structured_request": true/false  // true ONLY if user specifies exact count AND specific fields\n'
    "}\n\n"
    "FORBIDDEN in output: extra keys, explanations, defaults, invented fields."
)


class UserSchema(BaseModel):
    """Immutable specification derived from the user prompt."""

    topic: str
    examples_required: int = 0
    fields_required: list[str] = Field(default_factory=list)
    forbidden_content: list[str] = Field(default_factory=list)
    is_structured_request: bool = False


async def parse_user_schema(prompt: str) -> Optional[UserSchema]:
    """Extract a strict schema from *prompt*.

    Returns ``None`` when the prompt is generic (no specific field/count
    requirements) so the default pipeline can handle it.
    """

    user = f"User prompt: {prompt}"

    try:
        result = await call_llm_json(SCHEMA_PARSER_SYSTEM_PROMPT, user)
        schema = UserSchema(**result)
    except Exception:
        logger.warning("Failed to parse user schema, falling back to default pipeline")
        return None

    if not schema.is_structured_request:
        return None

    if schema.examples_required <= 0 or not schema.fields_required:
        return None

    return schema
