"""Narrative-first content generator with hard narrative enforcement."""

from __future__ import annotations

import json
import logging
import re
from typing import Iterable

from models.presentation_state import PresentationState
from services.llm_client import call_llm_json

logger = logging.getLogger(__name__)

NARRATIVE_SECTIONS = [
    {
        "id": "problem",
        "title": "Problem",
        "dimension": "specific real-world scenario",
        "instruction": "Describe one real-world failure with time, place, and product context. Do not mention the product idea or benefits.",
        "content_format": "Actor: ...\nAction: ...\nData: ...\nOutput: ...",
    },
    {
        "id": "actor",
        "title": "Actor",
        "dimension": "who experiences the problem",
        "instruction": "Name the exact role and workflow affected. Focus only on who they are and what work breaks.",
        "content_format": "Actor: ...\nAction: ...\nData: ...\nOutput: ...",
    },
    {
        "id": "root_cause",
        "title": "Root Cause",
        "dimension": "why the problem happens structurally",
        "instruction": "Explain the structural reason the problem happens. Focus on the failure source, not the current tools or the product.",
        "content_format": "Actor: ...\nAction: ...\nData: ...\nOutput: ...",
    },
    {
        "id": "system_gap",
        "title": "System Gap",
        "dimension": "why current tools fail",
        "instruction": "List the specific limitations of current tools. Do not describe your product or broad market claims.",
        "content_format": "Actor: ...\nAction: ...\nData: ...\nOutput: ...",
    },
    {
        "id": "product",
        "title": "Product",
        "dimension": "what the product is",
        "instruction": "Define the product only. State what it is for whom, without benefits, traction, or go-to-market claims.",
        "content_format": "Actor: ...\nAction: ...\nData: ...\nOutput: ...",
    },
    {
        "id": "mechanism",
        "title": "Mechanism",
        "dimension": "how it works",
        "instruction": "Explain the mechanism strictly as input to processing to output. Include concrete data and resulting action.",
        "content_format": "Actor: ...\nInput: ...\nProcessing: ...\nOutput: ...",
    },
    {
        "id": "defensibility",
        "title": "Defensibility",
        "dimension": "why it is hard to copy",
        "instruction": "Focus on data advantages, workflow lock-in, or switching barriers. Do not repeat the mechanism or product definition.",
        "content_format": "Actor: ...\nAction: ...\nData: ...\nOutput: ...",
    },
    {
        "id": "business_model",
        "title": "Business Model",
        "dimension": "who pays and how much",
        "instruction": "State the exact payer, the pricing model, and when revenue is recognized. Include numbers.",
        "content_format": "Payer: ...\nPricing: ...\nTrigger: ...\nOutput: ...",
    },
    {
        "id": "market_expansion",
        "title": "Market Expansion",
        "dimension": "how adoption spreads",
        "instruction": "Describe adoption in ordered steps from the initial wedge to expansion. Do not repeat go-to-market channels.",
        "content_format": "Actor: ...\nAction: ...\nData: ...\nOutput: ...",
    },
    {
        "id": "traction",
        "title": "Traction",
        "dimension": "proof with numbers",
        "instruction": "Provide proof only: numeric metrics, usage frequency, and measurable improvement. No strategy language.",
        "content_format": "Actor: ...\nAction: ...\nData: ...\nOutput: ...",
    },
    {
        "id": "go_to_market",
        "title": "Go-To-Market",
        "dimension": "how customers are acquired",
        "instruction": "Describe acquisition channels, sales motion, and conversion path. Do not repeat adoption sequencing from market expansion.",
        "content_format": "Actor: ...\nAction: ...\nData: ...\nOutput: ...",
    },
    {
        "id": "vision",
        "title": "Vision",
        "dimension": "future state",
        "instruction": "Describe the long-term future state after adoption scales. Focus on what changes in the world, not present mechanics.",
        "content_format": "Actor: ...\nAction: ...\nData: ...\nOutput: ...",
    },
]

