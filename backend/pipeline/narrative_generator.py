"""Narrative-first content generator.

Generates a FULL structured narrative in ONE LLM call, then splits it into slides.
This replaces the slide-by-slide generation approach for speed and coherence.

The narrative follows a strict 12-section progression:
  1. Problem (specific instance)
  2. Who experiences it
  3. Root cause
  4. Why current systems fail
  5. Product concept
  6. How it works (mechanism)
  7. Why it's hard to copy
  8. Business model (pricing, who pays)
  9. Market expansion
  10. Traction (must include metrics)
  11. Go-to-market
  12. Vision
"""

from __future__ import annotations

import json
import logging
from typing import Optional

from models.presentation_state import PresentationState
from services.llm_client import call_llm_json

logger = logging.getLogger(__name__)

# The 12 narrative sections in strict order.
NARRATIVE_SECTIONS = [
    {
        "id": "problem",
        "title": "Problem",
        "instruction": "Describe a specific, concrete instance of the problem. Name an actual scenario with real actors and real consequences. Do NOT use abstract language.",
        "dimension": "actor",
    },
    {
        "id": "who_experiences",
        "title": "Who Experiences It",
        "instruction": "Identify the specific people, roles, or organizations that suffer from this problem. Include their daily workflow and how the problem disrupts it.",
        "dimension": "workflow",
    },
    {
        "id": "root_cause",
        "title": "Root Cause",
        "instruction": "Explain the structural or systemic reason this problem exists. Name the specific technical, organizational, or economic failure that causes it.",
        "dimension": "system",
    },
    {
        "id": "why_current_fail",
        "title": "Why Current Systems Fail",
        "instruction": "Name specific existing solutions or approaches and explain exactly why each one fails. Reference concrete limitations, not generic claims.",
        "dimension": "mechanism",
    },
    {
        "id": "product_concept",
        "title": "Product Concept",
        "instruction": "Describe the product in one clear sentence. State what it does, for whom, and what makes it fundamentally different. No buzzwords.",
        "dimension": "actor",
    },
    {
        "id": "how_it_works",
        "title": "How It Works",
        "instruction": "Walk through the exact mechanism step by step. Name specific data inputs, processing steps, and outputs. Describe what happens at each stage.",
        "dimension": "mechanism",
    },
    {
        "id": "defensibility",
        "title": "Why It's Hard to Copy",
        "instruction": "Explain the specific structural advantages: proprietary data, network effects, technical complexity, or regulatory barriers. Be concrete about each.",
        "dimension": "system",
    },
    {
        "id": "business_model",
        "title": "Business Model",
        "instruction": "State who pays, how much, and for what. Name the pricing model, contract structure, and revenue mechanics. Include specific numbers or ranges.",
        "dimension": "economics",
    },
    {
        "id": "market_expansion",
        "title": "Market Expansion",
        "instruction": "Describe the initial target market segment and the expansion path. Name specific verticals, geographies, or use cases for each phase.",
        "dimension": "economics",
    },
    {
        "id": "traction",
        "title": "Traction",
        "instruction": "Include specific metrics: revenue, users, growth rate, contracts signed, pilots completed. Every claim must have a number attached.",
        "dimension": "metric",
    },
    {
        "id": "go_to_market",
        "title": "Go-to-Market",
        "instruction": "Describe the specific acquisition channels, sales motion, and distribution strategy. Name partners, platforms, or tactics.",
        "dimension": "adoption",
    },
    {
        "id": "vision",
        "title": "Vision",
        "instruction": "Describe the long-term end state. What does the world look like when this product succeeds at scale? Be specific about the transformation.",
        "dimension": "actor",
    },
]

# Dimensions each section must introduce
REQUIRED_DIMENSIONS = ["actor", "workflow", "system", "mechanism", "economics", "metric", "adoption"]

# Generic phrases that MUST NOT appear in output
BANNED_PHRASES = [
    "ai layer", "connected system", "decision engine",
    "leveraging ai", "innovative solution", "cutting-edge",
    "game-changing", "next-generation", "state-of-the-art",
    "world-class", "best-in-class", "ai-powered",
    "scalable", "seamless", "robust", "enhances",
    "improves efficiency",
]


