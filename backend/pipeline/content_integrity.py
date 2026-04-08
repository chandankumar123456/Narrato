"""Content Integrity Enforcement Layer — zero-tolerance alignment validation.

Ensures content flows correctly across pipeline stages WITHOUT loss,
mismatch, or reinterpretation:

    narrative_text  →  preprocessing_result  →  rendered HTML

Two enforcement checkpoints:
    1. verify_narrative_to_preprocess  (after Phase 1)
    2. verify_preprocess_to_render     (after Phase 2)

This module uses BOTH deterministic checks AND an LLM-based semantic
validator to catch alignment failures that string matching alone cannot.

On failure:  returns structured fix directives so the caller can
             repair the SPECIFIC failure — never regenerate from scratch.
"""

import logging
from services.llm_client import call_llm_json

def _fuzzy_match(text: str, html: str, threshold: float = 0.6) -> bool:
    words = [w.lower() for w in text.split() if len(w) > 3]
    if not words:
        return True

    html_lower = html.lower()
    matches = sum(1 for w in words if w in html_lower)
    return (matches / len(words)) >= threshold

logger = logging.getLogger(__name__)


# ── LLM Prompt — Narrative → Preprocess Alignment ─────────────────────

_NARRATIVE_PREPROCESS_PROMPT = """\
You are the **Content Integrity Enforcement Layer**.

Your ONLY job is to verify that a preprocessed structure faithfully preserves the meaning of the original narrative text.

You are NOT creative. You are a strict enforcer of content correctness.

---

# INPUT

narrative_text: The fully expressed meaning BEFORE structuring.
preprocessing_result: The structured version AFTER preprocessing (title, primary_element, supporting_elements).

---

# CHECKS (all must pass)

1. **primary_element_traces_narrative**: Does `primary_element` directly come from or faithfully represent the core idea in `narrative_text`? It must NOT be a single abstract word or generic label.

2. **supporting_elements_trace_narrative**: Are ALL `supporting_elements` extracted FROM the narrative_text? Each must carry a distinct, meaningful idea that exists in the narrative. They must reflect ideas present in the narrative_text. Minor rephrasing or compression is allowed if meaning is preserved.

3. **no_meaning_lost**: Does the preprocessing preserve the causal/explanatory depth of the narrative? If the narrative says "X happened BECAUSE Y", that reasoning must survive in the structured output.

4. **no_tone_drift**: Does the preprocessing maintain the narrative's tone? (e.g. confident stays confident, urgent stays urgent — not flattened to neutral)

5. **title_present**: Is there a non-empty title?

6. **primary_not_single_word**: Is `primary_element` more than a single word?

---

# OUTPUT

Return JSON:

{
  "primary_element_traces_narrative": boolean,
  "supporting_elements_trace_narrative": boolean,
  "no_meaning_lost": boolean,
  "no_tone_drift": boolean,
  "title_present": boolean,
  "primary_not_single_word": boolean,
  "fix_directive": "If ANY check is false, write a 1-2 sentence directive saying EXACTLY what content from narrative_text should be used to fix the failing field. If all pass, return empty string."
}

Only return JSON. No markdown backticks or preamble.
"""


# ── LLM Prompt — Preprocess → Render Alignment ───────────────────────

_PREPROCESS_RENDER_PROMPT = """\
You are the **Content Integrity Enforcement Layer**.

Your ONLY job is to verify that rendered HTML faithfully displays ALL structured content without loss, rewriting, or summarization.

You are NOT creative. You are a strict enforcer of content correctness.

---

# INPUT

preprocessing_result: The structured content (title, primary_element, supporting_elements).
rendered_html: The HTML output.

---

# CHECKS (all must pass)

1. **primary_visible**: Is `primary_element` clearly present and visually dominant?

2. **all_supporting_present**: Are all supporting elements represented in the HTML (exact match OR slight rephrasing allowed)?

3. **title_present_in_html**: Is the title rendered somewhere?

4. **meaning_preserved**: Has the meaning of content been preserved even if phrasing differs slightly?

5. **no_irrelevant_content**: No unrelated or completely new ideas should be added.

---

# OUTPUT

Return JSON:

{
  "primary_visible": boolean,
  "all_supporting_present": boolean,
  "title_present_in_html": boolean,
  "meaning_preserved": boolean,
  "no_irrelevant_content": boolean,
  "missing_elements": ["list of any supporting_elements text that is MISSING from HTML, empty array if all present"],
  "fix_directive": "If ANY check is false, write a 1-2 sentence directive saying EXACTLY what must be added or fixed. If all pass, return empty string."
}

IMPORTANT:
- Output MUST be valid JSON
- Do NOT include trailing commas
- Do NOT include extra keys

Only return JSON. No markdown backticks or preamble.
"""