EXPECTED_SECTION_IDS = [section["id"] for section in NARRATIVE_SECTIONS]
REQUIRED_DIMENSIONS = [section["dimension"] for section in NARRATIVE_SECTIONS]
COMMON_MARKERS = ("Actor:", "Action:", "Data:", "Output:")
MECHANISM_MARKERS = ("Actor:", "Input:", "Processing:", "Output:")
BUSINESS_MODEL_MARKERS = ("Payer:", "Pricing:", "Trigger:", "Output:")

BANNED_PHRASES = [
    "ai platform",
    "connected layer",
    "decision engine",
    "leveraging ai",
    "innovative solution",
    "cutting-edge",
    "game-changing",
    "next-generation",
    "state-of-the-art",
    "world-class",
    "best-in-class",
    "ai-powered",
    "scalable",
    "seamless",
    "robust",
    "enhances",
    "improves efficiency",
    "solution",
    "engine",
    "platform",
    "system",
    "layer",
]

STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "in", "into", "is", "it",
    "of", "on", "or", "that", "the", "their", "this", "to", "with", "who", "what", "when",
    "where", "why", "how", "your", "our", "its", "than", "then", "after", "before", "during",
    "actor", "action", "data", "output", "input", "processing", "payer", "pricing", "trigger",
    "team", "teams", "step", "handling", "decisions", "workflow", "workflows", "change", "changes",
}

NUMBER_RE = re.compile(r"\b\d+(?:[.,]\d+)?\b")
FREQUENCY_RE = re.compile(r"\b(daily|weekly|monthly|quarterly|per day|per week|per month|times per day|times per week)\b", re.I)
IMPROVEMENT_RE = re.compile(
    r"\b(\d+(?:[.,]\d+)?%|reduction|increase|decrease|lift|faster|lower|higher|fell|rose|reduced|grew|improved)\b",
    re.I,
)
PRICING_RE = re.compile(r"\b(per\s+(unit|site|seat|location|shipment|account)|subscription|annual|monthly|usage-based|contract)\b", re.I)
TRIGGER_RE = re.compile(r"\b(when|upon|after|at the time|charged|billed|invoice)\b", re.I)
OVERLAP_DETECTION_MIN_PHRASE_LENGTH = 5
OVERLAP_DETECTION_MAX_PHRASE_LENGTH = 7


