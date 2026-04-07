"""Visual + Narrative Control Layer — deterministic slide visual planning.

Sits BETWEEN content preprocessing and HTML rendering.
Decides HOW each slide should be visually experienced:
  - layout (spatial arrangement)
  - density (content volume)
  - emphasis (visual weight distribution)
  - alignment (element positioning)
  - visual_intent (emotional/design direction)

NO LLM call. Pure logic based on slide position, narrative role, and
layout history to guarantee variation.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


# ── Narrative Role Mapping ────────────────────────────────────────────
# Position → role (1-indexed positions, cycles for >10 slides)
_ROLE_SEQUENCE = [
    "hook",         # 1
    "context",      # 2
    "problem",      # 3
    "explanation",  # 4
    "tension",      # 5
    "insight",      # 6
    "solution",     # 7
    "application",  # 8
    "proof",        # 9
    "closure",      # 10
]


def _get_narrative_role(slide_index: int, total_slides: int, slide_role: Optional[str] = None) -> str:
    """Map slide index (0-based) to narrative role.

    For presentations with ≤10 slides: direct mapping.
    For >10 slides: first and last are always hook/closure; middle
    slides cycle through the interior roles.
    """
    role_text = (slide_role or "").strip().lower()
    if role_text:
        role_alias = {
            "problem": "problem",
            "solution": "solution",
            "product": "application",
            "market": "proof",
            "business model": "application",
            "competition": "explanation",
            "financials": "proof",
            "funding ask": "closure",
            "impact": "proof",
            "closure": "closure",
            "context": "context",
            "tension": "tension",
            "insight": "insight",
        }
        for key, mapped in role_alias.items():
            if key in role_text:
                return mapped

    if total_slides <= 10:
        if slide_index < len(_ROLE_SEQUENCE):
            return _ROLE_SEQUENCE[slide_index]
        return "application"  # fallback for edge cases

    # First slide is always hook, last is always closure
    if slide_index == 0:
        return "hook"
    if slide_index == total_slides - 1:
        return "closure"

    # Interior slides cycle through roles 1–8 (context → proof)
    interior_roles = _ROLE_SEQUENCE[1:-1]  # context..proof
    interior_idx = (slide_index - 1) % len(interior_roles)
    return interior_roles[interior_idx]


# ── Role → Visual Rules (deterministic) ──────────────────────────────

_ROLE_VISUAL_RULES: dict[str, dict] = {
    "hook": {
        "allowed_layouts": ["center_focus", "floating"],
        "density": "minimal",
        "emphasis": "primary",
        "alignment": "center",
        "visual_feel": "dramatic, arresting — the audience should stop and pay attention",
    },
    "context": {
        "allowed_layouts": ["left_heavy", "split"],
        "density": "medium",
        "emphasis": "balanced",
        "alignment": "left",
        "visual_feel": "grounded, informative — setting the stage with clarity",
    },
    "problem": {
        "allowed_layouts": ["left_heavy", "right_heavy"],
        "density": "medium",
        "emphasis": "primary",
        "alignment": "left",
        "visual_feel": "tense, confrontational — the issue demands attention",
    },
    "explanation": {
        "allowed_layouts": ["split", "staggered"],
        "density": "high",
        "emphasis": "balanced",
        "alignment": "mixed",
        "visual_feel": "structured, methodical — breaking down complexity into clarity",
    },
    "tension": {
        "allowed_layouts": ["right_heavy", "corner"],
        "density": "medium",
        "emphasis": "primary",
        "alignment": "right",
        "visual_feel": "compressed, urgent — emotional weight pulling the audience forward",
    },
    "insight": {
        "allowed_layouts": ["center_focus", "floating"],
        "density": "minimal",
        "emphasis": "primary",
        "alignment": "center",
        "visual_feel": "revelatory, clean — a single powerful idea landing with force",
    },
    "solution": {
        "allowed_layouts": ["split", "left_heavy"],
        "density": "high",
        "emphasis": "balanced",
        "alignment": "mixed",
        "visual_feel": "confident, resolving — demonstrating the answer with authority",
    },
    "application": {
        "allowed_layouts": ["staggered", "split"],
        "density": "high",
        "emphasis": "balanced",
        "alignment": "mixed",
        "visual_feel": "practical, detailed — showing how it works in reality",
    },
    "proof": {
        "allowed_layouts": ["staggered", "split"],
        "density": "high",
        "emphasis": "supporting",
        "alignment": "mixed",
        "visual_feel": "evidence-driven, structured — multiple supporting points build conviction",
    },
    "closure": {
        "allowed_layouts": ["center_focus", "floating"],
        "density": "minimal",
        "emphasis": "primary",
        "alignment": "center",
        "visual_feel": "calm, resolved — leaving the audience with a lasting impression",
    },
}


# ── Layout Diversity Engine ───────────────────────────────────────────

def _pick_layout(allowed: list[str], layout_history: list[str]) -> str:
    """Pick a layout from the allowed set, avoiding repeating the last 2 layouts.

    Guarantees visual diversity across the deck.
    """
    recent = layout_history[-2:] if len(layout_history) >= 2 else layout_history

    # Prefer layouts NOT in recent history
    preferred = [l for l in allowed if l not in recent]
    if preferred:
        return preferred[0]

    # If all allowed layouts are recent, pick the one used least recently
    for l in allowed:
        if l not in layout_history[-1:]:
            return l

    # Absolute fallback: first allowed
    return allowed[0]


def compute_visual_plan(
    slide_index: int,
    total_slides: int,
    preprocessing_result: dict,
    layout_history: list[str],
) -> dict:
    """Compute a deterministic visual plan for a single slide.

    Args:
        slide_index: 0-based slide position.
        total_slides: Total slides in the presentation.
        preprocessing_result: Output from the content preprocessor.
        layout_history: List of layouts already assigned to previous slides
                        (mutated in-place by appending the chosen layout).

    Returns:
        Visual plan dict with: layout, density, emphasis, alignment,
        narrative_role, visual_intent.
    """
    slide_role = preprocessing_result.get("role_in_story") or preprocessing_result.get("role")
    role = _get_narrative_role(slide_index, total_slides, slide_role=slide_role)
    rules = _ROLE_VISUAL_RULES.get(role, _ROLE_VISUAL_RULES["application"])

    fixed_layout_by_role = {
        "problem": "left_heavy",
        "solution": "center_focus",
        "product": "staggered",
        "market": "split",
        "financials": "right_heavy",
        "competition": "split",
        "business model": "staggered",
        "funding ask": "center_focus",
    }
    layout = None
    role_text = str(slide_role or "").lower()
    for key, fixed_layout in fixed_layout_by_role.items():
        if key in role_text:
            layout = fixed_layout
            break
    if layout is None:
        layout = _pick_layout(rules["allowed_layouts"], layout_history)
    layout_history.append(layout)

    # Build visual intent from role rules + content
    title = preprocessing_result.get("title", "")
    primary = preprocessing_result.get("primary_element", "")
    sups = preprocessing_result.get("supporting_elements", [])

    # Density override: if content has many supporting elements, bump density
    effective_density = rules["density"]
    if len(sups) >= 3 and effective_density == "medium":
        effective_density = "high"
    if len(sups) == 0 and effective_density != "minimal":
        effective_density = "minimal"

    visual_intent = (
        f"Role: {role}. {rules['visual_feel']}. "
        f"The dominant element is '{primary[:60]}' — it must be the first thing the eye sees. "
        f"{'Supporting content forms ' + str(len(sups)) + ' distinct blocks around it.' if sups else 'No supporting blocks — keep this minimal and impactful.'}"
    )

    plan = {
        "layout": layout,
        "density": effective_density,
        "emphasis": rules["emphasis"],
        "alignment": rules["alignment"],
        "narrative_role": role,
        "visual_intent": visual_intent,
    }

    logger.info(
        "[visual_control] Slide %d → role=%s layout=%s density=%s emphasis=%s alignment=%s",
        slide_index + 1, role, layout, effective_density,
        rules["emphasis"], rules["alignment"],
    )

    return plan


# ── Layout CSS Directives (injected into render prompt) ───────────────

_LAYOUT_CSS_DIRECTIVES: dict[str, str] = {
    "center_focus": (
        "Position the dominant element at absolute center (50%/50%). "
        "Use flexbox with justify-content:center and align-items:center. "
        "Supporting elements (if any) go below the center at reduced opacity or size."
    ),
    "left_heavy": (
        "Anchor the dominant element to the LEFT 30% of the slide. "
        "Use a 60/40 or 70/30 split with the right side as breathing space. "
        "Supporting elements stack vertically in the left column."
    ),
    "right_heavy": (
        "Anchor the dominant element to the RIGHT 30% of the slide. "
        "Use a 40/60 or 30/70 split with the left side as breathing space. "
        "Supporting elements stack vertically in the right column."
    ),
    "split": (
        "Divide the slide into two clear halves (left/right). "
        "Primary element dominates one half, supporting elements occupy the other. "
        "Use CSS grid: grid-template-columns: 1fr 1fr."
    ),
    "corner": (
        "Place the dominant element in the top-right or bottom-left corner, offset from center. "
        "Use absolute positioning with 15-20% margin from edges. "
        "Supporting elements anchor to the opposite corner."
    ),
    "floating": (
        "Position elements with asymmetric offsets — NOT centered, NOT aligned to grid. "
        "Use absolute positioning with varied top/left values (e.g. 30%/25%, 55%/60%). "
        "Create visual tension through offset placement."
    ),
    "staggered": (
        "Distribute elements in a staggered, uneven grid — no two elements share the same Y or X position. "
        "Use CSS grid with grid-template-rows and varied column spans. "
        "Each supporting element should feel independently placed."
    ),
}


def get_layout_directive(layout: str) -> str:
    """Get the CSS/positioning directive string for a layout type."""
    return _LAYOUT_CSS_DIRECTIVES.get(layout, _LAYOUT_CSS_DIRECTIVES["center_focus"])


def format_visual_plan_for_renderer(plan: dict) -> str:
    """Format the visual plan as a strict instruction block for the LLM renderer.

    This string is injected directly into the render prompt so the renderer
    MUST follow the visual plan rather than deciding layout on its own.
    """
    directive = get_layout_directive(plan["layout"])

    return (
        f"\n\n── VISUAL PLAN (MANDATORY — your layout MUST follow this) ──\n"
        f"NARRATIVE ROLE: {plan['narrative_role']}\n"
        f"LAYOUT: {plan['layout']}\n"
        f"LAYOUT DIRECTIVE: {directive}\n"
        f"DENSITY: {plan['density']}\n"
        f"EMPHASIS: {plan['emphasis']} (what should visually dominate)\n"
        f"ALIGNMENT: {plan['alignment']}\n"
        f"VISUAL INTENT: {plan['visual_intent']}\n"
        f"── END VISUAL PLAN ──\n"
    )
