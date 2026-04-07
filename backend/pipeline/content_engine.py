import logging
import json
from models.presentation_state import PresentationState
from services.llm_client import call_llm_json

logger = logging.getLogger(__name__)
MAX_SUPPORTING_ELEMENTS = 4
MAX_WORDS_PER_BULLET = 12

CONTENT_ENGINE_SYSTEM_PROMPT = """You are a Presentation Meaning Structurer.

Return STRICT JSON.

FORMAT:
{
  "structured_slides": [
    {
      "slide_id": 1,
      "intent": "...",
      "primary_element": "...",
      "supporting_elements": ["...", "..."]
    }
  ]
}

RULES:
- Each slide MUST have:
    - 1 strong primary_element
    - 2–4 supporting_elements
- Each element under 12 words
- No paragraphs
- DO NOT use title/points
"""

def extract_role_behavior(role: str) -> str:
    behaviors = {
        "Context": "scopive, baseline, minimal",
        "Hook": "minimal, bold, dominant",
        "Problem": "heavy, contrast",
        "Tension": "fragmented",
        "Insight": "reveal",
        "Solution": "structured clarity, organized",
        "Impact": "stat",
        "Closure": "bold, centered"
    }
    return behaviors.get(role, "minimal, balanced")


def _truncate_words(text: str, max_words: int) -> str:
    words = str(text or "").strip().split()
    return " ".join(words[:max_words]).strip()


def _normalize_supporting_elements(raw_elements, topic: str) -> list[str]:
    fixed: list[str] = []
    for raw in raw_elements or []:
        sentence = str(raw or "").replace("\n", " ").strip()
        if not sentence:
            continue
        sentence = sentence.split(".")[0].strip()
        sentence = _truncate_words(sentence, MAX_WORDS_PER_BULLET)
        if len(sentence.split()) < 3:
            sentence = _truncate_words(
                f"{sentence} for {topic} execution clarity",
                MAX_WORDS_PER_BULLET,
            )
        fixed.append(sentence)
        if len(fixed) >= MAX_SUPPORTING_ELEMENTS:
            break
    return fixed


def _repair_slide_count(structured_slides: list[dict], narrative_arc: list[dict], expected: int, topic: str) -> list[dict]:
    slides = list(structured_slides or [])
    if len(slides) > expected:
        return slides[:expected]

    while len(slides) < expected:
        i = len(slides)
        arc = narrative_arc[i] if i < len(narrative_arc) else {}
        if slides:
            source = dict(slides[-1])
            source["slide_id"] = i + 1
            source["primary_element"] = arc.get("key_message") or source.get("primary_element") or f"{topic} key point {i+1}"
            source["supporting_elements"] = _normalize_supporting_elements(
                arc.get("supporting_elements") or source.get("supporting_elements") or [f"Critical evidence for {topic}"],
                topic,
            )[:MAX_SUPPORTING_ELEMENTS]
            slides.append(source)
        else:
            slides.append({
                "slide_id": i + 1,
                "intent": arc.get("intent", "content"),
                "primary_element": _truncate_words(arc.get("key_message", f"{topic} core message"), MAX_WORDS_PER_BULLET),
                "supporting_elements": [f"Core investor insight for {topic}"],
            })
    return slides