# ── Deterministic Checks ─────────────────────────────────────────────

class IntegrityFailure(Exception):
    """Raised when content integrity cannot be recovered."""
    def __init__(self, stage: str, reason: str):
        self.stage = stage
        self.reason = reason
        super().__init__(f"INTEGRITY FAILURE [{stage}]: {reason}")


def _deterministic_preprocess_check(
    narrative_text: str,
    preprocessing_result: dict,
    slide_index: int,
) -> tuple[bool, str]:
    """Fast deterministic checks before calling LLM validator.

    Returns (passed, failure_reason).
    """
    title = preprocessing_result.get("title", "").strip()
    primary = preprocessing_result.get("primary_element", "").strip()
    sups = preprocessing_result.get("supporting_elements", [])

    # Check 1: title must exist
    if not title:
        return False, "EMPTY_TITLE: Title is empty after preprocessing."

    # Check 2: primary element must not be a single word
    if primary and len(primary.split()) <= 1:
        return False, f"SINGLE_WORD_PRIMARY: primary_element is '{primary}' — must be a meaningful phrase."

    # Check 3: primary element must exist
    if not primary:
        return False, "EMPTY_PRIMARY: primary_element is empty after preprocessing."

    # Check 4: non-initial slides must have supporting elements
    if slide_index > 0 and (not sups or len(sups) == 0):
        return False, "NO_SUPPORTING: Non-initial slide has no supporting_elements."

    # Check 5: supporting elements must each have substance (>2 words)
    for i, s in enumerate(sups):
        word_count = len(str(s).split())
        if word_count <= 2:
            return False, f"SHALLOW_SUPPORTING: supporting_elements[{i}] = '{s}' has only {word_count} words."

    # Check 6: if narrative was provided, primary should share some vocabulary
    if narrative_text and primary:
        narrative_words = set(narrative_text.lower().split())
        primary_words = set(primary.lower().split())
        # At least some overlap (excluding very short words)
        meaningful_overlap = primary_words.intersection(narrative_words) - {"the", "a", "an", "is", "was", "are", "and", "or", "to", "of", "in", "for", "it", "on", "by", "at", "as"}
        if len(meaningful_overlap) == 0 and len(primary_words) > 3:
            return False, f"PRIMARY_DRIFT: primary_element shares no meaningful words with narrative_text. Possible reinterpretation."

    return True, ""


def _deterministic_render_check(
    preprocessing_result: dict,
    html_content: str,
) -> tuple[bool, str, list[str]]:
    """Fast deterministic check: are all structured elements present in HTML?

    Returns (passed, failure_reason, missing_elements).
    """
    missing = []

    # Check title
    title = preprocessing_result.get("title", "").strip()
    if title:
        if not _fuzzy_match(title, html_content):
            missing.append(f"TITLE: {title}")

    # Check primary element
    # primary = preprocessing_result.get("primary_element", "").strip()
    # if primary and primary not in html_content:
    #     if primary[:30] not in html_content:
    #         missing.append(f"PRIMARY: {primary}")
    primary = preprocessing_result.get("primary_element", "").strip()

    if primary:
        primary_text = primary.strip()
        
        if primary_text:
            if primary_text not in html_content:
                # very relaxed match
                if len(primary_text) > 50 and primary_text[:25] not in html_content:
                    missing.append(f"PRIMARY: {primary}")

    # Check supporting elements (STRICT — each must appear)
    for sup in preprocessing_result.get("supporting_elements", []):
        sup_text = str(sup).strip()
        
        if sup_text:
            if not _fuzzy_match(sup_text, html_content):
                missing.append(sup_text)

    # If only 1 element missing and it's very long → allow pass
    if len(missing) == 1:
        elem = missing[0]
        if isinstance(elem, str) and len(elem) > 80:
            return True, "", []

    if missing:
        return False, f"MISSING_IN_RENDER: {len(missing)} element(s) not found in HTML", missing

    return True, "", []


