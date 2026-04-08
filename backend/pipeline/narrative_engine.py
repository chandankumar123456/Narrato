import logging
import json
from models.presentation_state import PresentationState
from services.llm_client import call_llm_json

logger = logging.getLogger(__name__)

class NarrativeEngineError(Exception):
    pass

NARRATIVE_ROLES = [
    "Context", "Problem", "Tension", "Insight", "Solution", "Impact", "Closure"
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
TRANSITION_REPAIR_TEXT = (
    "Because the previous limitation creates unresolved pressure, this step becomes necessary."
)
CAUSE_REPAIR_TEXT = (
    "This follows directly from the gap introduced in the previous step."
)
NEXT_TRIGGER_REPAIR_TEXT = (
    "This creates a new constraint that must be addressed immediately."
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
    return any(phrase in text for phrase in WEAK_TRANSITION_PHRASES)


def _is_weak_cause(value: object) -> bool:
    text = _safe_text(value).lower()
    if not text:
        return True
    if len(text.split()) < 5:
        return True
    weak = ("follows previous idea", "continues logic", "step follows")
    return any(phrase in text for phrase in weak)


def _is_weak_next_trigger(value: object) -> bool:
    text = _safe_text(value).lower()
    if not text:
        return True
    if len(text.split()) < 5:
        return True
    weak = ("next step", "leads to next", "then we see")
    return any(phrase in text for phrase in weak)


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
    """Soft-validate and repair arc structure; never raises for weak content."""
    repaired_slides = _normalize_slide_count(slides, target_count)
    required_keys = {
        "intent",
        "role_in_story",
        "key_message",
        "transition_reason",
        "emotional_tone",
        "cause",
        "tension",
        "resolution",
        "next_trigger",
    }

    output: list[dict] = []
    for i, slide in enumerate(repaired_slides):
        if not isinstance(slide, dict):
            slide = {}

        role_default = NARRATIVE_ROLES[min(i * len(NARRATIVE_ROLES) // max(target_count, 1), len(NARRATIVE_ROLES) - 1)]
        base = dict(slide)
        base.setdefault("intent", "general")
        base.setdefault("role_in_story", role_default)
        base.setdefault("key_message", f"Core point {i + 1}")
        base.setdefault("emotional_tone", "neutral")
        base.setdefault("tension", "Pressure accumulates as unresolved constraints persist.")
        base.setdefault("resolution", "")

        if i == 0:
            if not _safe_text(base.get("transition_reason")):
                base["transition_reason"] = "This establishes the opening context for the narrative."
            if not _safe_text(base.get("cause")):
                base["cause"] = "This introduces the initial condition that frames the narrative."
            if _is_weak_next_trigger(base.get("next_trigger")):
                base["next_trigger"] = NEXT_TRIGGER_REPAIR_TEXT
        else:
            if _is_weak_transition(base.get("transition_reason")):
                base["transition_reason"] = TRANSITION_REPAIR_TEXT
            if _is_weak_cause(base.get("cause")):
                base["cause"] = CAUSE_REPAIR_TEXT
            if _is_weak_next_trigger(base.get("next_trigger")):
                base["next_trigger"] = NEXT_TRIGGER_REPAIR_TEXT

        # Ensure all required keys exist and are non-empty (except resolution allowed empty)
        for key in required_keys:
            if key == "resolution":
                base.setdefault(key, "")
                continue
            if key not in base or not _safe_text(base.get(key)):
                if key == "transition_reason":
                    base[key] = TRANSITION_REPAIR_TEXT if i > 0 else "This establishes the opening context for the narrative."
                elif key == "cause":
                    base[key] = CAUSE_REPAIR_TEXT if i > 0 else "This introduces the initial condition that frames the narrative."
                elif key == "next_trigger":
                    base[key] = NEXT_TRIGGER_REPAIR_TEXT
                elif key == "key_message":
                    base[key] = f"Core point {i + 1}"
                elif key == "role_in_story":
                    base[key] = role_default
                elif key == "intent":
                    base[key] = "general"
                elif key == "emotional_tone":
                    base[key] = "neutral"
                elif key == "tension":
                    base[key] = "Pressure accumulates as unresolved constraints persist."

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

    max_retries = 1
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
            
            # Map valid slides to the state
            for slide in valid_slides:
                slide["why_this_slide"] = slide.get("cause", "")
                slide["why_next_slide"] = slide.get("next_trigger", "")
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
            "intent": "general",
            "role_in_story": NARRATIVE_ROLES[role_idx],
            "key_message": f"Core point {i+1} for {state.topic}",
            "transition_reason": "This creates need for next step" if i > 0 else "Start",
            "emotional_tone": "neutral",
            
            "cause": f"This step follows previous idea",
            "tension": f"Increasing importance of step {i+1}",
            "resolution": "",
            "next_trigger": f"This creates need for step {i+2}",
            "why_this_slide": f"This step continues logic",
            "why_next_slide": "This creates need for next step"
        })
    return state.model_copy(update={"narrative_arc": fallback_arc})