async def run_content_engine(state: PresentationState) -> PresentationState:
    """Generate slide content (works for both narrative + structured pipelines)."""

    # ✅ FIX: Remove hard dependency on narrative_arc
    if not state.narrative_arc:
        logger.warning("[content_engine] No narrative_arc found — generating from slide_plan")

        state.narrative_arc = []
        for slide in (state.slide_plan or []):
            state.narrative_arc.append({
    "intent": slide.get("purpose", ""),
    "role_in_story": slide.get("section", "Context"),
    "key_message": slide.get("purpose", ""),
    "cause": f"Follows logically from previous slide intent",
    "tension": f"Expands the narrative progression",
    "resolution": "",
    "next_trigger": "Leads to next structured step",
    "emotional_tone": "neutral"
})

    logger.info(f"[content_engine] Generating slide content for {len(state.narrative_arc)} slides")

    # ✅ Use arc only if narrative mode
    if getattr(state, "deck_mode", "general") == "investor":
        arc_json = "Use structured sections (problem, solution, market, etc.)"
    else:
        arc_json = json.dumps(state.narrative_arc, indent=2)

    user_prompt = f"""Topic: {state.topic}
Type: {state.presentation_type}
Deck Mode: {getattr(state, "deck_mode", "general")}
Audience: {state.audience}

Here is the structure:
{arc_json}

Generate EXACTLY {len(state.narrative_arc)} slides.
Each slide must map 1:1.

Return structured_slides with same length.
"""

    try:
        result = await call_llm_json(CONTENT_ENGINE_SYSTEM_PROMPT, user_prompt)
        structured_slides = result.get("structured_slides", [])

        # ✅ FIX: HARD fallback if model fails
        if not structured_slides:
            logger.warning("[content_engine] Empty response — using fallback content")

            structured_slides = []
            for i, arc in enumerate(state.narrative_arc):
                structured_slides.append({
                    "slide_id": i + 1,
                    "intent": arc.get("intent", ""),
                    "primary_element": arc.get("key_message", "Slide"),
                    "supporting_elements": ["Content unavailable"]
                })

        expected_slide_count = state.slide_count or len(state.narrative_arc)
        structured_slides = _repair_slide_count(
            structured_slides,
            state.narrative_arc or [],
            expected_slide_count,
            state.topic,
        )

        # ✅ Ensure proper structure for ALL slides
        for i, slide in enumerate(structured_slides):
            
            arc_slide = state.narrative_arc[i] if i < len(state.narrative_arc) else {}

            role = arc_slide.get("role_in_story", "Context")
            behavior = extract_role_behavior(role)
            original_intent = arc_slide.get("intent", "")
            emotional_tone = arc_slide.get("emotional_tone", "neutral")

            slide["intent"] = original_intent
            slide["role_in_story"] = role
            slide["role"] = role
            slide["emotional_tone"] = emotional_tone
            slide["type"] = "content_slide"
            slide["slide_id"] = i + 1
            slide["why_this_slide"] = arc_slide.get("cause", "")
            slide["why_next_slide"] = arc_slide.get("next_trigger", "")
            slide["cause"] = arc_slide.get("cause", "")
            slide["next_trigger"] = arc_slide.get("next_trigger", "")
            slide["tension"] = arc_slide.get("tension", "")
            slide["resolution"] = arc_slide.get("resolution", "")
            slide["primary_element"] = _truncate_words(
                slide.get("primary_element") or arc_slide.get("key_message", "Core message"),
                MAX_WORDS_PER_BULLET,
            )

            # ✅ FIX: enforce supporting_elements length
            slide["supporting_elements"] = _normalize_supporting_elements(
                slide.get("supporting_elements", []),
                state.topic,
            )
            if i > 0 and not slide["supporting_elements"]:
                slide["supporting_elements"] = [
                    _truncate_words(f"Operational proof point for {state.topic}", MAX_WORDS_PER_BULLET)
                ]

        # rebuild slide_plan
        slide_plan = []
        for i, slide in enumerate(structured_slides):
            arc = state.narrative_arc[i] if i < len(state.narrative_arc) else {}

            slide_plan.append({
                "slide_id": slide.get("slide_id", i+1),
                "section": arc.get("role_in_story", "general").lower(),
                "purpose": arc.get("key_message", "Slide point"),
                "type": "content_slide"
            })

        return state.model_copy(update={
            "structured_slides": structured_slides,
            "slide_plan": slide_plan
        })

    except Exception as e:
        logger.error(f"[content_engine] Content generation failed: {e}")
        raise e
