import logging
import json
import re
from models.presentation_state import PresentationState
from services.llm_client import call_llm_json

logger = logging.getLogger(__name__)

class NarrativeEngineError(Exception):
    pass

NARRATIVE_ROLES = [
    "Context", "Problem", "Tension", "Insight", "Solution", "Impact", "Closure"
]
CAUSAL_SLIDE_ROLES = [
    "Problem", "Consequence", "Escalation", "BreakingPoint", "Solution", "Proof", "Scale", "Ask"
]

HIGH_IMPORTANCE_SIGNALS = (
    "problem", "pain", "cost", "loss", "impact", "urgency", "consequence",
    "solution", "differentiation", "unique", "defensible", "advantage",
    "traction", "proof", "metric", "growth", "adoption",
    "revenue", "pricing", "arr", "business model", "monetization",
    "why now", "timing", "window", "regulation", "shift",
)
LOW_IMPORTANCE_SIGNALS = (
    "overview", "definition", "intro", "introduction", "background", "basics", "generic",
)

WEAK_TRANSITION_PHRASES = (
    "next step",
    "leads to next",
    "then we see",
)
GENERIC_CAUSAL_PHRASES = (
    "follows logically",
    "next step",
    "leads to",
    "this creates need",
    "logical continuation",
    "from previous",
    "continues logic",
)

NARRATIVE_ENGINE_SYSTEM_PROMPT = """You are a world-class Narrative Architect specializing in high-impact presentations.

🔥 BUSINESS PRIORITY OVERRIDE (CRITICAL):

This is an INVESTOR presentation.

MANDATORY REQUIREMENTS:
- At least ONE slide MUST explain PRICING (with actual numbers, e.g., $20/month, enterprise tiers)
- At least ONE slide MUST explain REVENUE MODEL or PROJECTIONS (e.g., ARR, growth, scaling)
- At least ONE slide MUST compare against COMPETITORS (e.g., BI tools, dashboards, AI copilots)

These are NON-NEGOTIABLE.
These slides MUST appear even if it slightly reduces narrative elegance.

If any of these are missing → OUTPUT IS INVALID → regenerate internally.

---

🔥 INVESTOR MODE OVERRIDE (CRITICAL):

This is an INVESTOR presentation.

MANDATORY:
- Include at least ONE slide explaining pricing (with numbers)
- Include at least ONE slide explaining revenue model or projections
- Include at least ONE slide comparing against competitors

These are REQUIRED.
If any of these are missing → OUTPUT IS INVALID → regenerate internally.

 ---

Your task is to construct a COMPLETE, CAUSAL, HIGH-TENSION narrative arc.

You must design EXACTLY {{slide_count}} slides.

You must strictly follow this narrative progression:
Context → Problem → Tension → Insight → Solution → Impact → Closure

AND enforce this slide_role progression:
Problem → Consequence → Escalation → BreakingPoint → Solution → Proof → Scale → Ask

You may expand phases across multiple slides, but ORDER MUST NEVER BREAK.

Every narrative MUST include:

- A visible breakdown or failure moment
- A point where current system clearly stops working
- A consequence that makes continuation impossible

If no failure point exists → regenerate internally
Slides must NOT repeat the same core idea.
If two slides express same meaning → merge or differentiate.

---

OUTPUT FORMAT (STRICT JSON ONLY):

{{
  "slides": [
    {{
      "intent": "...",
      "role_in_story": "...",
      "key_message": "...",
      "transition_reason": "...",
      "emotional_tone": "...",
      "slide_role": "...",
      "cause_from_previous": "...",
      "narrative_delta": "...",
      "forward_tension": "...",
      "tension_level": 0,
      "cause": "...",
      "tension": "...",
      "resolution": "...",
      "next_trigger": "..."
    }}
  ]
}}

---

HARD RULES (NON-NEGOTIABLE):

1. ONE IDEA PER SLIDE  
Each slide must express exactly ONE core idea.

---

2. CAUSALITY (STRICT)  
- Each slide MUST exist because of the previous slide  
- "cause" must reference a SPECIFIC outcome or gap from the previous slide  
- No generic phrases like "continuing", "next step"

---

3. FORWARD FORCE (CRITICAL)  
- Each slide MUST FORCE the next slide to exist  
- "next_trigger" must create pressure, curiosity, or unresolved need  
- Weak phrases like "leads to next" are FORBIDDEN

---

4. TENSION CURVE (MANDATORY)  
- Tension must increase from Context → Tension  
- There MUST be a peak tension BEFORE Solution  
- After Solution, tension must resolve progressively  

---

5. FAILURE POINT (MANDATORY)  
- At least one slide MUST explicitly show failure, limitation, or breakdown  
- Without failure → solution is weak → REJECT internally

---

6. TRANSITIONS (STRICT)  
- "transition_reason" must logically connect from previous slide  
- Must be specific, not generic  
- Minimum 6–12 words explaining WHY this slide follows

---

7. NO GENERIC LANGUAGE  
FORBIDDEN:
- "next step"
- "leads to"
- "introduction"
- "overview"
- "basics"

---

8. ROLE CONSISTENCY  
Each slide must clearly belong to one of:
Context, Problem, Tension, Insight, Solution, Impact, Closure

AND must include one slide_role from:
Problem, Consequence, Escalation, BreakingPoint, Solution, Proof, Scale, Ask

No skipping required phases.

---

9. PROGRESSION QUALITY  
Each slide must answer:
→ Why does this exist now?  
→ Why must the next slide exist?

---

10. COMPRESSION  
- key_message must be ≤ 12 words  
- Must be sharp, not descriptive sentences

---

11. FAILURE & CONSEQUENCE (CRITICAL)

- The narrative MUST contain a clear failure or breakdown point before the solution phase.
- This failure must show that the current approach is NOT sustainable.
- It must introduce a real consequence (loss, instability, conflict, or collapse).

If the failure is missing or weak → regenerate internally.

---

12. TENSION ESCALATION (STRICT)

- Each slide must increase pressure until a peak before the solution.
- Flat progression is NOT allowed.

---

13. NO IDEA DUPLICATION

- Each slide must introduce a NEW layer of meaning.

---

14. INEVITABILITY TEST

- Removing any slide should break the flow

---

15. IMPACT INTENSITY

- Failure must feel unavoidable and consequential

---

FAIL CONDITIONS (DO NOT OUTPUT IF PRESENT):
- Missing pricing / revenue / competition
- Weak transitions
- Missing tension
- No failure point
- Repeated ideas

---

FINAL GOAL:

The narrative must feel inevitable AND investor-ready.

Each slide should make the audience think:
"I HAVE to see what comes next."

Return ONLY valid JSON.
"""

