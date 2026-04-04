"""Multi-stage content generator with validation, critic loop, and intent enforcement.

Phases:
  1. Content Generation   – 3-4 mechanism-driven bullets per slide
  2. Self-Validation      – repetition / generic / depth checks
  3. Critic Loop          – investor-mode evaluation (max 3 attempts)
  4. Slide Intent Enforcement – ensure slide matches its declared intent
"""

from __future__ import annotations

import json
import logging
from typing import Optional

from models.presentation_state import PresentationState
from services.llm_client import call_llm_json

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 3

# Maps slide section/purpose keywords to their allowed intent categories
INTENT_MAP = {
    "problem": "problem",
    "solution": "solution",
    "market": "market",
    "product": "product",
    "benefits": "benefits",
    "intro": "intro",
    "conclusion": "conclusion",
}


async def generate_multi_stage_content(
    state: PresentationState,
) -> PresentationState:
    """Generate slide content using the multi-stage pipeline.

    For every slide in *state.slide_plan*, runs:
      Phase 1 – content generation
      Phase 2 – self-validation (repetition, generic, depth)
      Phase 3 – critic loop (investor evaluation)
      Phase 4 – intent enforcement

    If any phase fails, the slide is regenerated (up to MAX_ATTEMPTS).
    """
    if not state.slide_plan:
        return state

    structured: list[dict] = []
    previous_contents: list[dict] = []

    slide_plan_summary = json.dumps(
        [{"slide_id": s["slide_id"], "section": s["section"],
          "purpose": s["purpose"], "type": s["type"]}
         for s in state.slide_plan],
        indent=2,
    )

    for slide in state.slide_plan:
        slide_type = slide["type"]
        slide_section = slide["section"]
        slide_purpose = slide["purpose"]

        best_content: Optional[dict] = None
        last_feedback: Optional[str] = None
        last_output: Optional[dict] = None

        for attempt in range(1, MAX_ATTEMPTS + 1):
            # ── Phase 1: Content Generation ─────────────────────────
            content = await _generate_slide_content(
                state=state,
                slide=slide,
                slide_plan_summary=slide_plan_summary,
                previous_contents=previous_contents,
                previous_output=last_output,
                previous_feedback=last_feedback,
            )

            # ── Phase 2: Self-Validation ────────────────────────────
            validation = await _validate_content(
                content=content,
                slide=slide,
                previous_contents=previous_contents,
                topic=state.topic,
            )
            if not validation["passed"]:
                logger.warning(
                    "[multi-stage] Slide %s failed validation (attempt %d/%d): %s",
                    slide["slide_id"], attempt, MAX_ATTEMPTS,
                    validation["reason"],
                )
                last_output = content
                last_feedback = f"Validation failed: {validation['reason']}"
                if attempt < MAX_ATTEMPTS:
                    continue

            # ── Phase 3: Critic Loop (Investor Mode) ────────────────
            critic = await _critic_evaluate(
                content=content,
                slide=slide,
                topic=state.topic,
            )
            if not critic["accepted"]:
                logger.warning(
                    "[multi-stage] Slide %s rejected by critic (attempt %d/%d): %s",
                    slide["slide_id"], attempt, MAX_ATTEMPTS,
                    critic["reason"],
                )
                last_output = content
                last_feedback = f"Critic rejected: {critic['reason']}"
                if attempt < MAX_ATTEMPTS:
                    continue

            # ── Phase 4: Slide Intent Enforcement ───────────────────
            intent_ok = await _enforce_intent(
                content=content,
                slide=slide,
                topic=state.topic,
            )
            if not intent_ok["compliant"]:
                logger.warning(
                    "[multi-stage] Slide %s intent violation (attempt %d/%d): %s",
                    slide["slide_id"], attempt, MAX_ATTEMPTS,
                    intent_ok["reason"],
                )
                last_output = content
                last_feedback = f"Intent violation: {intent_ok['reason']}"
                if attempt < MAX_ATTEMPTS:
                    continue

            # All phases passed
            best_content = content
            break
        else:
            # Exhausted all attempts – use last generated content
            logger.warning(
                "[multi-stage] Slide %s: using best-effort content after %d attempts",
                slide["slide_id"], MAX_ATTEMPTS,
            )
            best_content = content  # type: ignore[assignment]

        slide_entry = {
            "slide_id": slide["slide_id"],
            "type": slide_type,
            "content": best_content,
        }
        structured.append(slide_entry)
        previous_contents.append({
            "slide_id": slide["slide_id"],
            "section": slide_section,
            "purpose": slide_purpose,
            "content": best_content,
        })

    return state.model_copy(update={"structured_slides": structured})


# ═══════════════════════════════════════════════════════════════════════
# Phase 1 – Content Generation
# ═══════════════════════════════════════════════════════════════════════

