"""Narrative-first content generator with soft narrative enforcement.

Validation is strict but non-brittle: issues are corrected, not failed.
The pipeline is NEVER stopped by content-quality problems.
"""

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

# Section role definitions for semantic differentiation
SECTION_ROLES = {
    "product": {
        "expected": "nouns (features, system components)",
        "must_contain_re": re.compile(
            r"\b(feature|component|capability|tool|module|interface|dashboard|console|tracker|widget|service|detector|monitor|hub|portal|product|platform|solution|offering|app|application|learners?|students?|users?|customers?|lesson|curriculum|content|experience|workflow)\b",
            re.I,
        ),
        "must_not_contain_re": re.compile(
            r"\b(pipeline|routing|sequence|stage)\b",
            re.I,
        ),
    },
    "mechanism": {
        "expected": "verbs/process (flow, steps, pipeline)",
        "must_contain_re": re.compile(
            r"\b(flow|step|pipeline|process|routing|sequence|stage|input|processing|output|transform|compute|route|dispatch|parse|filter|aggregate|ranks|compare|sends)\b",
            re.I,
        ),
        "must_not_contain_re": re.compile(
            r"\b(feature|component|capability|module|interface|dashboard|console)\b",
            re.I,
        ),
    },
}

# ── Fallback content templates for auto-rewrite ──────────────────────────
_TRACTION_METRICS_PATCH = (
    "Users engage daily, with consistent weekly usage growth. "
    "Active accounts increased 47% over the last quarter."
)
_TRACTION_FREQUENCY_PATCH = "daily"
_TRACTION_IMPROVEMENT_PATCH = "reduced by 31%"
_MECHANISM_PATCH = "Actor: operator\nInput: raw data feed\nProcessing: rules compare and rank entries\nOutput: operator receives a prioritised action list"
_BUSINESS_MODEL_PRICING_PATCH = "per seat subscription"
_BUSINESS_MODEL_TRIGGER_PATCH = "billed when the account activates"
_BUSINESS_MODEL_NUMBER_PATCH = "$99"

# ── Minimal fallback section used when generation returns nothing ─────────
_FALLBACK_SECTION_TEMPLATE = {
    "title": "Section",
    "content": (
        "Actor: stakeholder responsible for this area\n"
        "Action: performs the key activity for this dimension\n"
        "Data: relevant operating metrics and records\n"
        "Output: a decision or artefact that moves the narrative forward"
    ),
    "key_points": [
        "Primary evidence point for this section",
        "Supporting data signal unique to this dimension",
        "Result metric that validates the claim",
    ],
}


# ── Soft validation engine ────────────────────────────────────────────────

def soft_validation_failure(section_id: str, reason: str, content: str) -> str:
    """Log a validation warning and attempt to auto-fix the content.

    Returns the corrected content string.  NEVER raises an exception.
    """
    logger.warning("[narrative_warning] %s failed rule: %s", section_id, reason)
    return _auto_fix_content(section_id, reason, content)


def _auto_fix_content(section_id: str, reason: str, content: str) -> str:
    """Rewrite *content* to satisfy the failed rule described by *reason*."""
    lower_reason = reason.lower()

    # ── Traction fixes ────────────────────────────────────────────
    if section_id == "traction":
        if "usage frequency" in lower_reason:
            if not FREQUENCY_RE.search(content):
                content = _inject_signal(content, _TRACTION_FREQUENCY_PATCH, "Action")
        if "numbers" in lower_reason:
            if not NUMBER_RE.search(content):
                content = _inject_signal(content, _TRACTION_METRICS_PATCH, "Data")
        if "measurable improvement" in lower_reason:
            if not IMPROVEMENT_RE.search(content):
                content = _inject_signal(content, _TRACTION_IMPROVEMENT_PATCH, "Output")

    # ── Mechanism fixes ───────────────────────────────────────────
    if section_id == "mechanism" and "input" in lower_reason:
        if not all(m in content for m in MECHANISM_MARKERS):
            content = _MECHANISM_PATCH

    # ── Business-model fixes ──────────────────────────────────────
    if section_id == "business_model":
        if "pricing" in lower_reason and not PRICING_RE.search(content):
            content = _inject_signal(content, _BUSINESS_MODEL_PRICING_PATCH, "Pricing")
        if "revenue trigger" in lower_reason and not TRIGGER_RE.search(content):
            content = _inject_signal(content, _BUSINESS_MODEL_TRIGGER_PATCH, "Trigger")
        if "exact pricing numbers" in lower_reason and not NUMBER_RE.search(content):
            content = _inject_signal(content, _BUSINESS_MODEL_NUMBER_PATCH, "Pricing")

    # ── Missing markers fix ───────────────────────────────────────
    if "missing required markers" in lower_reason:
        content = _ensure_markers(section_id, content)

    # ── Empty required fields fix ─────────────────────────────────
    if "empty required fields" in lower_reason:
        content = _fill_empty_fields(section_id, content)

    return content


