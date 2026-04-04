"""Slide Evaluator — strict post-generation quality gate.

Takes already-generated slides and:
  Phase 1 – Hard Validation (deterministic + LLM semantic)
  Phase 2 – Scoring (specificity, mechanism, uniqueness, clarity)
  Phase 3 – Strict Critic (no-mercy investor mode)
  Phase 4 – Targeted Regeneration (specific fix instructions)
  Phase 5 – Intent Enforcement
  Phase 6 – Final Output (improved slide + report)

This module is NOT a content generator — it is a strict evaluator,
validator, and improver of slide content produced by earlier stages.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Optional

from models.presentation_state import PresentationState
from services.llm_client import call_llm_json

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────

MAX_IMPROVEMENT_ATTEMPTS = 3
MIN_ACCEPTABLE_SCORE = 4.0
MIN_BULLET_WORDS = 6

# Deterministic banned phrases — presence of ANY triggers hard rejection
GENERIC_PHRASES = [
    "improves efficiency",
    "scalable",
    "ai-powered",
    "enhances",
    "robust",
    "seamless",
    "leveraging ai",
    "innovative solution",
    "cutting-edge",
    "game-changing",
    "next-generation",
    "state-of-the-art",
    "world-class",
    "best-in-class",
]

# Pre-formatted for prompt injection (avoids repeated JSON serialization)
_GENERIC_PHRASES_STR = json.dumps(GENERIC_PHRASES)


# ═══════════════════════════════════════════════════════════════════════
# Public API
# ═══════════════════════════════════════════════════════════════════════

async def evaluate_and_improve_slides(
    state: PresentationState,
) -> PresentationState:
    """Evaluate every slide in *state.structured_slides* and improve weak ones.

    Returns updated state with:
      - ``structured_slides`` replaced with improved versions
      - ``metadata["slide_evaluations"]`` containing per-slide reports
    """
    if not state.structured_slides:
        return state

    previous_contents: list[dict] = []
    improved_slides: list[dict] = []
    evaluations: list[dict] = []

    for slide_data in state.structured_slides:
        slide_id = slide_data["slide_id"]
        slide_type = slide_data["type"]
        content = slide_data.get("content", {})

        # Find matching plan entry for intent info
        plan_entry = _find_plan_entry(state, slide_id)

        evaluation = await _evaluate_slide(
            content=content,
            slide_plan_entry=plan_entry,
            previous_contents=previous_contents,
            topic=state.topic,
        )

        final_content = content
        if not evaluation["is_valid"] or evaluation["overall_score"] < MIN_ACCEPTABLE_SCORE:
            # Attempt targeted regeneration
            final_content = await _improve_slide(
                content=content,
                evaluation=evaluation,
                slide_plan_entry=plan_entry,
                previous_contents=previous_contents,
                state=state,
            )
            # Re-evaluate after improvement
            evaluation = await _evaluate_slide(
                content=final_content,
                slide_plan_entry=plan_entry,
                previous_contents=previous_contents,
                topic=state.topic,
            )

        improved_slides.append({
            "slide_id": slide_id,
            "type": slide_type,
            "content": final_content,
            "image_path": slide_data.get("image_path"),
        })
        evaluations.append({
            "slide_id": slide_id,
            **evaluation,
        })
        previous_contents.append({
            "slide_id": slide_id,
            "section": plan_entry.get("section", ""),
            "purpose": plan_entry.get("purpose", ""),
            "content": final_content,
        })

    meta = dict(state.metadata or {})
    meta["slide_evaluations"] = evaluations

    return state.model_copy(update={
        "structured_slides": improved_slides,
        "metadata": meta,
    })


# ═══════════════════════════════════════════════════════════════════════
# Core evaluation pipeline
# ═══════════════════════════════════════════════════════════════════════

async def _evaluate_slide(
    content: dict,
    slide_plan_entry: dict,
    previous_contents: list[dict],
    topic: str,
) -> dict:
    """Run Phases 1-3+5 and return a structured evaluation result."""
    content_text = _flatten_content(content)

    # ── Phase 1: Hard Validation ─────────────────────────────────
    hard_result = _deterministic_checks(content)
    semantic_result = await _semantic_checks(
        content_text, previous_contents, topic
    )

    is_valid = hard_result["passed"] and semantic_result["passed"]
    validation_failures = hard_result["failures"] + semantic_result["failures"]

    # ── Phase 2: Scoring ─────────────────────────────────────────
    scores = await _score_slide(content_text, slide_plan_entry, topic)

    # ── Phase 3: Strict Critic ───────────────────────────────────
    critic = await _strict_critic(content_text, slide_plan_entry, topic)

    # ── Phase 5: Intent Enforcement ──────────────────────────────
    intent = await _check_intent(content_text, slide_plan_entry, topic)

    # Merge failures
    if not critic["accepted"]:
        is_valid = False
        validation_failures.append(f"critic_rejected: {critic['reason']}")
    if not intent["compliant"]:
        is_valid = False
        validation_failures.append(f"intent_violation: {intent['reason']}")

    overall = scores.get("overall", 0)
    if overall < MIN_ACCEPTABLE_SCORE:
        is_valid = False

    return {
        "is_valid": is_valid,
        "validation_failures": validation_failures,
        "scores": scores,
        "overall_score": overall,
        "critic_feedback": critic,
        "intent_check": intent,
    }


# ═══════════════════════════════════════════════════════════════════════
# Phase 1A – Deterministic Hard Checks
# ═══════════════════════════════════════════════════════════════════════

def _deterministic_checks(content: dict) -> dict:
    """Fast, zero-LLM checks for banned phrases, bullet length, etc."""
    failures: list[str] = []
    text_blob = _flatten_content(content).lower()

    # Check for generic/banned phrases
    for phrase in GENERIC_PHRASES:
        if phrase in text_blob:
            failures.append(f"generic_phrase: '{phrase}'")

    # Check bullet/description lengths
    bullets = _extract_bullets(content)
    for i, bullet in enumerate(bullets):
        word_count = len(bullet.split())
        if word_count < MIN_BULLET_WORDS:
            failures.append(
                f"short_bullet[{i}]: '{bullet}' ({word_count} words, min {MIN_BULLET_WORDS})"
            )

    return {"passed": len(failures) == 0, "failures": failures}


# ═══════════════════════════════════════════════════════════════════════
# Phase 1B – Semantic Checks (LLM)
# ═══════════════════════════════════════════════════════════════════════

async def _semantic_checks(
    content_text: str,
    previous_contents: list[dict],
    topic: str,
) -> dict:
    """LLM-based check for idea overlap with previous slides."""
    if not previous_contents:
        return {"passed": True, "failures": []}

    previous_text = "\n---\n".join(
        f"Slide {p['slide_id']} ({p.get('section', '')}):\n{_flatten_content(p['content'])}"
        for p in previous_contents
    )

    system_prompt = """You are a strict repetition detector for presentation slides.
