"""Deck Consistency Optimizer — full-deck quality alignment pass.

Runs AFTER per-slide evaluation to ensure the entire presentation is:
  1. Stylistically consistent (uniform tone across all slides)
  2. Depth-consistent (no weak slide next to a strong slide)
  3. Bullet-structure consistent (similar length, mechanism-driven style)
  4. Terminology-consistent (same terms used across deck)
  5. Clean of leftover generic phrases

This module does NOT:
  - Change slide intent or order
  - Introduce new ideas
  - Generate content from scratch

It only REFINES and ALIGNS existing slides.
"""

from __future__ import annotations

import json
import logging
from typing import Optional

from models.presentation_state import PresentationState
from services.llm_client import call_llm_json
from pipeline.slide_utils import flatten_content, extract_bullets, find_plan_entry

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────

# Score gap threshold — if a slide's score is this much below the
# deck's best, it's flagged as "weak" and must be improved.
WEAKNESS_THRESHOLD = 1.0

# Maximum LLM calls for the full-deck optimization pass
MAX_REWRITE_ATTEMPTS = 2

# Generic phrases that must NOT survive into the final deck
BANNED_PHRASES = [
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


# ═══════════════════════════════════════════════════════════════════════
# Public API
# ═══════════════════════════════════════════════════════════════════════

async def optimize_deck_consistency(
    state: PresentationState,
) -> PresentationState:
    """Analyze the full deck and fix inconsistencies across slides.

    Returns updated state with:
      - ``structured_slides`` rewritten for consistency
      - ``metadata["deck_consistency"]`` containing the analysis report
    """
    if not state.structured_slides or len(state.structured_slides) < 2:
        return state

    slides = state.structured_slides
    evaluations = (state.metadata or {}).get("slide_evaluations", [])

    # ── Step 1: Identify weak slides ─────────────────────────────
    weak_indices = _find_weak_slides(slides, evaluations)

    # ── Step 2: Detect terminology drift ─────────────────────────
    terminology_issues = await _detect_terminology_drift(slides, state.topic)

    # ── Step 3: Scan for leftover generic phrases ────────────────
    generic_issues = _scan_leftover_generics(slides)

    # ── Step 4: Analyze structural inconsistencies ───────────────
    structural_issues = _analyze_bullet_structure(slides)

    # Collect all slides that need work
    slides_needing_work = set(weak_indices)
    for issue in terminology_issues:
        slides_needing_work.update(issue.get("slide_indices", []))
    for issue in generic_issues:
        slides_needing_work.add(issue["slide_index"])
    for issue in structural_issues:
        slides_needing_work.add(issue["slide_index"])

    if not slides_needing_work:
        logger.info("[deck-optimizer] No consistency issues found")
        meta = dict(state.metadata or {})
        meta["deck_consistency"] = {
            "weak_slides": [],
            "terminology_issues": [],
            "generic_issues": [],
            "structural_issues": [],
            "slides_rewritten": 0,
        }
        return state.model_copy(update={"metadata": meta})

    logger.info(
        "[deck-optimizer] Found %d slides needing consistency fixes: %s",
        len(slides_needing_work), sorted(slides_needing_work),
    )

    # ── Step 5: Rewrite weak/inconsistent slides ─────────────────
    improved_slides = list(slides)  # shallow copy

    for idx in sorted(slides_needing_work):
        if idx >= len(slides):
            continue

        slide_data = slides[idx]
        slide_issues = _collect_issues_for_slide(
            idx, weak_indices, terminology_issues,
            generic_issues, structural_issues,
        )

        plan_entry = _find_plan_entry(state, slide_data["slide_id"])

        improved_content = await _rewrite_for_consistency(
            slide_data=slide_data,
            slide_issues=slide_issues,
            full_deck=slides,
            plan_entry=plan_entry,
            state=state,
        )

        improved_slides[idx] = {
            **slide_data,
            "content": improved_content,
        }

    meta = dict(state.metadata or {})
    meta["deck_consistency"] = {
        "weak_slides": weak_indices,
        "terminology_issues": terminology_issues,
        "generic_issues": [g["detail"] for g in generic_issues],
        "structural_issues": [s["detail"] for s in structural_issues],
        "slides_rewritten": len(slides_needing_work),
    }

    return state.model_copy(update={
        "structured_slides": improved_slides,
        "metadata": meta,
    })


# ═══════════════════════════════════════════════════════════════════════
# Step 1 – Identify weak slides by score gap
# ═══════════════════════════════════════════════════════════════════════

def _find_weak_slides(
    slides: list[dict],
    evaluations: list[dict],
) -> list[int]:
    """Find slide indices whose score is significantly below the best."""
    if not evaluations:
        return []

    scores_by_id = {e["slide_id"]: e.get("overall_score", 0) for e in evaluations}
    if not scores_by_id:
        return []

    best_score = max(scores_by_id.values())
    weak: list[int] = []

    for i, slide in enumerate(slides):
        sid = slide.get("slide_id")
        score = scores_by_id.get(sid, 0)
        if best_score - score >= WEAKNESS_THRESHOLD:
            weak.append(i)

    return weak


# ═══════════════════════════════════════════════════════════════════════
# Step 2 – Detect terminology drift (LLM)
# ═══════════════════════════════════════════════════════════════════════

async def _detect_terminology_drift(
    slides: list[dict],
    topic: str,
) -> list[dict]:
    """Use LLM to find inconsistent terminology across slides."""
    deck_text = _build_deck_text(slides)

    system_prompt = """You are a presentation consistency reviewer.
Analyze the FULL DECK for terminology inconsistencies.

Look for:
- Same concept described with different terms across slides
  (e.g., "workflow automation" vs "process automation")
- Tone shifts (e.g., formal in one slide, casual in another)
- Inconsistent naming of products, features, or processes

Return ONLY valid JSON:
{
  "issues": [
    {
      "type": "terminology_drift",
      "description": "what is inconsistent",
      "slide_indices": [0, 3],
      "suggested_term": "preferred term to use consistently"
    }
  ]
}

If the deck is consistent, return {"issues": []}."""

    user_prompt = f"""Topic: {topic}

FULL DECK:
{deck_text}

Check for terminology and tone inconsistencies across all slides."""

    try:
        result = await call_llm_json(system_prompt, user_prompt)
        return result.get("issues", [])
    except Exception as exc:
        logger.warning("[deck-optimizer] Terminology check failed: %s", exc)
        return []


# ═══════════════════════════════════════════════════════════════════════
# Step 3 – Scan leftover generic phrases (deterministic)
# ═══════════════════════════════════════════════════════════════════════

def _scan_leftover_generics(slides: list[dict]) -> list[dict]:
    """Deterministic scan for banned phrases that survived earlier passes."""
    issues: list[dict] = []
    for i, slide in enumerate(slides):
        content = slide.get("content", {})
        text_blob = _flatten_content(content).lower()
        for phrase in BANNED_PHRASES:
            if phrase in text_blob:
                issues.append({
                    "slide_index": i,
                    "detail": f"slide {i}: leftover generic phrase '{phrase}'",
                })
    return issues


# ═══════════════════════════════════════════════════════════════════════
# Step 4 – Analyze bullet structure consistency (deterministic)
# ═══════════════════════════════════════════════════════════════════════

def _analyze_bullet_structure(slides: list[dict]) -> list[dict]:
    """Check that all slides have similar bullet length and depth."""
    issues: list[dict] = []

    # Collect bullet lengths per slide
    all_lengths: list[list[int]] = []
    for slide in slides:
        bullets = _extract_bullets(slide.get("content", {}))
        lengths = [len(b.split()) for b in bullets]
        all_lengths.append(lengths)

    # Compute deck-wide stats (only for slides with bullets)
    flat_lengths = [l for lengths in all_lengths for l in lengths]
    if not flat_lengths:
        return []

    avg_length = sum(flat_lengths) / len(flat_lengths)

    # Flag slides whose bullets deviate significantly from the deck average
    for i, lengths in enumerate(all_lengths):
        if not lengths:
            continue
        slide_avg = sum(lengths) / len(lengths)
        # If a slide's avg bullet length is less than half or more than
        # double the deck average, it's an outlier
        if slide_avg < avg_length * 0.5:
            issues.append({
                "slide_index": i,
                "detail": (
                    f"slide {i}: bullets too short "
                    f"(avg {slide_avg:.0f} words vs deck avg {avg_length:.0f})"
                ),
            })
        elif slide_avg > avg_length * 2.0:
            issues.append({
                "slide_index": i,
                "detail": (
                    f"slide {i}: bullets too long "
                    f"(avg {slide_avg:.0f} words vs deck avg {avg_length:.0f})"
                ),
            })

    return issues


# ═══════════════════════════════════════════════════════════════════════
# Step 5 – Rewrite for consistency (LLM)
# ═══════════════════════════════════════════════════════════════════════

async def _rewrite_for_consistency(
    slide_data: dict,
    slide_issues: list[str],
    full_deck: list[dict],
    plan_entry: dict,
    state: PresentationState,
) -> dict:
    """Rewrite a single slide to fix consistency issues.

    The rewrite must:
    - Fix all identified issues
    - Match the tone and style of the strongest slides
    - NOT change the slide intent
    - NOT introduce new ideas
    """
    content = slide_data.get("content", {})

    # Build a reference of the strongest slides for tone/style matching
    reference_text = _build_deck_text(full_deck)

    system_prompt = f"""You are a presentation consistency optimizer.
You are given ONE slide that has consistency issues compared to the rest of the deck.

STRICT RULES:
1. Fix ONLY the identified issues — do not change content that is already good.
2. Match the tone, style, and depth of the strongest slides in the deck.
3. Do NOT change the slide intent or introduce new ideas.
4. All bullets must be mechanism-driven and specific to "{state.topic}".
5. FORBIDDEN phrases: {json.dumps(BANNED_PHRASES)}
6. Maintain consistent terminology with the rest of the deck.
7. Bullet length should be similar to other slides in the deck.

Return ONLY valid JSON matching the original slide structure."""

    user_prompt = f"""Topic: {state.topic}
Tone: {state.tone}
Audience: {state.audience or "general"}

SLIDE SECTION: {plan_entry.get('section', 'unknown')}
SLIDE PURPOSE: {plan_entry.get('purpose', 'unknown')}

ISSUES TO FIX:
{chr(10).join(f'- {issue}' for issue in slide_issues)}

CURRENT SLIDE CONTENT:
{json.dumps(content, indent=2)}

FULL DECK (for tone/style reference):
{reference_text}

Rewrite this slide fixing ALL consistency issues while keeping the same intent and JSON structure."""

    for attempt in range(1, MAX_REWRITE_ATTEMPTS + 1):
        try:
            improved = await call_llm_json(system_prompt, user_prompt)
            # Verify no banned phrases remain
            text_blob = _flatten_content(improved).lower()
            has_banned = any(p in text_blob for p in BANNED_PHRASES)
            if not has_banned:
                return improved
            else:
                logger.warning(
                    "[deck-optimizer] Rewrite attempt %d/%d still has banned phrases",
                    attempt, MAX_REWRITE_ATTEMPTS,
                )
                content = improved  # Use as base for next attempt
        except Exception as exc:
            logger.warning(
                "[deck-optimizer] Rewrite attempt %d/%d failed: %s",
                attempt, MAX_REWRITE_ATTEMPTS, exc,
            )

    # Return best effort (last improved version, or original)
    return content


# ═══════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════

def _build_deck_text(slides: list[dict]) -> str:
    """Build a human-readable text summary of the full deck."""
    parts: list[str] = []
    for i, slide in enumerate(slides):
        content = slide.get("content", {})
        parts.append(f"--- Slide {i} (type: {slide.get('type', 'unknown')}) ---")
        parts.append(_flatten_content(content))
    return "\n\n".join(parts)


def _flatten_content(content: dict) -> str:
    """Flatten a slide content dict into a human-readable string."""
    return flatten_content(content)


def _extract_bullets(content: dict) -> list[str]:
    """Extract descriptive text items from slide content for structural checks."""
    return extract_bullets(content)


def _collect_issues_for_slide(
    idx: int,
    weak_indices: list[int],
    terminology_issues: list[dict],
    generic_issues: list[dict],
    structural_issues: list[dict],
) -> list[str]:
    """Collect all issues that apply to a specific slide index."""
    issues: list[str] = []

    if idx in weak_indices:
        issues.append(
            "WEAKNESS: This slide scores significantly lower than the strongest "
            "slides in the deck. Improve depth and specificity to match."
        )

    for term in terminology_issues:
        if idx in term.get("slide_indices", []):
            issues.append(
                f"TERMINOLOGY: {term['description']}. "
                f"Use '{term.get('suggested_term', 'consistent term')}' instead."
            )

    for gen in generic_issues:
        if gen["slide_index"] == idx:
            issues.append(f"GENERIC PHRASE: {gen['detail']}")

    for struct in structural_issues:
        if struct["slide_index"] == idx:
            issues.append(f"STRUCTURE: {struct['detail']}")

    return issues


def _find_plan_entry(state: PresentationState, slide_id: int) -> dict:
    """Find the slide plan entry matching a slide_id."""
    return find_plan_entry(state, slide_id)