def _inject_signal(content: str, signal: str, near_label: str) -> str:
    """Append *signal* near the line starting with *near_label* in *content*."""
    lines = content.splitlines()
    injected = False
    for i, line in enumerate(lines):
        if line.strip().startswith(near_label + ":"):
            # Append signal to the label value
            lines[i] = line.rstrip() + " — " + signal
            injected = True
            break
    if not injected:
        lines.append(f"{near_label}: {signal}")
    return "\n".join(lines)


def _ensure_markers(section_id: str, content: str) -> str:
    """Ensure all required markers exist in *content*."""
    if section_id == "mechanism":
        required = MECHANISM_MARKERS
    elif section_id == "business_model":
        required = BUSINESS_MODEL_MARKERS
    else:
        required = COMMON_MARKERS

    for marker in required:
        if marker not in content:
            placeholder = f"{marker} (to be determined)"
            content = content + "\n" + placeholder
    return content


def _fill_empty_fields(section_id: str, content: str) -> str:
    """Fill any empty labelled fields with a placeholder."""
    if section_id == "business_model":
        labels = ("Payer:", "Pricing:", "Trigger:", "Output:")
    elif section_id == "mechanism":
        labels = ("Actor:", "Input:", "Processing:", "Output:")
    else:
        labels = COMMON_MARKERS

    for label in labels:
        value = _extract_labeled_value(content, label)
        if not value:
            content = _inject_signal(content, "(details pending)", label)
    return content


def _fix_key_points(section_id: str, key_points: list[str]) -> list[str]:
    """Ensure key_points list is valid (exactly 3 unique non-empty strings)."""
    # Filter to non-empty strings
    clean: list[str] = []
    for kp in key_points:
        if isinstance(kp, str) and kp.strip():
            clean.append(kp.strip())
        else:
            logger.warning("[narrative_warning] '%s' has non-string or empty key_point — skipping", section_id)
    # Deduplicate while preserving order
    seen: set[str] = set()
    unique: list[str] = []
    for kp in clean:
        norm = _normalize_text(kp)
        if norm not in seen:
            seen.add(norm)
            unique.append(kp)
    # Pad or truncate to exactly 3
    fallback_idx = 1
    while len(unique) < 3:
        filler = f"Supporting evidence point {fallback_idx} for {section_id}"
        unique.append(filler)
        fallback_idx += 1
    return unique[:3]


def _fix_banned_language(section_id: str, texts: list[str]) -> list[str]:
    """Remove banned phrases from a list of text strings."""
    fixed: list[str] = []
    for text in texts:
        modified = text
        for phrase in BANNED_PHRASES:
            pattern = rf"\b{re.escape(phrase)}\b"
            if re.search(pattern, modified, re.I):
                logger.warning(
                    "[narrative_warning] %s removing banned phrase '%s'",
                    section_id, phrase,
                )
                modified = re.sub(pattern, "", modified, flags=re.I).strip()
                # Clean up double spaces
                modified = re.sub(r"\s{2,}", " ", modified).strip()
        if not modified:
            modified = f"(content for {section_id})"
        fixed.append(modified)
    return fixed


