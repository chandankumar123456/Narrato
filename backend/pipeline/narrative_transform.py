"""Narrative Transformation Layer — understand → interpret → express.

Sits BEFORE the content preprocessor in the dynamic composition pipeline.
Transforms raw slide content from shallow data/facts into meaningful,
story-driven expression.  The preprocessor then structures this richer text.

Pipeline position:
    RAW CONTENT
        ↓
    Narrative Transformation  ← THIS MODULE
        ↓
    Preprocess (structure)
        ↓
    Visual Plan
        ↓
    Render

NO structural formatting here — only semantic enrichment.
"""

import logging
from services.llm_client import call_llm_json

logger = logging.getLogger(__name__)


# ── System Prompt ─────────────────────────────────────────────────────

NARRATIVE_TRANSFORM_PROMPT = """\
You are a **Narrative Transformation Engine**.

Your job is to convert raw slide content into **meaningful, story-driven expression** BEFORE it gets structured for visual layout.

---

# INPUT

You receive:

* raw content (the original text, bullet points, or data for one slide)
* slide position (1, 2, 3…)
* total slides in the presentation
* overall topic
* narrative role of this slide (hook, context, problem, etc.)
* emotional tone

---

# OBJECTIVE

Transform content so that it:

* explains WHY it matters
* preserves full meaning — never drop facts, numbers, or entities
* adds clarity and depth through causal reasoning
* avoids generic or shallow phrasing
* feels like part of a cohesive story, not an isolated bullet

---

# RULES

1. DO NOT summarize into keywords or short phrases
2. DO NOT use generic statements ("this is important", "it improves things")
3. ALWAYS express cause, impact, or reasoning
4. Each sentence must carry meaning
5. Language should feel natural and human, not robotic
6. Preserve ALL factual data — numbers, names, metrics, timelines
7. If the content already has strong narrative quality, refine but do not rewrite from scratch
8. Output must be 2–4 meaningful sentences — no more, no less
9. Never invent facts that are not present in the raw content

---

# OUTPUT FORMAT

Return JSON:

```json
{
  "narrative_text": "Rewritten version of the content in 2–4 meaningful sentences",
  "key_entities": ["entity1", "entity2"],
  "narrative_angle": "brief phrase describing the angle taken (e.g. 'cause and effect', 'before vs after', 'hidden cost')"
}
```

---

# QUALITY CHECK

Reject your own output if:

* it sounds generic
* it removes meaning from the original
* it feels like disconnected bullet points strung together
* it adds claims not present in the input

---

# EXAMPLE

**Bad input:**
"We improved onboarding. Growth increased."

**Bad output (REJECT THIS):**
"Onboarding is important. We made it better and things improved."

**Good output:**
"Our growth didn't come from luck — it came from fixing how users enter the product. By redesigning onboarding, we removed early friction, allowing users to engage faster and stay longer."

---

Return only JSON. No markdown backticks or preamble.
"""


# ── Public API ────────────────────────────────────────────────────────