# NARRATIVE_ENGINE_SYSTEM_PROMPT = """You are a world-class Narrative Architect specializing in high-impact presentations.

# Your task is to construct a COMPLETE, CAUSAL, HIGH-TENSION narrative arc.

# You must design EXACTLY {{slide_count}} slides.

# You must strictly follow this narrative progression:
# Context → Problem → Tension → Insight → Solution → Impact → Closure

# You may expand phases across multiple slides, but ORDER MUST NEVER BREAK.

# Every narrative MUST include:

# - A visible breakdown or failure moment
# - A point where current system clearly stops working
# - A consequence that makes continuation impossible

# If no failure point exists → regenerate internally
# Slides must NOT repeat the same core idea.
# If two slides express same meaning → merge or differentiate.

# ---

# OUTPUT FORMAT (STRICT JSON ONLY):

# {{
#   "slides": [
#     {{
#       "intent": "...",
#       "role_in_story": "...",
#       "key_message": "...",
#       "transition_reason": "...",
#       "emotional_tone": "...",
#       "cause": "...",
#       "tension": "...",
#       "resolution": "...",
#       "next_trigger": "..."
#     }}
#   ]
# }}

# ---

# HARD RULES (NON-NEGOTIABLE):

# 1. ONE IDEA PER SLIDE  
# Each slide must express exactly ONE core idea.

# ---

# 2. CAUSALITY (STRICT)  
# - Each slide MUST exist because of the previous slide  
# - "cause" must reference a SPECIFIC outcome or gap from the previous slide  
# - No generic phrases like "continuing", "next step"

# ---

# 3. FORWARD FORCE (CRITICAL)  
# - Each slide MUST FORCE the next slide to exist  
# - "next_trigger" must create pressure, curiosity, or unresolved need  
# - Weak phrases like "leads to next" are FORBIDDEN

# ---

