import re

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
_MIN_MEANINGFUL_WORDS = 8
_GENERIC_PHRASES = (
    "follows logically",
    "next step",
    "leads to",
    "this creates need",
    "logical continuation",
    "from previous",
    "continues logic",
)


def _txt(value) -> str:
    return str(value or "").strip()


def _contains_generic_phrase(value: str) -> bool:
    text = _txt(value).lower()
    return any(phrase in text for phrase in _GENERIC_PHRASES)


def _is_weak(value: str) -> bool:
    text = _txt(value)
    if not text:
        return True
    if len(text.split()) < _MIN_MEANINGFUL_WORDS:
        return True
    return _contains_generic_phrase(text)


def _extract_tokens(value: str) -> list[str]:
    return [
        token for token in re.findall(r"[a-z0-9]+", _txt(value).lower())
        if len(token) >= 4
    ]


def _references_previous_key_message(cause_text: str, previous_key_message: str) -> bool:
    cause_tokens = set(_extract_tokens(cause_text))
    prev_tokens = _extract_tokens(previous_key_message)
    if not prev_tokens:
        return False
    # return any(token in cause_tokens for token in prev_tokens)
    overlap = set(prev_tokens) & cause_tokens
    return len(overlap) >= 2


def validate_narrative_arc(narrative_arc):
    """Validate narrative causality without repairing content.

    Returns:
        {
            "slides": [...],
            "invalid_slide_indices": [0-based indices],
            "violations": [human-readable violations]
        }
    """
    slides = [dict(s) if isinstance(s, dict) else {} for s in (narrative_arc or [])]
    invalid: list[int] = []
    violations: list[str] = []
    last_role_rank = -1

    for i, slide in enumerate(slides):
        slide_failures: list[str] = []

        cause_text = _txt(slide.get("cause_from_previous"))
        delta_text = _txt(slide.get("narrative_delta"))
        forward_tension_text = _txt(slide.get("forward_tension"))
        transition_text = _txt(slide.get("transition_reason"))

        if _is_weak(cause_text):
            slide_failures.append("weak or missing cause_from_previous")
        if _is_weak(delta_text):
            slide_failures.append("weak or missing narrative_delta")
        if _is_weak(forward_tension_text):
            slide_failures.append("weak or missing forward_tension")
        if _is_weak(transition_text):
            slide_failures.append("weak or missing transition_reason")

        if i > 0:
            previous_key_message = _txt(slides[i - 1].get("key_message"))
            if not _references_previous_key_message(cause_text, previous_key_message):
                slide_failures.append("cause_from_previous does not reference previous key_message")

        role = _txt(slide.get("slide_role")) or _txt(slide.get("role_in_story"))
        if role:
            role_rank = _SLIDE_ROLE_RANK.get(role)
            if role_rank is not None:
                if role_rank < last_role_rank:
                    slide_failures.append("slide_role regression")
                last_role_rank = max(last_role_rank, role_rank)

        if slide_failures:
            invalid.append(i)
            violations.append(f"Slide {i + 1}: {', '.join(slide_failures)}")

    return {
        "slides": slides,
        "invalid_slide_indices": invalid,
        "violations": violations,
    }
