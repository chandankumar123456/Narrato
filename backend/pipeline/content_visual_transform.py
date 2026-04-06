"""
Content → visual structure: split headlines, stats, and narrative metadata
into primary / secondary / tertiary display fields. Used by the design engine
before template rendering (no LLM calls).
"""

from __future__ import annotations

import re
from typing import Any

# Narrative pipeline often emits this pattern — demote to kicker, not body copy.
_ACTOR_ACTION_PATTERN = re.compile(
    r"Actor:\s*(.+?)\s*\|\s*Action:\s*(.+)",
    re.IGNORECASE | re.DOTALL,
)

# Leading numeric / currency / percent / multiplier (e.g. "2.3x faster mastery")
_LEADING_STAT_PATTERN = re.compile(
    r"^((?:[\d.,]+x\b|[\d.,]+%?|\$[\d.,]+[KMBkmb]?|\$?[\d,]+(?:\.\d+)?%?))\s+(.+)$",
    re.IGNORECASE,
)

# Trailing parenthetical as tertiary context, e.g. "Market size (global)"
_PAREN_CONTEXT_PATTERN = re.compile(r"^(.+?)\s*(\([^)]{2,120}\))\s*$")


def extract_kicker_and_support(raw: str) -> tuple[str | None, str]:
    """
    If text matches Actor | Action pattern, return (kicker, "").
    Otherwise return (None, original) for normal subtitle handling.
    """
    if not raw or not str(raw).strip():
        return None, ""
    text = str(raw).strip()
    m = _ACTOR_ACTION_PATTERN.search(text)
    if m:
        actor = " ".join(m.group(1).split())
        action = " ".join(m.group(2).split())
        return f"{actor}\n{action}", ""
    return None, text