async def generate_narrative(state: PresentationState) -> PresentationState:
    """Generate a full 12-section narrative in one LLM call and map it to slides."""
    sections_json = json.dumps(
        [
            {
                "id": section["id"],
                "title": section["title"],
                "dimension": section["dimension"],
                "instruction": section["instruction"],
                "content_format": section["content_format"],
            }
            for section in NARRATIVE_SECTIONS
        ],
        indent=2,
    )

    banned_json = json.dumps(BANNED_PHRASES)
    expected_ids_json = json.dumps(EXPECTED_SECTION_IDS)

    system_prompt = f"""You are a pitch-deck narrative architect.
Generate the entire narrative in ONE pass.

HARD RULES:
1. Output EXACTLY 12 sections in this exact order: {expected_ids_json}
2. Each section may talk ONLY about its assigned dimension and nothing else.
3. Before writing each section, check all previous sections and SHIFT dimension if any explanation, mechanism, benefit, or phrasing overlaps.
4. NO generic language. NEVER use vague product terms. BANNED: {banned_json}
5. Each section must be concrete and directly usable in slides.
6. Every section must include actor, action, data, and output fields in content.
7. Section "mechanism" must use Input -> Processing -> Output explicitly.
8. Section "business_model" must include exact payer, pricing model, and revenue trigger.
9. Section "traction" must include numbers, usage frequency, and measurable improvement.
10. Do not add markdown, commentary, or any keys other than id, title, content, key_points.

NON-OVERLAP DIMENSIONS:
- problem: specific real-world scenario only
- actor: who experiences the problem only
- root_cause: structural cause only
- system_gap: limitations of current tools only
- product: product definition only
- mechanism: input -> processing -> output only
- defensibility: hard-to-copy reasons only
- business_model: payer + pricing + revenue trigger only
- market_expansion: adoption spread sequence only
- traction: proof with numbers only
- go_to_market: acquisition channels and sales motion only
- vision: future state only

Return ONLY valid JSON."""

    user_prompt = f"""Topic: {state.topic}
Presentation type: {state.presentation_type}
Audience: {state.audience or 'general'}
Tone: {state.tone}

Generate a strict narrative progression. Each section MUST answer "why next?" — the reader should feel a logical pull from one section to the next. NEVER repeat prior sections.

Required JSON format:
{{
  "sections": [
    {{
      "id": "problem",
      "title": "...",
      "content": "Actor: ...\\nAction: ...\\nData: ...\\nOutput: ...",
      "key_points": ["...", "...", "..."]
    }}
  ]
}}

For EVERY section:
- content must follow that section's exact content_format
- key_points must contain 3 concise, non-repetitive facts
- use specific actors, actions, data, and outputs
- do not repeat mechanisms, benefits, or phrasing used earlier

Sections:
{sections_json}
"""

    try:
        result = await call_llm_json(system_prompt, user_prompt)
        raw_sections = result.get("sections", [])
    except Exception as exc:
        logger.error("[narrative] LLM narrative generation failed: %s", exc)
        raise

    sections = _validate_sections(raw_sections)

    slide_plan: list[dict] = [
        {"slide_id": 1, "section": "intro", "purpose": "Title slide", "type": "title_slide"}
    ]
    structured_slides: list[dict] = [
        {
            "slide_id": 1,
            "type": "title_slide",
            "content": {
                "title": state.topic,
                "subtitle": _title_subtitle(sections[0]["content"]),
                "presenter": "",
            },
        }
    ]

    section_to_type = {
        "problem": "problem_slide",
        "actor": "feature_slide",
        "root_cause": "feature_slide",
        "system_gap": "comparison_slide",
        "product": "feature_slide",
        "mechanism": "feature_slide",
        "defensibility": "feature_slide",
        "business_model": "stats_slide",
        "market_expansion": "feature_slide",
        "traction": "stats_slide",
        "go_to_market": "feature_slide",
        "vision": "conclusion_slide",
    }

    for slide_id, section in enumerate(sections, start=2):
        slide_type = section_to_type[section["id"]]
        slide_plan.append(
            {
                "slide_id": slide_id,
                "section": section["id"],
                "purpose": section["title"],
                "type": slide_type,
            }
        )
        structured_slides.append(
            {
                "slide_id": slide_id,
                "type": slide_type,
                "content": _build_slide_content(slide_type, section["title"], section["content"], section["key_points"]),
            }
        )

    cta_slide_id = len(structured_slides) + 1
    slide_plan.append(
        {"slide_id": cta_slide_id, "section": "conclusion", "purpose": "Call to action", "type": "cta_slide"}
    )
    structured_slides.append(
        {
            "slide_id": cta_slide_id,
            "type": "cta_slide",
            "content": {
                "title": "Get Started",
                "cta_text": f"Review the {state.topic} narrative and move to diligence.",
                "contact": "",
            },
        }
    )

    meta = dict(state.metadata or {})
    meta["narrative_generation"] = {
        "sections_generated": len(sections),
        "slides_created": len(structured_slides),
        "method": "narrative_first_single_call",
        "schema": "id_title_content_key_points",
    }

    return state.model_copy(
        update={
            "slide_plan": slide_plan,
            "structured_slides": structured_slides,
            "metadata": meta,
        }
    )


def _validate_sections(raw_sections: list[dict]) -> list[dict]:
    if len(raw_sections) != len(EXPECTED_SECTION_IDS):
        raise ValueError(
            f"Narrative generation produced {len(raw_sections)} sections, expected exactly 12"
        )

    sections: list[dict] = []
    previous_claims: list[set[str]] = []

    for index, section in enumerate(raw_sections):
        expected = NARRATIVE_SECTIONS[index]
        validated = _validate_single_section(section, expected)
        current_claims = _claim_fingerprint(validated)
        for prior_index, prior_claims in enumerate(previous_claims):
            overlap = _claims_overlap(current_claims, prior_claims)
            if overlap:
                raise ValueError(
                    f"Narrative sections overlap: '{validated['id']}' repeats '{EXPECTED_SECTION_IDS[prior_index]}' via {sorted(overlap)[0]}"
                )
        previous_claims.append(current_claims)
        sections.append(validated)

    return sections