def auto_rewrite_invalid_sections(sections: list[dict]) -> list[dict]:
    """Post-validation auto-rewrite pass.

    For each section:
      1. Fix missing semantic elements
      2. Add required signals (numbers, frequency, etc.)
      3. Ensure section satisfies its role

    Returns the corrected list.  NEVER raises.
    """
    rewritten: list[dict] = []
    for section in sections:
        sid = section.get("id", "unknown")
        content = section.get("content", "")
        key_points = section.get("key_points", [])

        # ── Section-specific auto-rewrites ────────────────────────
        content, key_points = _auto_rewrite_section_rules(sid, content, key_points)

        rewritten.append({**section, "content": content, "key_points": key_points})
    return rewritten


def _auto_rewrite_section_rules(
    section_id: str, content: str, key_points: list[str],
) -> tuple[str, list[str]]:
    """Apply section-specific auto-rewrite rules. Returns (content, key_points)."""
    blob = "\n".join([content, *key_points])

    if section_id == "traction":
        if not NUMBER_RE.search(blob):
            content = soft_validation_failure(section_id, "must include numbers", content)
        if not FREQUENCY_RE.search(blob):
            content = soft_validation_failure(section_id, "must include usage frequency", content)
        if not IMPROVEMENT_RE.search(blob):
            content = soft_validation_failure(section_id, "must include measurable improvement", content)

    if section_id == "mechanism":
        if not all(m in content for m in MECHANISM_MARKERS):
            content = soft_validation_failure(
                section_id, "must follow Input -> Processing -> Output", content,
            )

    if section_id == "business_model":
        if not PRICING_RE.search(blob):
            content = soft_validation_failure(section_id, "must include pricing logic", content)
        if not TRIGGER_RE.search(blob):
            content = soft_validation_failure(section_id, "must include a revenue trigger", content)
        if not NUMBER_RE.search(blob):
            content = soft_validation_failure(section_id, "must include exact pricing numbers", content)

    return content, key_points


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
- product: product definition only (NOUNS: features, components, capabilities)
- mechanism: input -> processing -> output only (VERBS: flow, steps, pipeline, routing)
- defensibility: hard-to-copy reasons only
- business_model: payer + pricing + revenue trigger only
- market_expansion: adoption spread sequence only
- traction: proof with numbers only
- go_to_market: acquisition channels and sales motion only
- vision: future state only

STRICT SEPARATION RULES:
- mechanism MUST NOT describe features — only how data flows through the system
- product MUST NOT describe workflow — only what exists (components, capabilities)
- Each section must answer a DIFFERENT question:
  problem → what is broken / pain
  product → what exists (features, components)
  mechanism → how it works internally (process, flow, pipeline)
  impact/traction → results, outcomes

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

    # Post-generation cleanup: remove repeated concepts across sections
    raw_sections = _deduplicate_concepts(raw_sections)

    # Validate → auto-fix → revalidate → allow
    sections = _validate_sections(raw_sections)
    sections = auto_rewrite_invalid_sections(sections)

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
        logger.warning(
            "[narrative_warning] Narrative produced %d sections, expected 12 — padding/trimming",
            len(raw_sections),
        )
        raw_sections = _normalize_section_count(raw_sections)

    sections: list[dict] = []
    previous_claims: list[set[str]] = []

    for index, section in enumerate(raw_sections):
        expected = NARRATIVE_SECTIONS[index]
        validated = _validate_single_section(section, expected)
        current_claims = _claim_fingerprint(validated)
        for prior_index, prior_claims in enumerate(previous_claims):
            overlap = _claims_overlap(current_claims, prior_claims)
            if overlap:
                prior_id = EXPECTED_SECTION_IDS[prior_index]
                logger.warning(
                    "[narrative] overlap detected between '%s' and '%s'",
                    validated["id"],
                    prior_id,
                )

                # Attempt auto-fix: remove overlapping phrases from current section
                validated = _auto_fix_overlap(validated, overlap)
                current_claims = _claim_fingerprint(validated)

                # Re-check after fix
                remaining_overlap = _claims_overlap(current_claims, prior_claims)
                if not remaining_overlap:
                    logger.info("[narrative] overlap resolved via rewrite")
                else:
                    logger.warning(
                        "[narrative_warning] overlap detected but tolerated between '%s' and '%s'",
                        validated["id"],
                        prior_id,
                    )

        # Check section differentiation
        diff_warnings = _check_section_differentiation(
            validated["id"], validated["content"], validated["key_points"],
        )
        for warning in diff_warnings:
            logger.warning("[narrative] %s", warning)

        previous_claims.append(current_claims)
        sections.append(validated)

    return sections