def title_to_display_lines(title: str, max_lines: int = 3) -> list[str]:
    """
    Break titles into 2–3 lines for display hierarchy (not one flat string).
    Prefers semantic separators over arbitrary wrapping.
    """
    t = (title or "").strip()
    if not t:
        return [""]
    for sep in (" — ", " – ", " | ", "; "):
        if sep in t:
            parts = [p.strip() for p in t.split(sep) if p.strip()]
            if 2 <= len(parts) <= max_lines:
                return parts[:max_lines]
    if len(t) > 48 and "," in t:
        chunks = [c.strip() for c in t.split(",") if c.strip()]
        if len(chunks) >= 2:
            line1 = chunks[0]
            rest = ", ".join(chunks[1:])
            if len(rest) < 120:
                return [line1, rest]
    words = t.split()
    if len(words) <= 6:
        return [t]
    mid = max(len(words) // 2, 4)
    return [" ".join(words[:mid]), " ".join(words[mid:])]


def parse_merged_stat_bullet(text: str) -> dict[str, Any] | None:
    """
    If a bullet is a single line like '68% of students fall behind grade level',
    return enriched stat dict; otherwise None.
    """
    t = (text or "").strip()
    if not t or len(t) < 6:
        return None
    m = _LEADING_STAT_PATTERN.match(t)
    if not m:
        return None
    v, rest = m.group(1).strip(), m.group(2).strip()
    if not rest:
        return None
    return enrich_stat_row(v, rest)


def is_currency_stat_value(value: str) -> bool:
    v = (value or "").strip()
    return bool(v) and v[0] in "$€£¥"


def enrich_stat_row(value: str, label: str) -> dict[str, Any]:
    """
    Ensure value/label split; pull parenthetical into tertiary context line.
    """
    v = (value or "").strip()
    l = (label or "").strip()
    if not v and l:
        m = _LEADING_STAT_PATTERN.match(l)
        if m:
            v, l = m.group(1).strip(), m.group(2).strip()
    ctx: str | None = None
    primary = l
    if l:
        pm = _PAREN_CONTEXT_PATTERN.match(l)
        if pm:
            primary, ctx = pm.group(1).strip(), pm.group(2).strip()
    return {"value": v, "label": primary, "label_context": ctx}


_VERB_LEAD_CLAUSE = re.compile(
    r"^(handle|handles|handling|manage|manages|managing|coordinate|coordinates|"
    r"drive|drives|build|builds|deliver|delivers|support|supports|lead|leads|"
    r"own|owns|run|runs|use|uses|using|power|powers|enable|enables)\b",
    re.I,
)


def split_role_line_detail(body: str, max_lead_words: int = 8) -> tuple[str, str]:
    """
    Split a sentence into a dominant role/title line and supporting clause when a
    lowercase verb phrase starts the second part, e.g.
    'Retail pricing analysts handle item-level changes' → (lead, 'handle …').
    """
    s = (body or "").strip()
    if not s:
        return "", ""
    words = s.split()
    if len(words) < 4:
        return split_body_lead_support(s, max_lead_words=max_lead_words)
    for i in range(2, min(max_lead_words + 2, len(words))):
        w = words[i]
        if not w:
            continue
        if w[0].islower() and _VERB_LEAD_CLAUSE.match(w):
            lead = " ".join(words[:i])
            rest = " ".join(words[i:])
            if len(lead.split()) >= 2 and len(rest.split()) >= 2:
                return lead, rest
    return split_body_lead_support(s, max_lead_words=max_lead_words)


def split_body_lead_support(body: str, max_lead_words: int = 7) -> tuple[str, str]:
    """
    First phrase (headline) vs supporting clause — e.g. role line + detail.
    """
    s = (body or "").strip()
    if not s:
        return "", ""
    if "," in s and len(s) > 40:
        a, b = s.split(",", 1)
        if len(a.split()) <= max_lead_words + 3:
            return a.strip(), b.strip()
    words = s.split()
    if len(words) <= max_lead_words:
        return s, ""
    return " ".join(words[:max_lead_words]), " ".join(words[max_lead_words:])


def dedupe_subtitle_vs_title(title: str, subtitle: str) -> str:
    """Avoid repeating the title inside the subtitle."""
    if not subtitle:
        return ""
    t, s = title.strip().lower(), subtitle.strip()
    if s.lower().startswith(t) and len(s) > len(title) + 5:
        return s[len(title) :].lstrip(" —–-|:").strip() or s
    if s.lower() == t:
        return ""
    return s


def compute_presentation_spec(
    slide_index: int,
    layout: str,
    slide_type: str,
    extra: dict[str, str] | None = None,
) -> dict[str, str]:
    """
    Deck rhythm + layout variants so consecutive slides are not identical shells.
    Optional *extra* merges presentation keys from the design-decision layer.
    """
    rhythms = ("airy", "standard", "dense")
    rhythm = rhythms[slide_index % 3]
    spec: dict[str, str] = {"rhythm": rhythm}

    if layout == "hero_center":
        # First slide: pitch-deck cover (eyebrow + brand + tagline) like reference decks
        if slide_index == 0:
            spec["hero_variant"] = "cover"
        else:
            spec["hero_variant"] = "editorial" if slide_index % 3 == 1 else "statement"
    elif layout == "grid_cards":
        spec["grid_variant"] = "bento" if slide_index % 2 == 1 else "uniform"
    elif layout == "stats_blocks":
        spec["stats_variant"] = "spotlight" if slide_index % 2 == 0 else "classic"
    elif layout == "split_left_text_right_visual":
        spec["split_variant"] = "asymmetric" if slide_index % 2 == 0 else "balanced"
    elif layout == "step_flow":
        spec["steps_variant"] = "rail" if slide_index % 2 == 0 else "stack"
    elif layout == "timeline_flow":
        spec["timeline_variant"] = "featured" if slide_index % 2 == 0 else "compact"

    if extra:
        for k, v in extra.items():
            if v is not None and str(v).strip() != "":
                spec[str(k)] = str(v)

    return spec