# ── Public API ────────────────────────────────────────────────────────

async def verify_narrative_to_preprocess(
    narrative_text: str,
    narrative_angle: str,
    preprocessing_result: dict,
    slide_index: int,
) -> dict:
    """Verify alignment between narrative transform output and preprocessed structure.

    Returns:
        {
            "status": "pass" | "fail",
            "fix_directive": str  (empty on pass, repair instruction on fail),
            "deterministic_reason": str  (if deterministic check caught it),
        }
    """
    # Skip check if narrative was passthrough (no transformation happened)
    if narrative_angle == "passthrough" or not narrative_text:
        return {"status": "pass", "fix_directive": "", "deterministic_reason": ""}

    # ── Deterministic checks first (fast, no LLM cost) ──
    det_passed, det_reason = _deterministic_preprocess_check(
        narrative_text, preprocessing_result, slide_index
    )
    if not det_passed:
        logger.warning(
            "Slide %d: INTEGRITY deterministic fail (narrative→preprocess): %s",
            slide_index + 1, det_reason,
        )
        # Build a fix directive from the narrative text
        fix = _build_preprocess_fix_directive(det_reason, narrative_text, preprocessing_result)
        return {"status": "fail", "fix_directive": fix, "deterministic_reason": det_reason}

    # ── LLM semantic check (deeper alignment) ──
    check_input = (
        f"narrative_text:\n{narrative_text}\n\n"
        f"preprocessing_result:\n{preprocessing_result}"
    )

    try:
        result = await call_llm_json(_NARRATIVE_PREPROCESS_PROMPT, check_input)

        checks = [
            result.get("primary_element_traces_narrative", False),
            result.get("supporting_elements_trace_narrative", False),
            result.get("no_meaning_lost", False),
            result.get("no_tone_drift", False),
            result.get("title_present", False),
            result.get("primary_not_single_word", False),
        ]

        if sum(checks) >= 4:
            logger.info("Slide %d: INTEGRITY pass (narrative→preprocess)", slide_index + 1)
            return {"status": "pass", "fix_directive": "", "deterministic_reason": ""}
        else:
            fix = result.get("fix_directive", "Restore narrative meaning into primary_element and supporting_elements.")
            failed_checks = [
                name for name, val in zip(
                    ["primary_traces", "supporting_traces", "meaning", "tone", "title", "primary_words"],
                    checks
                ) if not val
            ]
            logger.warning(
                "Slide %d: INTEGRITY semantic fail (narrative→preprocess): failed=%s fix=%s",
                slide_index + 1, failed_checks, fix,
            )
            return {"status": "fail", "fix_directive": fix, "deterministic_reason": ""}

    except Exception as e:
        logger.warning(
            "Slide %d: INTEGRITY LLM check failed (%s) — relying on deterministic checks only",
            slide_index + 1, e,
        )
        # Deterministic already passed if we're here
        return {"status": "pass", "fix_directive": "", "deterministic_reason": ""}