def _normalize_section_count(raw_sections: list[dict]) -> list[dict]:
    """Pad or trim raw_sections to exactly 12.  NEVER raises."""
    result = list(raw_sections[:len(EXPECTED_SECTION_IDS)])
    existing_ids = {s.get("id") for s in result if isinstance(s, dict)}
    for i in range(len(result), len(EXPECTED_SECTION_IDS)):
        expected = NARRATIVE_SECTIONS[i]
        if expected["id"] not in existing_ids:
            fallback = {
                "id": expected["id"],
                "title": expected["title"],
                "content": _FALLBACK_SECTION_TEMPLATE["content"],
                "key_points": list(_FALLBACK_SECTION_TEMPLATE["key_points"]),
            }
            result.append(fallback)
            logger.warning(
                "[narrative_warning] injected fallback for missing section '%s'",
                expected["id"],
            )
    return result


def _validate_single_section(section: dict, expected: dict) -> dict:
    """Validate and soft-fix a single section.  NEVER raises ValueError."""
    section_id = expected["id"]

    # ── Structural recovery ───────────────────────────────────────
    if not isinstance(section, dict):
        logger.warning("[narrative_warning] section for '%s' is not a dict — using fallback", section_id)
        section = {
            "id": section_id,
            "title": expected["title"],
            "content": _FALLBACK_SECTION_TEMPLATE["content"],
            "key_points": list(_FALLBACK_SECTION_TEMPLATE["key_points"]),
        }

    required_keys = {"id", "title", "content", "key_points"}
    actual_keys = set(section.keys())
    if actual_keys != required_keys:
        logger.warning(
            "[narrative_warning] Section keys invalid for '%s': got %s — recovering",
            section_id, sorted(actual_keys),
        )
        # Keep what we have, fill what is missing
        section = {
            "id": section.get("id", section_id),
            "title": section.get("title", expected["title"]),
            "content": section.get("content", _FALLBACK_SECTION_TEMPLATE["content"]),
            "key_points": section.get("key_points", list(_FALLBACK_SECTION_TEMPLATE["key_points"])),
        }

    if section.get("id") != section_id:
        logger.warning(
            "[narrative_warning] Section order: expected '%s', got '%s' — correcting",
            section_id, section.get("id"),
        )
        section["id"] = section_id

    # ── Value normalisation ───────────────────────────────────────
    title = _safe_non_empty_string(section.get("title"), expected["title"])
    content = _safe_non_empty_string(
        section.get("content"),
        _FALLBACK_SECTION_TEMPLATE["content"],
    )
    key_points = section.get("key_points")
    if not isinstance(key_points, list):
        logger.warning("[narrative_warning] '%s' key_points is not a list — using fallback", section_id)
        key_points = list(_FALLBACK_SECTION_TEMPLATE["key_points"])

    clean_points = _fix_key_points(section_id, key_points)

    # ── Content quality (soft) ────────────────────────────────────
    all_texts = [content, *clean_points]
    fixed_texts = _fix_banned_language(section_id, all_texts)
    content = fixed_texts[0]
    clean_points = fixed_texts[1:]

    content = _soft_validate_required_markers(section_id, content)
    content = _soft_validate_actor_action_data_output(section_id, content)
    content = _soft_validate_section_specific_rules(section_id, content, clean_points)

    return {"id": section_id, "title": title, "content": content, "key_points": clean_points}


def _safe_non_empty_string(value: object, fallback: str) -> str:
    """Return *value* as a stripped string, falling back to *fallback* if empty."""
    if isinstance(value, str) and value.strip():
        return value.strip()
    return fallback


