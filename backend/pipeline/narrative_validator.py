import logging

logger = logging.getLogger(__name__)

SLIDE_ROLE_SEQUENCE = [
    "Problem",
    "Consequence",
    "Escalation",
    "BreakingPoint",
    "Solution",
    "Proof",
    "Scale",
    "Ask",
]
_SLIDE_ROLE_RANK = {role: idx for idx, role in enumerate(SLIDE_ROLE_SEQUENCE)}
_WEAK_PHRASES = {
    "derived",
    "basic",
    "from previous",
    "logical continuation",
    "next step",
    "leads to next",
    "then we see",
}
DEFAULT_FIRST_SLIDE_CAUSE = "This opens with the central investor problem and sets the baseline pressure."
DEFAULT_NARRATIVE_DELTA = "This slide changes the narrative by adding a new consequence."
DEFAULT_FORWARD_TENSION = "This creates unresolved pressure that forces the next slide."


def _txt(value) -> str:
    return str(value or "").strip()


def _is_weak(value) -> bool:
    text = _txt(value).lower()
    if not text or len(text.split()) < 5:
        return True
    return any(p in text for p in _WEAK_PHRASES)


def _safe_tension(value, fallback: int) -> int:
    try:
        return max(0, min(10, int(value)))
    except Exception:
        return fallback


def _default_role(idx: int, total: int) -> str:
    if total <= 0:
        return SLIDE_ROLE_SEQUENCE[min(idx, len(SLIDE_ROLE_SEQUENCE) - 1)]
    mapped = min(idx * len(SLIDE_ROLE_SEQUENCE) // max(total, 1), len(SLIDE_ROLE_SEQUENCE) - 1)
    return SLIDE_ROLE_SEQUENCE[mapped]


def _default_tension(idx: int, total: int) -> int:
    if total <= 1:
        return 5
    solution_idx = max(1, min(total - 1, total // 2))
    if idx <= solution_idx:
        return max(2, min(9, int(round((idx / max(solution_idx, 1)) * 9))))
    remaining = max(1, total - 1 - solution_idx)
    numerator = max(0, total - 1 - idx)
    return max(1, min(6, int(round((numerator / remaining) * 6))))


def _repair_slide(slide: dict, idx: int, total: int, previous_slide: dict | None) -> dict:
    repaired = dict(slide or {})
    role = _txt(repaired.get("slide_role")) or _default_role(idx, total)
    repaired["slide_role"] = role
    repaired["role_in_story"] = _txt(repaired.get("role_in_story")) or role
    repaired["intent"] = _txt(repaired.get("intent")) or "general"
    repaired["emotional_tone"] = _txt(repaired.get("emotional_tone")) or "neutral"
    repaired["key_message"] = _txt(repaired.get("key_message")) or f"Core point {idx + 1}"
    repaired["transition_reason"] = _txt(repaired.get("transition_reason"))
    repaired["resolution"] = _txt(repaired.get("resolution"))

    if idx == 0:
        if _is_weak(repaired.get("cause_from_previous")):
            repaired["cause_from_previous"] = DEFAULT_FIRST_SLIDE_CAUSE
    else:
        prev_msg = _txt((previous_slide or {}).get("key_message")) or "the previous unresolved gap"
        if _is_weak(repaired.get("cause_from_previous")):
            repaired["cause_from_previous"] = f"Because {prev_msg}, this slide is required to advance the argument."

    if _is_weak(repaired.get("narrative_delta")):
        repaired["narrative_delta"] = DEFAULT_NARRATIVE_DELTA

    if _is_weak(repaired.get("forward_tension")):
        repaired["forward_tension"] = DEFAULT_FORWARD_TENSION

    if _is_weak(repaired.get("transition_reason")):
        repaired["transition_reason"] = "This follows because the previous claim creates unresolved investor pressure."

    repaired["tension_level"] = _safe_tension(repaired.get("tension_level"), _default_tension(idx, total))

    # Backward-compatible aliases
    repaired["cause"] = repaired["cause_from_previous"]
    repaired["next_trigger"] = repaired["forward_tension"]
    repaired["tension"] = _txt(repaired.get("tension")) or repaired["forward_tension"]
    return repaired


def _repair_tension_curve(slides: list[dict]) -> list[dict]:
    repaired = [dict(s) for s in slides]
    if not repaired:
        return repaired

    solution_idx = next(
        (i for i, s in enumerate(repaired) if _txt(s.get("slide_role")) == "Solution"),
        max(1, len(repaired) // 2),
    )

    for i, slide in enumerate(repaired):
        current = _safe_tension(slide.get("tension_level"), _default_tension(i, len(repaired)))
        if i <= solution_idx and i > 0:
            prev = _safe_tension(repaired[i - 1].get("tension_level"), _default_tension(i - 1, len(repaired)))
            current = max(current, min(10, prev + 1))
        elif i > solution_idx:
            prev = _safe_tension(repaired[i - 1].get("tension_level"), _default_tension(i - 1, len(repaired)))
            current = min(current, max(0, prev - 1))

        slide["tension_level"] = max(0, min(10, current))
    return repaired


def validate_narrative_arc(narrative_arc):
    arc = [dict(s) if isinstance(s, dict) else {} for s in (narrative_arc or [])]
    if not arc:
        return arc

    repaired: list[dict] = []
    violations: list[str] = []
    total = len(arc)
    last_rank = -1

    for i, slide in enumerate(arc):
        required_failures = []
        if not _txt(slide.get("cause_from_previous")) and not _txt(slide.get("cause")):
            required_failures.append("missing cause")
        if _is_weak(slide.get("narrative_delta")):
            required_failures.append("no narrative change")
        if _is_weak(slide.get("transition_reason")) or _is_weak(slide.get("forward_tension") or slide.get("next_trigger")):
            required_failures.append("weak transition")

        role = _txt(slide.get("slide_role")) or _txt(slide.get("role_in_story"))
        role = role if role in _SLIDE_ROLE_RANK else _default_role(i, total)
        role_rank = _SLIDE_ROLE_RANK.get(role, _SLIDE_ROLE_RANK[_default_role(i, total)])
        if role_rank < last_rank:
            required_failures.append("slide_role regression")
        last_rank = max(last_rank, role_rank)

        prev = repaired[-1] if repaired else None
        candidate = dict(slide)
        if required_failures:
            violations.append(f"Slide {i + 1}: {', '.join(required_failures)}")
            candidate = _repair_slide(candidate, i, total, prev)
        else:
            candidate = _repair_slide(candidate, i, total, prev)

        repaired.append(candidate)

    repaired = _repair_tension_curve(repaired)

    if violations:
        for v in violations:
            logger.warning("[narrative_validator] repaired violation: %s", v)

    return repaired