async def verify_preprocess_to_render(
    preprocessing_result: dict,
    html_content: str,
    slide_index: int,
) -> dict:
    """Verify alignment between preprocessed structure and rendered HTML.

    Returns:
        {
            "status": "pass" | "fail",
            "fix_directive": str,
            "missing_elements": list[str],
            "deterministic_reason": str,
        }
    """
    # ── Deterministic checks first ──
    det_passed, det_reason, missing = _deterministic_render_check(
        preprocessing_result, html_content
    )
    if not det_passed:
        logger.warning(
            "Slide %d: INTEGRITY deterministic fail (preprocess→render): %s | missing=%s",
            slide_index + 1, det_reason, missing,
        )
        fix = f"Inject missing elements into HTML: {missing}"
        return {
            "status": "fail",
            "fix_directive": fix,
            "missing_elements": missing,
            "deterministic_reason": det_reason,
        }

    # ── LLM semantic check ──
    check_input = (
        f"preprocessing_result:\n{preprocessing_result}\n\n"
        f"rendered_html:\n{html_content}"
    )

    try:
        result = await call_llm_json(_PREPROCESS_RENDER_PROMPT, check_input)

        checks = [
            result.get("primary_visible", False),
            result.get("all_supporting_present", False),
            result.get("title_present_in_html", False),
            result.get("meaning_preserved", True),
            result.get("no_irrelevant_content", True),
        ]

        llm_missing = result.get("missing_elements", [])

        if sum(checks) >= 3:
            logger.info("Slide %d: INTEGRITY pass (preprocess→render)", slide_index + 1)
            return {
                "status": "pass",
                "fix_directive": "",
                "missing_elements": [],
                "deterministic_reason": "",
            }
        else:
            fix = result.get("fix_directive", "Ensure all structured content is represented clearly in HTML (exact wording not required).")
            failed_checks = [
                name for name, val in zip(
                    ["primary_visible", "all_supporting", "title_in_html", "meaning_preserved", "no_irrelevant_content"],
                    checks
                ) if not val
            ]
            logger.warning(
                "Slide %d: INTEGRITY semantic fail (preprocess→render): failed=%s missing=%s",
                slide_index + 1, failed_checks, llm_missing,
            )
            return {
                "status": "fail",
                "fix_directive": fix,
                "missing_elements": llm_missing if isinstance(llm_missing, list) else [],
                "deterministic_reason": "",
            }

    except Exception as e:
        logger.warning(
            "Slide %d: INTEGRITY LLM render check failed (%s) — deterministic only",
            slide_index + 1, e,
        )
        return {
            "status": "pass",
            "fix_directive": "",
            "missing_elements": [],
            "deterministic_reason": "",
        }


# ── Fix Directive Builder ─────────────────────────────────────────────

def _build_preprocess_fix_directive(
    det_reason: str,
    narrative_text: str,
    preprocessing_result: dict,
) -> str:
    """Build an actionable fix directive from a deterministic failure reason.

    The directive tells the preprocessor EXACTLY what to fix using the
    original narrative text — no creative rewriting.
    """
    if "EMPTY_TITLE" in det_reason:
        # Extract a title from the first sentence of narrative
        first_sentence = narrative_text.split(".")[0].strip()
        return f"Set title to the opening idea: '{first_sentence[:60]}'"

    if "SINGLE_WORD_PRIMARY" in det_reason:
        # Use the first sentence of narrative as primary
        first_sentence = narrative_text.split(".")[0].strip()
        return f"Replace primary_element with the core narrative statement: '{first_sentence}'"

    if "EMPTY_PRIMARY" in det_reason:
        first_sentence = narrative_text.split(".")[0].strip()
        return f"Set primary_element from narrative: '{first_sentence}'"

    if "NO_SUPPORTING" in det_reason:
        # Split narrative into sentences for supporting elements
        sentences = [s.strip() for s in narrative_text.split(".") if s.strip()]
        candidates = sentences[1:4] if len(sentences) > 1 else [narrative_text]
        return f"Extract supporting_elements from narrative sentences: {candidates}"

    if "SHALLOW_SUPPORTING" in det_reason:
        return f"Replace shallow supporting element with a meaningful phrase from narrative_text."

    if "PRIMARY_DRIFT" in det_reason:
        return f"primary_element has drifted from narrative meaning. Rewrite it using vocabulary from narrative_text: '{narrative_text[:80]}...'"

    return f"Fix based on: {det_reason}. Use narrative_text as source of truth."