Compare the CURRENT slide content against ALL previous slides.

Return ONLY valid JSON:
{
  "has_overlap": true/false,
  "overlapping_ideas": ["description of repeated idea 1", ...]
}

Mark has_overlap=true if ANY idea, concept, or claim is substantially
repeated — even if rephrased with different words."""

    user_prompt = f"""Topic: {topic}

CURRENT SLIDE:
{content_text}

PREVIOUS SLIDES:
{previous_text}

Check for semantic overlap. Be strict — even partial idea reuse counts."""

    try:
        result = await call_llm_json(system_prompt, user_prompt)
        has_overlap = bool(result.get("has_overlap", False))
        overlaps = result.get("overlapping_ideas", [])
        failures = [f"repeated_idea: {idea}" for idea in overlaps] if has_overlap else []
        return {"passed": not has_overlap, "failures": failures}
    except Exception as exc:
        logger.warning("[evaluator] Semantic check failed: %s — passing by default", exc)
        return {"passed": True, "failures": []}


# ═══════════════════════════════════════════════════════════════════════
# Phase 2 – Scoring
# ═══════════════════════════════════════════════════════════════════════

async def _score_slide(
    content_text: str,
    slide_plan_entry: dict,
    topic: str,
) -> dict:
    """Score slide on four dimensions (1-5 each) and compute overall."""
    system_prompt = """You are a strict slide quality scorer. Score the slide on four dimensions.

