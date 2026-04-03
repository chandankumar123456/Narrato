"""Phase 1: User Input Schema Parser.

Parses user input into a rigid specification schema that drives strict-mode
pipeline stages.  Returns ``None`` for generic/unstructured prompts so the
default pipeline handles them.
"""

from __future__ import annotations

import logging
from typing import Optional

from pydantic import BaseModel, Field
from services.llm_client import call_llm_json

logger = logging.getLogger(__name__)


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

    system = (
        "You are a specification parser.  Analyse the user's presentation "
        "prompt and extract ONLY what they explicitly state.\n\n"
        "Return a JSON object with these fields:\n"
        "- topic (string): the core subject\n"
        "- examples_required (int): exact count of examples requested (0 if none)\n"
        "- fields_required (list[str]): per-example fields the user specified "
        "(e.g. [\"origin\", \"history\"]).  ONLY include fields the user "
        "explicitly mentioned.  Do NOT infer, expand, or add extra fields.\n"
        "- forbidden_content (list[str]): topics that would be off-topic or "
        "unrelated to the user's request (e.g. market analysis, investment "
        "content, supply chain, generic explanations).  Derive these from the "
        "domain context.\n"
        "- is_structured_request (bool): true if the prompt contains specific "
        "structural requirements (exact example count AND specific fields), "
        "false for generic prompts like 'make me a presentation about X'."
    )

    user = f"User prompt: {prompt}"

    try:
        result = await call_llm_json(system, user)
        schema = UserSchema(**result)
    except Exception:
        logger.warning("Failed to parse user schema, falling back to default pipeline")
        return None

    if not schema.is_structured_request:
        return None

    if schema.examples_required <= 0 or not schema.fields_required:
        return None

    return schema