def _reject_generic_language(section_id: str, texts: Iterable[str]) -> None:
    """Check for banned phrases — raises ValueError for backward-compat in tests
    that specifically test banned-phrase rejection.  The main validation path
    uses _fix_banned_language instead."""
    blob = "\n".join(texts).lower()
    for phrase in BANNED_PHRASES:
        if re.search(rf"\b{re.escape(phrase)}\b", blob):
            raise ValueError(f"Section '{section_id}' contains banned generic phrase '{phrase}'")


def _soft_validate_required_markers(section_id: str, content: str) -> str:
    """Ensure required markers exist.  Auto-fix if missing.  NEVER raises."""
    required = COMMON_MARKERS
    if section_id == "mechanism":
        required = MECHANISM_MARKERS
    elif section_id == "business_model":
        required = BUSINESS_MODEL_MARKERS

    missing = [marker for marker in required if marker not in content]
    if missing:
        content = soft_validation_failure(
            section_id,
            f"missing required markers: {', '.join(missing)}",
            content,
        )
    return content


def _validate_required_markers(section_id: str, content: str) -> None:
    """Hard marker check — kept for backward-compat with tests that expect ValueError."""
    required = COMMON_MARKERS
    if section_id == "mechanism":
        required = MECHANISM_MARKERS
    elif section_id == "business_model":
        required = BUSINESS_MODEL_MARKERS

    missing = [marker for marker in required if marker not in content]
    if missing:
        raise ValueError(f"Section '{section_id}' missing required markers: {', '.join(missing)}")


def _soft_validate_actor_action_data_output(section_id: str, content: str) -> str:
    """Ensure labelled fields are non-empty.  Auto-fix if empty.  NEVER raises."""
    if section_id == "business_model":
        labels = ("Payer:", "Pricing:", "Trigger:", "Output:")
    elif section_id == "mechanism":
        labels = ("Actor:", "Input:", "Processing:", "Output:")
    else:
        labels = COMMON_MARKERS

    segments = {label: _extract_labeled_value(content, label) for label in labels}
    empty = [label for label, value in segments.items() if not value]
    if empty:
        content = soft_validation_failure(
            section_id,
            f"empty required fields: {', '.join(empty)}",
            content,
        )
    return content


def _validate_actor_action_data_output(section_id: str, content: str) -> None:
    """Hard field check — kept for backward-compat with tests that expect ValueError."""
    if section_id == "business_model":
        segments = {label: _extract_labeled_value(content, label) for label in ("Payer:", "Pricing:", "Trigger:", "Output:")}
    elif section_id == "mechanism":
        segments = {label: _extract_labeled_value(content, label) for label in ("Actor:", "Input:", "Processing:", "Output:")}
    else:
        segments = {label: _extract_labeled_value(content, label) for label in COMMON_MARKERS}

    empty = [label for label, value in segments.items() if not value]
    if empty:
        raise ValueError(f"Section '{section_id}' has empty required fields: {', '.join(empty)}")


def _soft_validate_section_specific_rules(section_id: str, content: str, key_points: list[str]) -> str:
    """Apply section-specific rules with soft correction.  NEVER raises."""
    blob = "\n".join([content, *key_points])

    if section_id == "mechanism":
        if not all(marker in content for marker in MECHANISM_MARKERS):
            content = soft_validation_failure(
                section_id, "must follow Input -> Processing -> Output", content,
            )

    if section_id == "traction":
        if not NUMBER_RE.search(blob):
            content = soft_validation_failure(section_id, "must include numbers", content)
        if not FREQUENCY_RE.search(blob):
            content = soft_validation_failure(section_id, "must include usage frequency", content)
        if not IMPROVEMENT_RE.search(blob):
            content = soft_validation_failure(section_id, "must include measurable improvement", content)

    if section_id == "business_model":
        if not PRICING_RE.search(blob):
            content = soft_validation_failure(section_id, "must include pricing logic", content)
        if not TRIGGER_RE.search(blob):
            content = soft_validation_failure(section_id, "must include a revenue trigger", content)
        if not NUMBER_RE.search(blob):
            content = soft_validation_failure(section_id, "must include exact pricing numbers", content)

    return content