Return ONLY valid JSON:
{
  "specificity": <1-5>,
  "mechanism": <1-5>,
  "uniqueness": <1-5>,
  "clarity": <1-5>
}

Scoring rules:
- 5: Exceptional — concrete, unique, impossible to confuse with another topic
- 4: Good — mostly specific, minor improvements possible
- 3: Average — some vague areas, partially reusable across topics
- 2: Weak — mostly generic, lacks concrete mechanisms
- 1: Unacceptable — could apply to any startup, no mechanisms

Be STRICT. Most generic startup content should score 2 or lower."""

    user_prompt = f"""Topic: {topic}
Slide section: {slide_plan_entry.get('section', 'unknown')}
Slide purpose: {slide_plan_entry.get('purpose', 'unknown')}

SLIDE CONTENT:
{content_text}

Score strictly. Do NOT be generous."""

    try:
        scores = await call_llm_json(system_prompt, user_prompt)
        # Clamp to [1, 5] and compute average
        dims = ["specificity", "mechanism", "uniqueness", "clarity"]
        for d in dims:
            scores[d] = max(1, min(5, int(scores.get(d, 1))))
        scores["overall"] = round(sum(scores[d] for d in dims) / len(dims), 1)
        return scores
    except Exception as exc:
        logger.warning("[evaluator] Scoring failed: %s — returning defaults", exc)
        return {
            "specificity": 3, "mechanism": 3, "uniqueness": 3, "clarity": 3,
            "overall": 3.0,
        }


# ═══════════════════════════════════════════════════════════════════════
# Phase 3 – Strict Critic (No Mercy)
# ═══════════════════════════════════════════════════════════════════════

async def _strict_critic(
    content_text: str,
    slide_plan_entry: dict,
    topic: str,
) -> dict:
    """Tier-1 investor critic with zero tolerance for weakness."""
    system_prompt = """You are a Tier-1 venture capital investor who has reviewed
thousands of pitch decks. You have ZERO tolerance for:

- Generic claims with no backing mechanism
- Predictable startup language that sounds like a template
- Content with no defensibility or structural insight
- Buzzwords substituting for real explanation

Examples of instant rejection:
❌ "This improves efficiency" → No mechanism or measurable insight
❌ "Our AI-powered platform" → No explanation of what the AI does
❌ "Scalable architecture" → No detail on how it scales

Return ONLY valid JSON:
{"accepted": true/false, "reason": "detailed explanation", "weaknesses": ["weakness1", ...]}

Be HARSH. Reject anything that feels average or template-like."""

    user_prompt = f"""Topic: {topic}
Slide section: {slide_plan_entry.get('section', 'unknown')}
Slide purpose: {slide_plan_entry.get('purpose', 'unknown')}

SLIDE CONTENT:
{content_text}