async def _generate_slide_content(
    state: PresentationState,
    slide: dict,
    slide_plan_summary: str,
    previous_contents: list[dict],
    previous_output: dict | None = None,
    previous_feedback: str | None = None,
) -> dict:
    """Generate mechanism-driven content for a single slide.

    If previous_output and previous_feedback are provided (retry scenario),
    they are included in the prompt so the LLM can improve upon the previous attempt.
    """
    previous_summary = ""
    if previous_contents:
        previous_summary = json.dumps(
            [{"slide_id": p["slide_id"], "section": p["section"],
              "content": p["content"]}
             for p in previous_contents],
            indent=2,
        )

    slide_type = slide["type"]
    section = slide["section"]
    purpose = slide["purpose"]
    key_message = ""
    if state.story:
        key_message = state.story.get("key_message", "")

    system_prompt = f"""You are a world-class presentation content architect.
You generate highly specific, mechanism-driven slide content.

STRICT RULES:
1. Each bullet MUST include a concrete mechanism (how it works) OR a specific structural detail.
2. FORBIDDEN: vague phrases like "leveraging AI", "innovative solution", "cutting-edge technology",
   "game-changing", "next-generation", "state-of-the-art", "world-class", "best-in-class".
3. FORBIDDEN: generic startup language applicable to any company in any industry.
4. Every bullet must answer: "What exactly happens?" and "How does it happen?"
5. Content must introduce NEW information not present in previous slides.
6. Content must be specific to the topic "{state.topic}" — not reusable for other topics.

Return ONLY valid JSON. No markdown, no backticks, no preamble."""

    # Build retry context if this is a retry attempt
    retry_context = ""
    if previous_output and previous_feedback:
        retry_context = f"""

PREVIOUS ATTEMPT (rejected — you MUST fix the issues below):
{json.dumps(previous_output, indent=2)}

FEEDBACK ON PREVIOUS ATTEMPT:
{previous_feedback}

Generate IMPROVED content that addresses ALL feedback. Do NOT repeat the same output."""

    user_prompt = f"""Topic: {state.topic}
Presentation type: {state.presentation_type}
Audience: {state.audience or "general"}
Tone: {state.tone}
Key message: {key_message}

FULL SLIDE PLAN:
{slide_plan_summary}

CURRENT SLIDE:
- Slide ID: {slide["slide_id"]}
- Section: {section}
- Purpose: {purpose}
- Type: {slide_type}

PREVIOUS SLIDES CONTENT (DO NOT REPEAT):
{previous_summary or "None yet — this is the first slide."}
{retry_context}
Generate content for the current slide following the JSON schema for type "{slide_type}".
Each text field must be specific and mechanism-driven.
For feature/problem/benefit slides, generate 3-4 bullet points where each bullet
explains a concrete mechanism or structural detail specific to "{state.topic}".

{_get_schema_for_type(slide_type)}"""

    try:
        content = await call_llm_json(system_prompt, user_prompt)
    except Exception:
        content = {"title": purpose, "body": "Content unavailable"}

    return content


def _get_schema_for_type(slide_type: str) -> str:
    """Return the JSON schema instruction for a given slide type."""
    schemas = {
        "title_slide": 'Return: {"title": "...", "subtitle": "...", "presenter": ""}',
        "section_header": 'Return: {"section_title": "...", "tagline": "..."}',
        "agenda_slide": 'Return: {"title": "Agenda", "items": ["item1", "item2", "item3"]}',
        "problem_slide": 'Return: {"title": "...", "cards": [{"icon": "⚠", "label": "...", "description": "mechanism-driven detail"}]} — generate 3-4 cards',
        "stats_slide": 'Return: {"title": "...", "stat": "XX%", "stat_label": "...", "description": "...", "source": "..."}',
        "feature_slide": 'Return: {"title": "...", "features": [{"icon": "⚡", "label": "...", "description": "mechanism-driven detail"}]} — generate 3-4 features',
        "comparison_slide": 'Return: {"title": "...", "left_label": "...", "left_points": ["..."], "right_label": "...", "right_points": ["..."]}',
        "timeline_slide": 'Return: {"title": "...", "events": [{"year": "...", "label": "..."}]}',
        "example_slide": 'Return: {"title": "...", "example_title": "...", "context": "...", "result": "...", "takeaway": "..."}',
        "conclusion_slide": 'Return: {"title": "...", "bullets": ["mechanism-driven point 1", "point 2", "point 3"], "key_takeaway": "..."}',
        "cta_slide": 'Return: {"title": "...", "cta_text": "...", "contact": "..."}',
        "quote_slide": 'Return: {"quote": "...", "attribution": "..."}',
        "image_slide": 'Return: {"title": "...", "caption": "..."}',
        "thank_you_slide": 'Return: {"title": "Thank You", "message": "...", "contact": "..."}',
    }
    return schemas.get(slide_type, 'Return: {"title": "...", "body": "..."}')


# ═══════════════════════════════════════════════════════════════════════
# Phase 2 – Self-Validation
# ═══════════════════════════════════════════════════════════════════════