# 4. TENSION CURVE (MANDATORY)  
# - Tension must increase from Context → Tension  
# - There MUST be a peak tension BEFORE Solution  
# - After Solution, tension must resolve progressively  

# ---

# 5. FAILURE POINT (MANDATORY)  
# - At least one slide MUST explicitly show failure, limitation, or breakdown  
# - Without failure → solution is weak → REJECT internally

# ---

# 6. TRANSITIONS (STRICT)  
# - "transition_reason" must logically connect from previous slide  
# - Must be specific, not generic  
# - Minimum 6–12 words explaining WHY this slide follows

# ---

# 7. NO GENERIC LANGUAGE  
# FORBIDDEN:
# - "next step"
# - "leads to"
# - "introduction"
# - "overview"
# - "basics"

# ---

# 8. ROLE CONSISTENCY  
# Each slide must clearly belong to one of:
# Context, Problem, Tension, Insight, Solution, Impact, Closure

# No skipping required phases.

# ---

# 9. PROGRESSION QUALITY  
# Each slide must answer:
# → Why does this exist now?  
# → Why must the next slide exist?

# ---

# 10. COMPRESSION  
# - key_message must be ≤ 12 words  
# - Must be sharp, not descriptive sentences

# ---

# 11. FAILURE & CONSEQUENCE (CRITICAL)

# - The narrative MUST contain a clear failure or breakdown point before the solution phase.
# - This failure must show that the current approach is NOT sustainable.
# - It must introduce a real consequence (loss, instability, conflict, or collapse).

# Examples of valid failure:
# - System instability becomes unavoidable
# - Tradeoffs accumulate beyond control
# - Local optimization leads to irreversible damage

# If the failure is missing or weak → regenerate internally.

# ---

# 12. TENSION ESCALATION (STRICT)

# - Each slide must increase pressure until a peak before the solution.
# - Pressure can be:
#   - conflict
#   - inefficiency
#   - hidden cost
#   - instability
#   - risk accumulation

# Flat progression is NOT allowed.

# ---

# 13. NO IDEA DUPLICATION

# - No two slides should express the same core idea.
# - If overlap exists → differentiate or remove redundancy.
# - Each slide must introduce a NEW layer of meaning.

# ---

# 14. INEVITABILITY TEST

# After constructing the narrative, verify:

# - Removing any slide should break the flow
# - Each slide must feel necessary, not optional

# If not → regenerate internally

#  ---

# 15. IMPACT INTENSITY

# - Failure must feel unavoidable and consequential
# - Use language that implies loss, instability, or breakdown
# - Avoid neutral phrasing

# Example:
# ❌ "system becomes unstable"
# ✅ "system begins to fail faster than it can recover"

# If failure feels neutral → regenerate internally

#  ---

# FAIL CONDITIONS (DO NOT OUTPUT IF PRESENT):
# - Weak transitions
# - Missing tension
# - No failure point
# - Repeated ideas
# - Generic phrases

# If any fail condition occurs → internally regenerate before output.

# ---

# FINAL GOAL:

# The narrative must feel inevitable.

# Each slide should make the audience think:
# "I HAVE to see what comes next."

# Return ONLY valid JSON.
# """

def _safe_text(value: object) -> str:
    return str(value or "").strip()


def _is_weak_transition(value: object) -> bool:
    text = _safe_text(value).lower()
    if not text:
        return True
    if len(text.split()) < 5:
        return True
    if any(phrase in text for phrase in WEAK_TRANSITION_PHRASES):
        return True
    return any(phrase in text for phrase in GENERIC_CAUSAL_PHRASES)


def _is_weak_cause(value: object) -> bool:
    text = _safe_text(value).lower()
    if not text:
        return True
    if len(text.split()) < 5:
        return True
    return any(phrase in text for phrase in GENERIC_CAUSAL_PHRASES)


def _is_weak_next_trigger(value: object) -> bool:
    text = _safe_text(value).lower()
    if not text:
        return True
    if len(text.split()) < 5:
        return True
    return any(phrase in text for phrase in GENERIC_CAUSAL_PHRASES)


def _extract_tokens(value: object) -> list[str]:
    return [
        token for token in re.findall(r"[a-z0-9]+", _safe_text(value).lower())
        if len(token) >= 4
    ]