def _validate_single_section(section: dict, expected: dict) -> dict:
    if not isinstance(section, dict):
        raise ValueError("Each narrative section must be an object")

    required_keys = {"id", "title", "content", "key_points"}
    if set(section.keys()) != required_keys:
        raise ValueError(f"Section keys invalid for {expected['id']}: expected {sorted(required_keys)}")

    section_id = section.get("id")
    if section_id != expected["id"]:
        raise ValueError(f"Section order invalid: expected '{expected['id']}', got '{section_id}'")

    title = _require_non_empty_string(section.get("title"), f"title for {section_id}")
    content = _require_non_empty_string(section.get("content"), f"content for {section_id}")
    key_points = section.get("key_points")
    if not isinstance(key_points, list) or len(key_points) != 3:
        raise ValueError(f"Section '{section_id}' must include exactly 3 key_points")
    clean_points = [_require_non_empty_string(point, f"key_point for {section_id}") for point in key_points]
    if len({_normalize_text(point) for point in clean_points}) != len(clean_points):
        raise ValueError(f"Section '{section_id}' contains duplicate key_points")

    # Check content and key_points for banned phrases (titles are predefined
    # by NARRATIVE_SECTIONS and may legitimately contain words like "system").
    _reject_generic_language(section_id, [content, *clean_points])
    _validate_required_markers(section_id, content)
    _validate_actor_action_data_output(section_id, content)
    _validate_section_specific_rules(section_id, content, clean_points)

    return {"id": section_id, "title": title, "content": content, "key_points": clean_points}


def _reject_generic_language(section_id: str, texts: Iterable[str]) -> None:
    blob = "\n".join(texts).lower()
    for phrase in BANNED_PHRASES:
        if re.search(rf"\b{re.escape(phrase)}\b", blob):
            raise ValueError(f"Section '{section_id}' contains banned generic phrase '{phrase}'")


def _validate_required_markers(section_id: str, content: str) -> None:
    required = COMMON_MARKERS
    if section_id == "mechanism":
        required = MECHANISM_MARKERS
    elif section_id == "business_model":
        required = BUSINESS_MODEL_MARKERS

    missing = [marker for marker in required if marker not in content]
    if missing:
        raise ValueError(f"Section '{section_id}' missing required markers: {', '.join(missing)}")


def _validate_actor_action_data_output(section_id: str, content: str) -> None:
    if section_id == "business_model":
        segments = {label: _extract_labeled_value(content, label) for label in ("Payer:", "Pricing:", "Trigger:", "Output:")}
    elif section_id == "mechanism":
        segments = {label: _extract_labeled_value(content, label) for label in ("Actor:", "Input:", "Processing:", "Output:")}
    else:
        segments = {label: _extract_labeled_value(content, label) for label in COMMON_MARKERS}

    empty = [label for label, value in segments.items() if not value]
    if empty:
        raise ValueError(f"Section '{section_id}' has empty required fields: {', '.join(empty)}")


def _validate_section_specific_rules(section_id: str, content: str, key_points: list[str]) -> None:
    blob = "\n".join([content, *key_points])

    if section_id == "mechanism":
        if not all(marker in content for marker in MECHANISM_MARKERS):
            raise ValueError("Section 'mechanism' must follow Input -> Processing -> Output")

    if section_id == "traction":
        if not NUMBER_RE.search(blob):
            raise ValueError("Section 'traction' must include numbers")
        if not FREQUENCY_RE.search(blob):
            raise ValueError("Section 'traction' must include usage frequency")
        if not IMPROVEMENT_RE.search(blob):
            raise ValueError("Section 'traction' must include measurable improvement")

    if section_id == "business_model":
        if not PRICING_RE.search(blob):
            raise ValueError("Section 'business_model' must include pricing logic")
        if not TRIGGER_RE.search(blob):
            raise ValueError("Section 'business_model' must include a revenue trigger")
        if not NUMBER_RE.search(blob):
            raise ValueError("Section 'business_model' must include exact pricing numbers")