async def generate_narrative(state: PresentationState) -> PresentationState:
    """Generate full structured narrative in ONE LLM call, then split into slides.

    Returns updated state with:
      - ``structured_slides`` populated from narrative sections
      - ``slide_plan`` populated from narrative sections
      - ``metadata["narrative_generation"]`` with generation info
    """
    sections_json = json.dumps(
        [
            {
                "section_id": s["id"],
                "title": s["title"],
                "instruction": s["instruction"],
                "new_dimension": s["dimension"],
            }
            for s in NARRATIVE_SECTIONS
        ],
        indent=2,
    )

    banned_json = json.dumps(BANNED_PHRASES)

    system_prompt = f"""You are a world-class pitch deck narrative architect.
You generate a COMPLETE structured narrative for a presentation in ONE response.

ABSOLUTE RULES:
1. Each section MUST introduce NEW information not present in ANY other section.
2. NO repetition across sections — each section covers a different dimension.
3. NO generic phrases. BANNED: {banned_json}
4. Replace ALL abstraction with: specific actors, specific workflows, specific data, specific outputs.
5. Every claim must include a concrete mechanism, number, or named entity.
6. The "Traction" section MUST include at least 3 specific metrics with numbers.
7. The "Business Model" section MUST include pricing specifics.
8. The "How It Works" section MUST describe step-by-step data flow.

DIMENSION RULE: Each section introduces a NEW dimension from this set:
[actor, workflow, system, mechanism, economics, metric, adoption]
If a section overlaps with a previous one, rewrite it to introduce genuinely new information.

Return ONLY valid JSON. No markdown, no backticks, no preamble."""

    user_prompt = f"""Topic: {state.topic}
Presentation type: {state.presentation_type}
Audience: {state.audience or "general"}
Tone: {state.tone}

Generate a COMPLETE narrative with ALL 12 sections below.
For each section, provide:
- "title": section title (string)
- "body": 3-4 bullet points, each a specific, mechanism-driven statement (list of strings)
- "key_insight": one sentence summarizing the unique insight of this section (string)

SECTIONS (generate ALL in order):
{sections_json}

Return JSON:
{{
  "sections": [
    {{
      "section_id": "problem",
      "title": "...",
      "body": ["bullet 1 with specific detail", "bullet 2 with mechanism", "bullet 3 with data"],
      "key_insight": "One sentence unique insight"
    }},
    ... (all 12 sections)
  ]
}}"""

    try:
        result = await call_llm_json(system_prompt, user_prompt)
        sections = result.get("sections", [])
    except Exception as exc:
        logger.error("[narrative] LLM narrative generation failed: %s", exc)
        raise  # Let pipeline handle the failure

    if not sections or len(sections) != 12:
        raise ValueError(
            f"Narrative generation produced {len(sections)} sections, expected exactly 12"
        )

    # ── Convert narrative sections into slide plan + structured slides ──
    slide_plan: list[dict] = []
    structured_slides: list[dict] = []

    # Title slide
    slide_plan.append({
        "slide_id": 1,
        "section": "intro",
        "purpose": "Title slide",
        "type": "title_slide",
    })
    structured_slides.append({
        "slide_id": 1,
        "type": "title_slide",
        "content": {
            "title": state.topic,
            "subtitle": sections[0].get("key_insight", "") if sections else "",
            "presenter": "",
        },
    })

    # Map each narrative section to 1 slide
    slide_id = 2
    section_to_type = {
        "problem": "problem_slide",
        "who_experiences": "feature_slide",
        "root_cause": "feature_slide",
        "why_current_fail": "comparison_slide",
        "product_concept": "feature_slide",
        "how_it_works": "feature_slide",
        "defensibility": "feature_slide",
        "business_model": "stats_slide",
        "market_expansion": "feature_slide",
        "traction": "stats_slide",
        "go_to_market": "feature_slide",
        "vision": "conclusion_slide",
    }

    for section in sections:
        section_id = section.get("section_id", "unknown")
        slide_type = section_to_type.get(section_id, "feature_slide")
        title = section.get("title", section_id.replace("_", " ").title())
        body = section.get("body", [])
        key_insight = section.get("key_insight", "")

        slide_plan.append({
            "slide_id": slide_id,
            "section": section_id,
            "purpose": title,
            "type": slide_type,
        })

        # Build content based on slide type
        content = _build_slide_content(slide_type, title, body, key_insight)

        structured_slides.append({
            "slide_id": slide_id,
            "type": slide_type,
            "content": content,
        })
        slide_id += 1

    # Thank you / CTA slide
    slide_plan.append({
        "slide_id": slide_id,
        "section": "conclusion",
        "purpose": "Call to action",
        "type": "cta_slide",
    })
    structured_slides.append({
        "slide_id": slide_id,
        "type": "cta_slide",
        "content": {
            "title": "Get Started",
            "cta_text": f"Learn more about {state.topic}",
            "contact": "",
        },
    })

    meta = dict(state.metadata or {})
    meta["narrative_generation"] = {
        "sections_generated": len(sections),
        "slides_created": len(structured_slides),
        "method": "narrative_first_single_call",
    }

    return state.model_copy(update={
        "slide_plan": slide_plan,
        "structured_slides": structured_slides,
        "metadata": meta,
    })


def _build_slide_content(
    slide_type: str,
    title: str,
    body: list[str],
    key_insight: str,
) -> dict:
    """Build slide content dict from narrative section data.

    Does NOT call LLM — purely structural mapping.
    """
    if slide_type == "problem_slide":
        cards = [
            {"icon": "⚠", "label": f"Issue {i+1}", "description": b}
            for i, b in enumerate(body[:4])
        ]
        return {"title": title, "cards": cards}

    elif slide_type == "comparison_slide":
        # Split body into left (current) vs right (better)
        mid = len(body) // 2
        return {
            "title": title,
            "left_label": "Current State",
            "left_points": body[:mid] if mid > 0 else body[:2],
            "right_label": "Better Approach",
            "right_points": body[mid:] if mid > 0 else body[2:],
        }

    elif slide_type == "stats_slide":
        # Use key_insight as main stat description
        return {
            "title": title,
            "stat": body[0] if body else "",
            "stat_label": key_insight,
            "description": " | ".join(body[1:3]) if len(body) > 1 else "",
            "source": body[-1] if len(body) > 3 else "",
        }

    elif slide_type == "conclusion_slide":
        return {
            "title": title,
            "bullets": body[:4],
            "key_takeaway": key_insight,
        }

    else:
        # Default: feature_slide
        features = [
            {"icon": _get_icon(i), "label": b.split(".")[0][:60] if "." in b else b[:60], "description": b}
            for i, b in enumerate(body[:4])
        ]
        return {"title": title, "features": features}


def _get_icon(index: int) -> str:
    """Return a distinct icon for each feature position."""
    icons = ["🔹", "🔸", "⚡", "🎯", "📊", "🔑", "💡", "🚀"]
    return icons[index % len(icons)]