def _cause_references_previous_message(cause_text: object, previous_key_message: object) -> bool:
    prev_tokens = _extract_tokens(previous_key_message)
    if not prev_tokens:
        return False
    cause_tokens = set(_extract_tokens(cause_text))
    return any(token in cause_tokens for token in prev_tokens)


def _find_weak_causal_slide_indices(slides: list[dict]) -> list[int]:
    invalid: list[int] = []
    for idx, slide in enumerate(slides or []):
        cause_text = slide.get("cause_from_previous")
        delta_text = slide.get("narrative_delta")
        pressure_text = slide.get("forward_tension")
        transition_text = slide.get("transition_reason")
        if (
            _is_weak_cause(cause_text)
            or _is_weak_transition(delta_text)
            or _is_weak_next_trigger(pressure_text)
            or _is_weak_transition(transition_text)
        ):
            invalid.append(idx)
            continue
        if idx > 0:
            previous_key = (slides[idx - 1] or {}).get("key_message")
            if not _cause_references_previous_message(cause_text, previous_key):
                invalid.append(idx)
    return invalid


def _normalize_slide_role(role: object, idx: int, target_count: int) -> str:
    role_text = _safe_text(role)
    if role_text in CAUSAL_SLIDE_ROLES:
        return role_text
    if target_count <= 0:
        return CAUSAL_SLIDE_ROLES[min(idx, len(CAUSAL_SLIDE_ROLES) - 1)]
    mapped_idx = min(
        idx * len(CAUSAL_SLIDE_ROLES) // max(target_count, 1),
        len(CAUSAL_SLIDE_ROLES) - 1
    )
    return CAUSAL_SLIDE_ROLES[mapped_idx]