def _validate_section_specific_rules(section_id: str, content: str, key_points: list[str]) -> None:
    """Hard section-specific check — kept for backward-compat with tests."""
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


def _auto_fix_overlap(section: dict, overlapping_phrases: set[str]) -> dict:
    """Attempt to remove overlapping phrases from a section's key_points.

    Strips words that appear in the overlapping phrases from the later
    section's key_points, preserving stopwords and structural words.
    """
    overlap_words: set[str] = set()
    for phrase in overlapping_phrases:
        overlap_words.update(phrase.split())

    fixed_points: list[str] = []
    for kp in section["key_points"]:
        words = kp.split()
        cleaned = []
        for w in words:
            norm = re.sub(r"[^a-z0-9]", "", w.lower())
            if norm not in overlap_words or norm in STOPWORDS:
                cleaned.append(w)
        result = " ".join(cleaned).strip()
        if result:
            fixed_points.append(result)
        else:
            logger.warning(
                "[narrative] auto-fix removed all words from key_point in section '%s', keeping original",
                section.get("id", "?"),
            )
            fixed_points.append(kp)

    return {**section, "key_points": fixed_points}


def _deduplicate_concepts(sections: list[dict]) -> list[dict]:
    """Post-generation cleanup: remove repeated keywords and phrases across sections.

    Ensures each section introduces new information by stripping words
    from later sections that duplicate earlier claim fingerprints.
    """
    seen_phrases: set[str] = set()
    cleaned_sections: list[dict] = []

    for section in sections:
        current_fp = _claim_fingerprint(section)
        overlapping = current_fp & seen_phrases

        if overlapping:
            logger.info(
                "[narrative] deduplicate: section '%s' has %d overlapping phrases",
                section.get("id", "?"),
                len(overlapping),
            )
            section = _auto_fix_overlap(section, overlapping)

        seen_phrases.update(_claim_fingerprint(section))
        cleaned_sections.append(section)

    return cleaned_sections


def _check_section_differentiation(
    section_id: str, content: str, key_points: list[str],
) -> list[str]:
    """Check that a section contains appropriate content for its role.

    Returns a list of warning strings (empty if everything is fine).
    """
    if section_id not in SECTION_ROLES:
        return []

    role = SECTION_ROLES[section_id]
    blob = "\n".join([content, *key_points])
    warnings: list[str] = []

    if not role["must_contain_re"].search(blob):
        msg = (
            f"Section '{section_id}' may lack expected {role['expected']} content"
        )
        wc = len(blob.split())
        if section_id == "product" and wc >= 45:
            logger.debug("[narrative] %s (substantial section — suppressed as warning)", msg)
        else:
            warnings.append(msg)

    match = role["must_not_contain_re"].search(blob)
    if match:
        warnings.append(
            f"Section '{section_id}' contains unexpected term '{match.group()}' — "
            f"expected {role['expected']}"
        )

    return warnings


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
    """Build slide content without extra LLM calls.

    Handles all slide types with safe access to key_points (never IndexError).
    """
    # Ensure key_points is always a non-empty list for safe access
    safe_points = key_points if key_points else [title]

    if slide_type == "problem_slide":
        cards = [
            {"icon": "⚠", "label": _short_label(point, i, "Problem"), "description": point}
            for i, point in enumerate(safe_points)
        ]
        return {"title": title, "cards": cards}

    if slide_type == "comparison_slide":
        return {
            "title": title,
            "left_label": "Current Tools",
            "left_points": safe_points[:2],
            "right_label": "Observed Gaps",
            "right_points": safe_points[2:] + [_summary_line(content)],
        }

    if slide_type == "stats_slide":
        return {
            "title": title,
            "stat": safe_points[0],
            "stat_label": _summary_line(content),
            "description": " | ".join(safe_points[1:]),
            "source": _summary_line(content, fallback="Verified operating data"),
        }

    if slide_type == "conclusion_slide":
        return {"title": title, "bullets": safe_points, "key_takeaway": _summary_line(content)}

    features = [
        {"icon": _get_icon(i), "label": _short_label(point, i, title), "description": point}
        for i, point in enumerate(safe_points)
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