As a Tier-1 investor, evaluate this slide. Be merciless."""

    try:
        result = await call_llm_json(system_prompt, user_prompt)
        return {
            "accepted": bool(result.get("accepted", False)),
            "reason": result.get("reason", "unknown"),
            "weaknesses": result.get("weaknesses", []),
        }
    except Exception as exc:
        logger.warning("[evaluator] Critic failed: %s — accepting by default", exc)
        return {"accepted": True, "reason": "critic skipped due to error", "weaknesses": []}


# ═══════════════════════════════════════════════════════════════════════
# Phase 4 – Targeted Regeneration
# ═══════════════════════════════════════════════════════════════════════

async def _improve_slide(
    content: dict,
    evaluation: dict,
    slide_plan_entry: dict,
    previous_contents: list[dict],
    state: PresentationState,
) -> dict:
    """Regenerate slide with specific, targeted fix instructions."""
    failures = evaluation.get("validation_failures", [])
    scores = evaluation.get("scores", {})
    critic = evaluation.get("critic_feedback", {})

    # Build targeted fix instructions from failure analysis
    fix_instructions = _build_fix_instructions(failures, scores, critic)

    previous_summary = ""
    if previous_contents:
        previous_summary = json.dumps(
            [{"slide_id": p["slide_id"], "section": p["section"],
              "content": p["content"]}
             for p in previous_contents],
            indent=2,
        )

    best_content = content

    for attempt in range(1, MAX_IMPROVEMENT_ATTEMPTS + 1):
        system_prompt = f"""You are a strict slide content improver for presentations.
You are given a WEAK slide and specific instructions on what to fix.

STRICT RULES:
1. Each bullet MUST include a concrete mechanism (how it works) OR a specific structural detail.
2. FORBIDDEN phrases: {_GENERIC_PHRASES_STR}
3. Every bullet must have at least {MIN_BULLET_WORDS} meaningful words.
4. Content must be specific to "{state.topic}" — not reusable for other topics.
5. Content must NOT repeat ideas from previous slides.

Return ONLY valid JSON matching the original slide structure. No markdown, no backticks."""

        user_prompt = f"""Topic: {state.topic}
Audience: {state.audience or "general"}
Tone: {state.tone}

SLIDE SECTION: {slide_plan_entry.get('section', 'unknown')}
SLIDE PURPOSE: {slide_plan_entry.get('purpose', 'unknown')}
SLIDE TYPE: {slide_plan_entry.get('type', 'unknown')}

CURRENT WEAK CONTENT:
{json.dumps(content, indent=2)}

SPECIFIC FIX INSTRUCTIONS:
{fix_instructions}

PREVIOUS SLIDES (DO NOT REPEAT):
{previous_summary or "None"}