def _default_tension_level(idx: int, target_count: int) -> int:
    if target_count <= 1:
        return 5
    solution_idx = max(1, min(target_count - 1, target_count // 2))
    if idx <= solution_idx:
        ramp = int(round((idx / max(solution_idx, 1)) * 9))
        return max(2, min(9, ramp))
    tail_span = max(1, target_count - 1 - solution_idx)
    tail = int(round(((target_count - 1 - idx) / tail_span) * 6))
    return max(1, min(6, tail))


def _normalize_slide_count(slides: list, target_count: int) -> list:
    normalized = list(slides or [])
    if not normalized and target_count > 0:
        normalized = [{}]

    if len(normalized) < target_count:
        logger.warning(
            "[narrative_engine] Arc shorter than requested (%d/%d); padding softly",
            len(normalized), target_count,
        )
        while len(normalized) < target_count:
            normalized.append(dict(normalized[-1]) if isinstance(normalized[-1], dict) else {})
    elif len(normalized) > target_count:
        logger.warning(
            "[narrative_engine] Arc longer than requested (%d/%d); trimming softly",
            len(normalized), target_count,
        )
        normalized = normalized[:target_count]
    return normalized


def validate_narrative_arc(slides: list, target_count: int) -> list:
    """Normalize arc structure only; do not repair weak causal content."""
    normalized_slides = _normalize_slide_count(slides, target_count)
    required_keys = {
        "intent",
        "role_in_story",
        "slide_role",
        "key_message",
        "transition_reason",
        "emotional_tone",
        "cause_from_previous",
        "narrative_delta",
        "forward_tension",
        "tension_level",
        "cause",
        "tension",
        "resolution",
        "next_trigger",
    }

    output: list[dict] = []
    for i, slide in enumerate(normalized_slides):
        if not isinstance(slide, dict):
            slide = {}

        role_default = NARRATIVE_ROLES[min(i * len(NARRATIVE_ROLES) // max(target_count, 1), len(NARRATIVE_ROLES) - 1)]
        base = dict(slide)
        base.setdefault("intent", "")
        base.setdefault("role_in_story", role_default)
        base.setdefault("slide_role", _normalize_slide_role(base.get("slide_role"), i, target_count))
        base.setdefault("key_message", "")
        base.setdefault("emotional_tone", "")
        base.setdefault("tension", "")
        base.setdefault("resolution", "")
        base.setdefault("cause_from_previous", "")
        base.setdefault("narrative_delta", "")
        base.setdefault("forward_tension", "")
        base.setdefault("tension_level", _default_tension_level(i, target_count))

        base["role_in_story"] = _safe_text(base.get("role_in_story")) or role_default
        base["slide_role"] = _normalize_slide_role(base.get("slide_role"), i, target_count)

        try:
            base["tension_level"] = max(0, min(10, int(base.get("tension_level"))))
        except Exception:
            base["tension_level"] = _default_tension_level(i, target_count)

        base["cause"] = _safe_text(base.get("cause_from_previous"))
        base["next_trigger"] = _safe_text(base.get("forward_tension"))
        base["tension"] = _safe_text(base.get("tension")) or _safe_text(base.get("forward_tension"))

        # Ensure all required keys exist and are non-empty (except resolution allowed empty)
        for key in required_keys:
            if key == "resolution":
                base.setdefault(key, "")
                continue
            if key not in base or not _safe_text(base.get(key)):
                if key == "tension_level":
                    base[key] = _default_tension_level(i, target_count)
                elif key == "role_in_story":
                    base[key] = role_default
                elif key == "slide_role":
                    base[key] = _normalize_slide_role(base.get("slide_role"), i, target_count)
                else:
                    base[key] = ""

        output.append(base)

    return output


def _score_slide_importance(slide: dict) -> str:
    text = " ".join(
        [
            str(slide.get("intent", "")),
            str(slide.get("role_in_story", "")),
            str(slide.get("key_message", "")),
            str(slide.get("transition_reason", "")),
        ]
    ).lower()
    if any(token in text for token in HIGH_IMPORTANCE_SIGNALS):
        return "high"
    if any(token in text for token in LOW_IMPORTANCE_SIGNALS):
        return "low"
    return "low"


def _has_high_impact_slide(slides: list[dict]) -> bool:
    for slide in slides:
        text = " ".join(
            [
                str(slide.get("role_in_story", "")),
                str(slide.get("key_message", "")),
                str(slide.get("intent", "")),
            ]
        ).lower()
        if "why now" in text or "why this wins" in text:
            return True
    return False


def _inject_high_impact_slide(slides: list[dict]) -> list[dict]:
    if not slides:
        return slides

    target_idx = len(slides) - 1
    for idx, slide in enumerate(slides):
        role = str(slide.get("role_in_story", "")).lower()
        if "funding ask" in role or "closure" in role or "impact" in role:
            target_idx = idx

    high_impact = {
        "intent": "why_now",
        "role_in_story": "Why now",
        "key_message": "Why this wins now: delay forfeits market leadership",
        "transition_reason": "Market conditions and buyer behavior now favor decisive adoption",
        "emotional_tone": "assertive",
        "cause": "Incumbent workflows are failing while demand and urgency are compounding",
        "tension": "Every delayed quarter increases switching costs and cedes strategic ground",
        "resolution": "Adopt now to capture category advantage before the window narrows",
        "next_trigger": "Immediate execution converts urgency into measurable market control",
        "importance": "high",
    }
    slides[target_idx] = {**slides[target_idx], **high_impact}
    return slides


def _apply_investor_importance_weighting(slides: list[dict]) -> list[dict]:
    weighted: list[dict] = []
    for slide in slides:
        weighted.append({**slide, "importance": _score_slide_importance(slide)})
    return weighted


async def regenerate_invalid_narrative_slides(
    state: PresentationState,
    narrative_arc: list[dict],
    invalid_indices: list[int],
    business_context: dict | None = None,
) -> list[dict]:
    if not invalid_indices:
        return narrative_arc

    arc_json = json.dumps(narrative_arc, indent=2)
    one_based = [idx + 1 for idx in invalid_indices]
    system_prompt = (
        "You rewrite only invalid slides in a narrative arc. "
        "Return strict JSON with key 'slides' as an array of objects: "
        "{slide_index, intent, role_in_story, key_message, transition_reason, emotional_tone, "
        "slide_role, cause_from_previous, narrative_delta, forward_tension, tension_level}. "
        "Each rewritten slide must avoid generic phrases and must be causally specific."
    )
    user_prompt = f"""
Topic: {state.topic}
Audience: {state.audience}
Tone: {state.tone}
Invalid slide indices (1-based): {one_based}

Current arc:
{arc_json}

Rules:
- Rewrite ONLY the invalid slides.
- cause_from_previous must reference previous slide key_message terms.
- narrative_delta and forward_tension must be specific and non-generic.
- transition_reason must be specific and non-generic.
- Do not add placeholders like "follows logically", "next step", "leads to", "this creates need".

Return JSON only.
"""
    try:
        result = await call_llm_json(system_prompt, user_prompt)
        rewrites = result.get("slides", [])
        updated_arc = [dict(s) if isinstance(s, dict) else {} for s in (narrative_arc or [])]
        rewrite_by_index = {}
        for item in rewrites:
            try:
                idx = int(item.get("slide_index")) - 1
            except Exception:
                continue
            if idx in invalid_indices:
                rewrite_by_index[idx] = dict(item)
        for idx in invalid_indices:
            patch = rewrite_by_index.get(idx, {})
            if patch:
                updated_arc[idx] = {**updated_arc[idx], **patch}
        return updated_arc
    except Exception as exc:
        logger.warning("[narrative_engine] Failed to regenerate invalid slides: %s", exc)
        return narrative_arc


async def run_narrative_engine(state: PresentationState, business_context: dict = None) -> PresentationState:
    """Generate the presentation's narrative arc mapping out slide intents."""
    logger.info(f"[narrative_engine] Building story arc for {state.slide_count} slides...")

    business_text = ""

    if business_context:
        business_text = f"""

    IMPORTANT: This is NOT a generic presentation.
    This is a STARTUP / PRODUCT narrative.

    PRODUCT DETAILS:

    Product Name: {business_context['product_name']}
    Product Type: {business_context['product_type']}
    Target User: {business_context['target_user']}

    Core Problem:
    {business_context['problem']}

    Solution:
    {business_context['solution']}

    Key Features:
    {business_context['key_features']}

    Market Context:
    {business_context['market']}

    Business Model:
    {business_context['monetization']}

    Differentiation:
    {business_context['differentiation']}

    MANDATE:
    - Narrative MUST revolve around THIS PRODUCT
    - Problem must match THIS problem
    - Solution must match THIS solution
    - Do NOT generate abstract/system-level philosophy
    """

    system_prompt = NARRATIVE_ENGINE_SYSTEM_PROMPT.format(slide_count=state.slide_count)
    context = (state.metadata or {}).get("context", {}) if isinstance(state.metadata, dict) else {}
    deck_goal = str(context.get("deck_goal", "")).strip()
    context_audience = str(context.get("audience", "")).strip()
    context_tone = str(context.get("tone", "")).strip()
    context_topic = str(context.get("topic", "")).strip()

    user_prompt = f"""
        {business_text}

        Topic: {state.topic}
        Type: {state.presentation_type}
        Audience: {state.audience}
        Tone: {state.tone}

        You are building a PRODUCT / STARTUP narrative.

        STRICT REQUIREMENTS:
        - The story MUST be about the product defined above
        - Problem must reflect real user pain (not abstract)
        - Solution must introduce the product clearly
        - Include market and business implications in later slides
        - Include a slide explaining pricing model
        - Include a slide explaining revenue potential or projections
        - Include a slide comparing against competitors

        Remember:
        Design exactly {state.slide_count} slides following:
        Context → Problem → Tension → Insight → Solution → Impact → Closure

        Output strictly JSON.

        ---

        You are generating a structured presentation narrative.

        CONTEXT:

        * Goal: {deck_goal}
        * Audience: {context_audience}
        * Tone: {context_tone}
        * Topic: {context_topic}

        ---

        STRUCTURE RULES:

        * Each section MUST naturally lead to the next
        * Do NOT jump randomly between topics
        * Do NOT mix multiple sections in one part
        * Maintain consistent tone across all sections
        * Avoid repetition

        ---

        SLIDE-AWARE GENERATION:

        For EACH section, ensure:

        * One clear primary idea (this becomes primary_element)
        * 2–3 supporting ideas (this becomes supporting_elements)

        DO NOT generate vague paragraphs.

        Generate content that can be easily split into slides.

        ---

        TRANSITION RULE:

        Each section must implicitly answer:

        "Why does the next section follow from this one?"

        Ensure logical progression, not just topic listing.

        ---

        NARRATIVE DISCIPLINE REQUIREMENTS (MANDATORY):

        1. EARLY PRODUCT ANCHORING
        * The product MUST be clearly introduced immediately after the problem.
        * Do NOT delay product explanation to later slides.
        * The audience must understand what is being built early.

        2. FORWARD-ONLY FLOW (STRICT)
        * Once a concept is introduced, DO NOT return to it again.
        * Do NOT reintroduce the problem after moving to solution.
        * Do NOT jump backward in narrative.
        * The story must move strictly forward.

        3. NO REPETITION
        * Each slide must introduce NEW information.
        * Do NOT repeat the same idea using different wording.
        * If two slides express similar meaning → differentiate them clearly.

        4. NO META CONTENT
        FORBIDDEN:
        * Slides about “product must be defined”
        * Slides about “market must be defined”
        * Slides that discuss how to build the pitch itself
        All slides must be actual content, not commentary.

        5. PRODUCT CLARITY (MANDATORY)
        * Clearly define:
          * what the product is
          * what it does
          * how it solves the problem
        * Avoid abstract descriptions like “ecosystem” without grounding.

        6. CONTINUOUS STORY FLOW
        Each slide must:
        * logically follow from previous slide
        * naturally lead to the next slide
        * feel like part of one continuous argument

        7. INVESTOR READINESS
        Ensure the narrative clearly contains:
        * problem
        * impact
        * solution
        * product clarity
        * revenue model
        * competition
        * market
        * projection
        * funding ask
        These must appear naturally in flow (not randomly).

        ---

        OUTPUT REQUIREMENT:

        * Generate a full narrative that follows the sequence above
        * Ensure it can be cleanly divided into slides
        * Ensure progression is logical and smooth
    """

    max_retries = 2
    for attempt in range(max_retries):
        try:
            result = await call_llm_json(system_prompt, user_prompt)
            slides = result.get("slides", [])

            # ✅ FIX: auto-correct slide count
            if len(slides) < state.slide_count:
                if not slides:
                    slides = [{}]
                while len(slides) < state.slide_count:
                    slides.append(slides[-1])

            elif len(slides) > state.slide_count:
                slides = slides[:state.slide_count]

            valid_slides = validate_narrative_arc(slides, state.slide_count)
            weak_indices = _find_weak_causal_slide_indices(valid_slides)
            if weak_indices and attempt < max_retries - 1:
                logger.warning(
                    "[narrative_engine] Weak causal fields in slides %s, regenerating full narrative once",
                    ",".join(str(i + 1) for i in weak_indices),
                )
                continue
            
            # Map valid slides to the state
            for slide in valid_slides:
                slide["why_this_slide"] = slide.get("cause_from_previous", "")
                slide["why_next_slide"] = slide.get("forward_tension", "")
            from pipeline.investor_enforcer import enforce_investor_structure

            # 🔥 enforce investor completeness + emphasis controls
            if state.presentation_mode == "investor":
                valid_slides = enforce_investor_structure(valid_slides)
                valid_slides = _apply_investor_importance_weighting(valid_slides)
                if not _has_high_impact_slide(valid_slides):
                    valid_slides = _inject_high_impact_slide(valid_slides)

            return state.model_copy(update={"narrative_arc": valid_slides})
            
        except NarrativeEngineError as e:
            logger.warning(f"[narrative_engine] Validation failed on attempt {attempt+1}: {e}")
        except Exception as e:
            logger.error(f"[narrative_engine] LLM generation failed: {e}")

    # Fallback if engine fails completely
    logger.error("[narrative_engine] Failed to generate a valid narrative arc. Falling back to simple linear arc.")
    fallback_arc = []
    for i in range(state.slide_count):
        role_idx = min(i * len(NARRATIVE_ROLES) // state.slide_count, len(NARRATIVE_ROLES) - 1)
        fallback_arc.append({
            "intent": "",
            "role_in_story": NARRATIVE_ROLES[role_idx],
            "key_message": f"Core point {i+1} for {state.topic}",
            "transition_reason": "",
            "emotional_tone": "",
            
            "slide_role": _normalize_slide_role("", i, state.slide_count),
            "cause_from_previous": "",
            "narrative_delta": "",
            "forward_tension": "",
            "tension_level": _default_tension_level(i, state.slide_count),
            "cause": "",
            "tension": "",
            "resolution": "",
            "next_trigger": "",
            "why_this_slide": "",
            "why_next_slide": ""
        })
    return state.model_copy(update={"narrative_arc": fallback_arc})
