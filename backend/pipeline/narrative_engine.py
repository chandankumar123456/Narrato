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

WEAK_MARKERS = {"", "derived", "basic", "from previous", "logical continuation", "next step"}

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

def validate_narrative_arc(slides: list, target_count: int) -> list:
    """Validate the strict rules of the narrative arc."""
    if len(slides) != target_count:
        logger.warning(f"Narrative arc mismatch: expected {target_count} slides, got {len(slides)}")
        # If length mismatches, we can pad or truncate, or raise to retry. For robustness, let LLM decide or just enforce it.
        # But failing hard means we might retry. Let's return False to retry at the caller level.
        raise NarrativeEngineError("Slide count mismatch")

    roles_seen = []
    for i, slide in enumerate(slides):
        required_keys = {
    "intent",
    "role_in_story",
    "key_message",
    "transition_reason",
    "emotional_tone",
    "cause",
    "tension",
    "resolution",
    "next_trigger"
}
        if not required_keys.issubset(set(slide.keys())):
            raise NarrativeEngineError(f"Slide {i+1} is missing required keys.")
        roles_seen.append(slide.get("role_in_story", ""))

        # Check for meaningful transitions
        transition = slide.get("transition_reason", "")
        if i > 0 and (
            len(str(transition).split()) < 5 or
            "next" in transition.lower()
        ):
            # Reject weak reasoning or missing transitions
            raise NarrativeEngineError(f"Slide {i+1} has weak or missing transition reasoning: '{transition}'")

    # Justify ordering
    role_order_map = {r: i for i, r in enumerate(NARRATIVE_ROLES)}
    last_role_idx = -1
    for i, role in enumerate(roles_seen):
        if role in role_order_map:
            current_idx = role_order_map[role]
            if current_idx < last_role_idx:
                raise NarrativeEngineError(f"Narrative flow went backward at Slide {i+1}: from {NARRATIVE_ROLES[last_role_idx]} to {role}")
            last_role_idx = current_idx
            
    return slides


def _is_weak(value: str) -> bool:
    normalized = str(value or "").strip().lower()
    return normalized in WEAK_MARKERS or len(normalized.split()) < 4


def _phase_tension(idx: int, total: int, role: str) -> str:
    if idx == 0:
        return "Low tension: context is introduced with early stakes"
    role_l = str(role or "").lower()
    if "solution" in role_l or "product" in role_l:
        return "Resolution starts: pressure shifts into actionable clarity"
    if "impact" in role_l or "financial" in role_l:
        return "Resolution deepens: outcomes validate the prior risk"
    if "closure" in role_l or "funding ask" in role_l:
        return "Resolved close: tension converts into a decisive next step"

    midpoint = max(1, total // 2)
    if idx < midpoint:
        return "Rising tension: constraints are compounding and urgency increases"
    if idx == midpoint:
        return "Peak tension: continuation without change becomes untenable"
    return "Controlled descent: pressure remains but is now being resolved"


def _repair_narrative_fields(slides: list[dict], topic: str) -> list[dict]:
    repaired: list[dict] = []
    total = len(slides)
    for i, original in enumerate(slides):
        slide = dict(original)
        previous = repaired[i - 1] if i > 0 else None
        prev_message = (previous or {}).get("key_message", f"Slide {i}")

        if _is_weak(slide.get("key_message")):
            role = slide.get("role_in_story", "Context")
            slide["key_message"] = f"{role} focus for {topic}".strip()

        if i > 0:
            cause = str(slide.get("cause", "")).strip()
            if _is_weak(cause) or prev_message.lower() not in cause.lower():
                slide["cause"] = f"Because '{prev_message}' exposes a gap, this slide is required now"
        elif _is_weak(slide.get("cause")):
            slide["cause"] = "This opens the narrative baseline that all later slides depend on"

        if _is_weak(slide.get("next_trigger")):
            next_role = slides[i + 1].get("role_in_story", "next phase") if i + 1 < total else "decision"
            slide["next_trigger"] = f"This unresolved pressure now forces the {next_role} slide"

        slide["tension"] = _phase_tension(i, total, slide.get("role_in_story", ""))

        # Inevitability reinforcement for weak transition chains
        transition_reason = str(slide.get("transition_reason", "")).strip()
        if i > 0 and (_is_weak(transition_reason) or prev_message.lower() not in transition_reason.lower()):
            slide["transition_reason"] = f"'{prev_message}' creates a concrete constraint this slide must resolve next"

        slide["why_this_slide"] = slide.get("cause", "")
        slide["why_next_slide"] = slide.get("next_trigger", "")
        repaired.append(slide)
    return repaired


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
    """

    max_retries = 2
    for attempt in range(max_retries):
        try:
            result = await call_llm_json(system_prompt, user_prompt)
            slides = result.get("slides", [])

            # ✅ FIX: auto-correct slide count
            if len(slides) < state.slide_count:
                # duplicate last slide structure to fill
                while len(slides) < state.slide_count:
                    slides.append(slides[-1])

            elif len(slides) > state.slide_count:
                slides = slides[:state.slide_count]

            valid_slides = validate_narrative_arc(slides, state.slide_count)
            valid_slides = _repair_narrative_fields(valid_slides, state.topic)
            
            # Map valid slides to the state
            for slide in valid_slides:
                slide["why_this_slide"] = slide.get("cause", "")
                slide["why_next_slide"] = slide.get("next_trigger", "")
            from pipeline.investor_enforcer import enforce_investor_structure

            # 🔥 enforce investor completeness and deterministic count
            valid_slides = enforce_investor_structure(valid_slides, target_count=state.slide_count)

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
    from pipeline.investor_enforcer import enforce_investor_structure
    fallback_arc = _repair_narrative_fields(fallback_arc, state.topic)
    fallback_arc = enforce_investor_structure(fallback_arc, target_count=state.slide_count)
    return state.model_copy(update={"narrative_arc": fallback_arc})
