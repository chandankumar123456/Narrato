from typing import List, Dict, Set

REQUIRED_ROLES = [
    "Problem",
    "Solution",
    "Product",
    "Market",
    "Business Model",
    "Competition",
    "Financials",
    "Funding Ask"
]


def normalize_role(role: str) -> str:
    return (role or "").strip().lower()


def _canonical_coverage(role: str) -> Set[str]:
    normalized = normalize_role(role)
    covered: Set[str] = set()

    direct_map = {
        "problem": "Problem",
        "solution": "Solution",
        "product": "Product",
        "market": "Market",
        "business model": "Business Model",
        "competition": "Competition",
        "financials": "Financials",
        "funding ask": "Funding Ask",
    }

    for key, canonical in direct_map.items():
        if key in normalized:
            covered.add(canonical)

    # Narrative role normalization required by contract
    if "solution" in normalized:
        covered.update({"Product", "Business Model"})
    if "impact" in normalized:
        covered.add("Financials")
    if "closure" in normalized:
        covered.add("Funding Ask")

    return covered


def find_role(slides: List[Dict], target: str) -> bool:
    for s in slides:
        role = s.get("role_in_story", "") or s.get("role", "")
        if target in _canonical_coverage(role):
            return True
    return False


def inject_slide(slides: List[Dict], role: str) -> Dict:
    """
    Creates a hard fallback slide if missing
    """

    def next_step(text: str) -> str:
        return f"{text} → forcing the next stage of the narrative"

    if role == "Competition":
        return {
            "intent": "comparison",
            "role_in_story": "Competition",
            "key_message": "Existing tools fail to unify monetization",
            "transition_reason": "Fragmented platforms create inefficiency and lost revenue",
            "emotional_tone": "critical",
            "cause": "No unified marketplace exists",
            "tension": "Fragmentation reduces monetization potential",
            "resolution": "",
            "next_trigger": next_step("A better unified solution must replace fragmented tools")
        }

    if role == "Financials":
        return {
            "intent": "financials",
            "role_in_story": "Financials",
            "key_message": "Projected $50M ARR within 3 years",
            "transition_reason": "Revenue scales directly with marketplace transaction volume",
            "emotional_tone": "confident",
            "cause": "Transaction volume drives revenue growth",
            "tension": "Scaling requires predictable monetization",
            "resolution": "",
            "next_trigger": next_step("Clear financial upside creates need for investor participation")
        }

    if role == "Funding Ask":
        return {
            "intent": "funding",
            "role_in_story": "Funding Ask",
            "key_message": "Raising $5M to scale marketplace",
            "transition_reason": "Capital is required to accelerate growth and capture market",
            "emotional_tone": "decisive",
            "cause": "Growth opportunity requires immediate investment",
            "tension": "Without funding, expansion slows significantly",
            "resolution": "",
            "next_trigger": next_step("Funding unlocks execution and market capture")
        }

    if role == "Business Model":
        return {
            "intent": "business_model",
            "role_in_story": "Business Model",
            "key_message": "Revenue from transaction take rates",
            "transition_reason": "Marketplace monetization scales with each transaction",
            "emotional_tone": "logical",
            "cause": "Transactions generate recurring revenue streams",
            "tension": "Need scalable and repeatable monetization",
            "resolution": "",
            "next_trigger": next_step("Proven monetization leads to market expansion opportunity")
        }

    # fallback (IMPORTANT: fully validator-safe)
    return {
        "intent": role.lower(),
        "role_in_story": role,
        "key_message": f"{role} clearly defined",
        "transition_reason": "This element is required for investor completeness",
        "emotional_tone": "neutral",
        "cause": "Missing required component in narrative",
        "tension": "This creates increasing pressure that must be resolved",
        "resolution": "",
        "next_trigger": next_step("This ensures continuity of the investor narrative")
    }


def _trim_to_target_count(slides: List[Dict], target_count: int) -> List[Dict]:
    trimmed = list(slides)
    idx = len(trimmed) - 1
    while len(trimmed) > target_count and idx >= 0:
        candidate = trimmed[idx]
        probe = trimmed[:idx] + trimmed[idx + 1:]
        if all(find_role(probe, role) for role in REQUIRED_ROLES):
            trimmed = probe
        idx -= 1
    return trimmed[:target_count]


def _pad_to_target_count(slides: List[Dict], target_count: int) -> List[Dict]:
    padded = list(slides)
    while len(padded) < target_count:
        if padded:
            last = dict(padded[-1])
            last["key_message"] = f"{last.get('key_message', 'Investor point')} (reinforced)"
            last["cause"] = f"Builds directly on: {padded[-1].get('key_message', 'previous slide')}"
            last["next_trigger"] = "This creates a concrete need for the next investor proof point"
            padded.append(last)
        else:
            padded.append(inject_slide([], "Problem"))
    return padded


def _reindex_slides(slides: List[Dict]) -> List[Dict]:
    for idx, slide in enumerate(slides, start=1):
        slide["slide_id"] = idx
    return slides


def enforce_investor_structure(slides: List[Dict], target_count: int | None = None) -> List[Dict]:
    """
    Ensures all required investor roles exist.
    Injects missing slides.
    """

    enforced = list(slides or [])

    for role in REQUIRED_ROLES:
        if not find_role(enforced, role):
            enforced.append(inject_slide(enforced, role))

    if target_count is not None:
        if len(enforced) > target_count:
            enforced = _trim_to_target_count(enforced, target_count)
        elif len(enforced) < target_count:
            enforced = _pad_to_target_count(enforced, target_count)

    return _reindex_slides(enforced)