async def transform_narrative(
    raw_content: dict | str,
    slide_index: int,
    total_slides: int,
    topic: str,
    narrative_role: str = "",
    emotional_tone: str = "",
) -> dict:
    """Transform raw slide content into story-driven narrative text.

    Args:
        raw_content: The original slide content (dict or string).
        slide_index: 0-based slide position.
        total_slides: Total number of slides.
        topic: Overall presentation topic.
        narrative_role: The narrative role assigned to this slide (hook, context, etc.).
        emotional_tone: Emotional tone for this slide.

    Returns:
        Dict with keys:
            - narrative_text: str — the enriched narrative (2–4 sentences)
            - key_entities: list[str] — extracted key entities
            - narrative_angle: str — the storytelling angle used
    """
    # Flatten content to a readable string for the LLM
    if isinstance(raw_content, dict):
        content_str = _flatten_content(raw_content)
    else:
        content_str = str(raw_content).strip()

    if not content_str:
        logger.warning("Slide %d: No content to transform — skipping narrative layer", slide_index + 1)
        return {
            "narrative_text": "",
            "key_entities": [],
            "narrative_angle": "passthrough",
        }

    user_prompt = (
        f"Slide position: {slide_index + 1} of {total_slides}\n"
        f"Overall topic: {topic}\n"
        f"Narrative role: {narrative_role or 'general'}\n"
        f"Emotional tone: {emotional_tone or 'neutral'}\n"
        f"\nRaw content:\n{content_str}"
    )

    try:
        result = await call_llm_json(NARRATIVE_TRANSFORM_PROMPT, user_prompt)

        narrative_text = result.get("narrative_text", "").strip()
        key_entities = result.get("key_entities", [])
        narrative_angle = result.get("narrative_angle", "").strip()

        # ── Quality gate: reject if output is shorter than input or generic ──
        if not narrative_text:
            logger.warning(
                "Slide %d: Narrative transform returned empty — falling back to raw content",
                slide_index + 1,
            )
            return _passthrough(content_str)

        # Reject if the transform lost too much content (fewer words than 40% of input)
        input_words = len(content_str.split())
        output_words = len(narrative_text.split())
        if output_words < input_words * 0.4 and input_words > 10:
            logger.warning(
                "Slide %d: Narrative transform lost content (%d → %d words) — falling back",
                slide_index + 1, input_words, output_words,
            )
            return _passthrough(content_str)

        logger.info(
            "Slide %d: Narrative transform OK — angle='%s', %d→%d words",
            slide_index + 1, narrative_angle, input_words, output_words,
        )

        return {
            "narrative_text": narrative_text,
            "key_entities": key_entities if isinstance(key_entities, list) else [],
            "narrative_angle": narrative_angle,
        }

    except Exception as e:
        logger.warning(
            "Slide %d: Narrative transform failed (%s) — falling back to raw content",
            slide_index + 1, e,
        )
        return _passthrough(content_str)


# ── Helpers ───────────────────────────────────────────────────────────

def _passthrough(content_str: str) -> dict:
    """Return a passthrough result when transformation fails or is skipped."""
    return {
        "narrative_text": content_str,
        "key_entities": [],
        "narrative_angle": "passthrough",
    }


def _flatten_content(content: dict) -> str:
    """Flatten a content dictionary into a readable string for the LLM.

    Handles common content structures:
      - title / punchline / subtext / metrics
      - features list
      - bullets list
      - arbitrary key-value pairs
    """
    parts: list[str] = []

    # Extract known keys in priority order
    for key in ("title", "punchline", "headline"):
        if key in content and content[key]:
            parts.append(str(content[key]).strip())

    for key in ("subtext", "subtitle", "summary"):
        if key in content and content[key]:
            parts.append(str(content[key]).strip())

    # Handle features list
    features = content.get("features")
    if isinstance(features, list):
        for feat in features:
            if isinstance(feat, dict):
                label = feat.get("label", "")
                desc = feat.get("description", "")
                if label or desc:
                    parts.append(f"{label}: {desc}".strip(": "))
            elif isinstance(feat, str):
                parts.append(feat)

    # Handle bullets
    bullets = content.get("bullets")
    if isinstance(bullets, list):
        for b in bullets:
            if b:
                parts.append(str(b).strip())

    # Handle metrics
    metrics = content.get("metrics")
    if isinstance(metrics, (dict, list)):
        if isinstance(metrics, dict):
            for k, v in metrics.items():
                parts.append(f"{k}: {v}")
        elif isinstance(metrics, list):
            for m in metrics:
                parts.append(str(m).strip())

    # Catch remaining keys not already handled
    handled_keys = {"title", "punchline", "headline", "subtext", "subtitle",
                    "summary", "features", "bullets", "metrics",
                    "presenter", "name"}
    for key, value in content.items():
        if key not in handled_keys and value:
            if isinstance(value, str):
                parts.append(f"{key}: {value}")
            elif isinstance(value, list):
                parts.append(f"{key}: {', '.join(str(v) for v in value)}")

    return "\n".join(parts)