Rewrite this slide fixing ALL issues. Keep the same JSON structure."""

        try:
            improved = await call_llm_json(system_prompt, user_prompt)
            # Verify deterministic checks pass on improved version
            check = _deterministic_checks(improved)
            if check["passed"]:
                best_content = improved
                break
            else:
                logger.warning(
                    "[evaluator] Improvement attempt %d/%d still has issues: %s",
                    attempt, MAX_IMPROVEMENT_ATTEMPTS, check["failures"],
                )
                best_content = improved
                content = improved  # Use improved version as base for next attempt
        except Exception as exc:
            logger.warning(
                "[evaluator] Improvement attempt %d/%d failed: %s",
                attempt, MAX_IMPROVEMENT_ATTEMPTS, exc,
            )

    return best_content


def _build_fix_instructions(
    failures: list[str],
    scores: dict,
    critic: dict,
) -> str:
    """Build specific, actionable fix instructions from evaluation results."""
    instructions: list[str] = []

    # Classify failures and build targeted fixes
    has_repetition = any("repeated" in f.lower() for f in failures)
    has_generic = any("generic_phrase" in f for f in failures)
    has_short = any("short_bullet" in f for f in failures)
    has_critic_rejection = any("critic_rejected" in f for f in failures)
    has_intent_violation = any("intent_violation" in f for f in failures)

    if has_repetition:
        instructions.append(
            "REPETITION FIX: This slide repeats ideas from previous slides. "
            "Make ALL content completely different — introduce new concepts, "
            "new mechanisms, and new structural details not mentioned before."
        )

    if has_generic:
        generic_found = [
            f.split("'")[1] for f in failures
            if f.startswith("generic_phrase") and "'" in f
        ]
        instructions.append(
            f"GENERIC FIX: Remove these banned phrases: {generic_found}. "
            "Replace with specific mechanisms — explain HOW things work, "
            "not just WHAT they do. Add concrete systems, processes, or data."
        )

    if has_short:
        instructions.append(
            f"DEPTH FIX: Some bullets are too short (< {MIN_BULLET_WORDS} words). "
            "Each bullet must contain a concrete mechanism or structural detail. "
            "Expand with specifics: numbers, processes, technical details."
        )

    if has_critic_rejection:
        weaknesses = critic.get("weaknesses", [])
        instructions.append(
            "INVESTOR FIX: A strict investor rejected this slide. "
            f"Weaknesses identified: {weaknesses}. "
            "Make content defensible, specific, and structurally clear."
        )

    if has_intent_violation:
        instructions.append(
            "INTENT FIX: Content does not match the declared slide intent. "
            "Rewrite to strictly match the slide's section and purpose."
        )

    # Score-based fixes
    if scores.get("specificity", 5) < MIN_ACCEPTABLE_SCORE:
        instructions.append(
            "SPECIFICITY FIX: Score too low. Add topic-specific details "
            "that could NOT apply to any other company or industry."
        )
    if scores.get("mechanism", 5) < MIN_ACCEPTABLE_SCORE:
        instructions.append(
            "MECHANISM FIX: Score too low. Every bullet must explain "
            "HOW something works, not just what it is."
        )
    if scores.get("uniqueness", 5) < MIN_ACCEPTABLE_SCORE:
        instructions.append(
            "UNIQUENESS FIX: Score too low. Content must be completely "
            "original — not reusable across industries or companies."
        )
    if scores.get("clarity", 5) < MIN_ACCEPTABLE_SCORE:
        instructions.append(
            "CLARITY FIX: Score too low. Restructure for clear, "
            "unambiguous communication. One idea per bullet."
        )

    if not instructions:
        instructions.append(
            "GENERAL FIX: Improve overall quality. Make content more "
            "specific, mechanism-driven, and investor-grade."
        )

    return "\n".join(f"- {inst}" for inst in instructions)


# ═══════════════════════════════════════════════════════════════════════
# Phase 5 – Intent Enforcement
# ═══════════════════════════════════════════════════════════════════════

async def _check_intent(
    content_text: str,
    slide_plan_entry: dict,
    topic: str,
) -> dict:
    """Verify content matches the declared slide intent."""
    section = slide_plan_entry.get("section", "unknown")
    purpose = slide_plan_entry.get("purpose", "unknown")

    system_prompt = """You are a strict slide intent enforcer.
Verify that a slide's content EXACTLY matches its declared section and purpose.

Intent rules:
- Problem slides → ONLY problems, pain points, challenges
- Solution slides → ONLY the solution, approach, methodology
- Market slides → ONLY market data, sizing, opportunity
- Product slides → ONLY how the product works
- Benefits slides → ONLY specific advantages or outcomes
- Intro slides → ONLY topic introduction
- Conclusion slides → ONLY summary or call to action

Return ONLY valid JSON:
{"compliant": true/false, "reason": "explanation"}"""

    user_prompt = f"""Topic: {topic}
Slide section: {section}
Slide purpose: {purpose}

SLIDE CONTENT:
{content_text}

Is this content STRICTLY aligned with section "{section}" and purpose "{purpose}"?"""

    try:
        result = await call_llm_json(system_prompt, user_prompt)
        return {
            "compliant": bool(result.get("compliant", False)),
            "reason": result.get("reason", "unknown"),
        }
    except Exception as exc:
        logger.warning("[evaluator] Intent check failed: %s — passing by default", exc)
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


def _extract_bullets(content: dict) -> list[str]:
    """Extract all descriptive text items from slide content for quality checks.

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


def _find_plan_entry(state: PresentationState, slide_id: int) -> dict:
    """Find the slide plan entry matching a slide_id."""
    if state.slide_plan:
        for entry in state.slide_plan:
            if entry.get("slide_id") == slide_id:
                return entry
    return {"section": "unknown", "purpose": "unknown", "type": "unknown", "slide_id": slide_id}