def _claim_fingerprint(section: dict) -> set[str]:
    claims = set()
    content_parts = []
    for line in section["content"].splitlines():
        if ":" in line:
            _, value = line.split(":", 1)
            content_parts.append(value.strip())
        else:
            content_parts.append(line.strip())
    for text in [*content_parts, *section["key_points"]]:
        normalized = _normalize_text(text)
        claims.update(_normalized_phrases(normalized))
    return claims


def _claims_overlap(current: set[str], prior: set[str]) -> set[str]:
    overlap = current & prior
    return {
        claim for claim in overlap
        if len(claim.split()) >= OVERLAP_DETECTION_MIN_PHRASE_LENGTH
    }


def _normalized_phrases(text: str) -> set[str]:
    tokens = [token for token in re.findall(r"[a-z0-9]+", text) if token not in STOPWORDS]
    phrases = set()
    for size in range(
        OVERLAP_DETECTION_MIN_PHRASE_LENGTH,
        OVERLAP_DETECTION_MAX_PHRASE_LENGTH + 1,
    ):
        for index in range(len(tokens) - size + 1):
            phrases.add(" ".join(tokens[index:index + size]))
    return phrases


def _extract_labeled_value(content: str, label: str) -> str:
    pattern = rf"{re.escape(label)}\s*(.+?)(?=\n[A-Z][A-Za-z\- ]+:|\Z)"
    match = re.search(pattern, content, re.S)
    return match.group(1).strip() if match else ""


def _build_slide_content(slide_type: str, title: str, content: str, key_points: list[str]) -> dict:
    """Build slide content without extra LLM calls."""
    if slide_type == "problem_slide":
        cards = [
            {"icon": "⚠", "label": _short_label(point, i, "Problem"), "description": point}
            for i, point in enumerate(key_points)
        ]
        return {"title": title, "cards": cards}

    if slide_type == "comparison_slide":
        return {
            "title": title,
            "left_label": "Current Tools",
            "left_points": key_points[:2],
            "right_label": "Observed Gaps",
            "right_points": key_points[2:] + [_summary_line(content)],
        }

    if slide_type == "stats_slide":
        return {
            "title": title,
            "stat": key_points[0],
            "stat_label": _summary_line(content),
            "description": " | ".join(key_points[1:]),
            "source": _summary_line(content, fallback="Verified operating data"),
        }

    if slide_type == "conclusion_slide":
        return {"title": title, "bullets": key_points, "key_takeaway": _summary_line(content)}

    features = [
        {"icon": _get_icon(i), "label": _short_label(point, i, title), "description": point}
        for i, point in enumerate(key_points)
    ]
    return {"title": title, "features": features, "summary": _summary_line(content)}


def _title_subtitle(content: str) -> str:
    return _summary_line(content, fallback="Structured narrative generated in one pass.")


def _summary_line(content: str, fallback: str = "") -> str:
    parts = [line.strip() for line in content.splitlines() if ":" in line]
    summary = " | ".join(parts[:2]).strip()
    return summary or fallback


def _short_label(text: str, index: int, fallback: str) -> str:
    cleaned = text.split(":", 1)[0].strip()
    if cleaned and len(cleaned.split()) <= 6:
        return cleaned
    words = text.split()
    return " ".join(words[:4]) if words else f"{fallback} {index + 1}"


def _get_icon(index: int) -> str:
    icons = ["🔹", "🔸", "⚡", "🎯", "📊", "🔑", "💡", "🚀"]
    return icons[index % len(icons)]


def _require_non_empty_string(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Missing {label}")
    return value.strip()


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9\s]", " ", text.lower())).strip()