async def _validate_content(
    content: dict,
    slide: dict,
    previous_contents: list[dict],
    topic: str,
) -> dict:
    """Validate content for repetition, generality, and depth."""
    content_text = _flatten_content(content)
    previous_text = " | ".join(
        _flatten_content(p["content"]) for p in previous_contents
    )

    system_prompt = """You are a strict quality validator for presentation slides.
Evaluate the slide content against three criteria. Return ONLY valid JSON.

CRITERIA:
1. REPETITION CHECK: Does this slide repeat meaning/information from previous slides?
2. GENERIC CHECK: Is this content reusable across unrelated industries/topics?
3. DEPTH CHECK: Does every bullet contain a concrete mechanism or structural detail?

Return: {"passed": true/false, "reason": "explanation if failed"}
If ALL three checks pass, return {"passed": true, "reason": "all checks passed"}.
If ANY check fails, return {"passed": false, "reason": "which check failed and why"}."""

    user_prompt = f"""Topic: {topic}
Slide section: {slide["section"]}
Slide purpose: {slide["purpose"]}

CURRENT SLIDE CONTENT:
{content_text}

PREVIOUS SLIDES CONTENT:
{previous_text or "None"}

Evaluate strictly. A slide FAILS if:
- It repeats the same idea as a previous slide (even rephrased)
- Its content could apply to any random startup/company without changes
- Any bullet lacks a specific mechanism or structural detail"""

    try:
        result = await call_llm_json(system_prompt, user_prompt)
        return {
            "passed": bool(result.get("passed", False)),
            "reason": result.get("reason", "unknown"),
        }
    except Exception as exc:
        logger.warning("[validation] LLM validation failed: %s — passing by default", exc)
        return {"passed": True, "reason": "validation skipped due to error"}


# ═══════════════════════════════════════════════════════════════════════
# Phase 3 – Critic Loop (Investor Mode)
# ═══════════════════════════════════════════════════════════════════════

async def _critic_evaluate(
    content: dict,
    slide: dict,
    topic: str,
) -> dict:
    """Evaluate slide content as a strict investor critic."""
    content_text = _flatten_content(content)

    system_prompt = """You are a strict venture capital investor evaluating a pitch deck slide.
You have seen hundreds of pitch decks and have zero tolerance for:
- Vague language with no substance
- Claims without structural clarity on HOW something works
- Content that lacks specificity to the actual business/topic
- Buzzwords that substitute for real explanation

Return ONLY valid JSON:
{"accepted": true/false, "reason": "why accepted or rejected"}"""

    user_prompt = f"""Topic: {topic}
Slide section: {slide["section"]}
Slide purpose: {slide["purpose"]}

SLIDE CONTENT:
{content_text}

As a strict investor, would you accept this slide in a pitch deck?
Reject if the content is vague, not convincing, lacks structural clarity, or is not specific enough."""

    try:
        result = await call_llm_json(system_prompt, user_prompt)
        return {
            "accepted": bool(result.get("accepted", False)),
            "reason": result.get("reason", "unknown"),
        }
    except Exception as exc:
        logger.warning("[critic] LLM critic failed: %s — accepting by default", exc)
        return {"accepted": True, "reason": "critic skipped due to error"}


# ═══════════════════════════════════════════════════════════════════════
# Phase 4 – Slide Intent Enforcement
# ═══════════════════════════════════════════════════════════════════════

async def _enforce_intent(
    content: dict,
    slide: dict,
    topic: str,
) -> dict:
    """Ensure slide content strictly adheres to the declared intent."""
    content_text = _flatten_content(content)
    section = slide["section"]
    purpose = slide["purpose"]

    system_prompt = """You are a strict slide intent enforcer for presentations.
Your job is to verify that a slide's content matches its declared section and purpose EXACTLY.

Rules:
- Problem slides must ONLY contain problems, pain points, or challenges
- Solution slides must ONLY contain the solution, approach, or methodology
- Market slides must ONLY contain market data, sizing, or opportunity
- Product slides must ONLY explain how the product works
- Benefits slides must ONLY contain specific advantages or outcomes
- Intro slides must ONLY introduce the topic
- Conclusion slides must ONLY summarize or provide a call to action

Return ONLY valid JSON:
{"compliant": true/false, "reason": "explanation if not compliant"}"""

    user_prompt = f"""Topic: {topic}
Slide section: {section}
Slide purpose: {purpose}
Slide type: {slide["type"]}

SLIDE CONTENT:
{content_text}

Is this content strictly aligned with its declared section "{section}" and purpose "{purpose}"?
Flag any content that belongs in a different section."""

    try:
        result = await call_llm_json(system_prompt, user_prompt)
        return {
            "compliant": bool(result.get("compliant", False)),
            "reason": result.get("reason", "unknown"),
        }
    except Exception as exc:
        logger.warning("[intent] LLM intent check failed: %s — passing by default", exc)
        return {"compliant": True, "reason": "intent check skipped due to error"}


# ═══════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════

def _flatten_content(content: dict) -> str:
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
