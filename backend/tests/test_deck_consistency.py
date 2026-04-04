"""Tests for the deck consistency optimizer.

Tests cover:
- Step 1: Weak slide detection by score gap
- Step 2: Terminology drift detection (LLM-based)
- Step 3: Leftover generic phrase scanning (deterministic)
- Step 4: Bullet structure consistency analysis (deterministic)
- Step 5: Consistency rewriting (LLM-based)
- Full pipeline: optimize_deck_consistency
- Integration: Metadata storage, edge cases
"""

import json
import pytest

from models.presentation_state import PresentationState
from pipeline.deck_consistency_optimizer import (
    BANNED_PHRASES,
    WEAKNESS_THRESHOLD,
    _find_weak_slides,
    _scan_leftover_generics,
    _analyze_bullet_structure,
    _collect_issues_for_slide,
    _flatten_content,
    _extract_bullets,
    _build_deck_text,
    _find_plan_entry,
    optimize_deck_consistency,
)


# ── Helpers ──────────────────────────────────────────────────────────

def _make_state(**overrides) -> PresentationState:
    """Create a minimal PresentationState for testing."""
    defaults = {
        "topic": "AI-powered Fraud Detection in Banking",
        "presentation_type": "pitch",
        "tone": "professional",
        "audience": "venture capital investors",
        "slide_count": 10,
        "story": {
            "narrative_type": "problem-solution",
            "key_message": "Real-time fraud detection using behavioral biometrics",
            "hook": "Banks lose $30B annually to fraud",
            "sections_flow": [
                {"section": "intro", "purpose": "Introduction", "emotion": "curiosity"},
                {"section": "problem", "purpose": "The fraud problem", "emotion": "urgency"},
                {"section": "solution", "purpose": "Our approach", "emotion": "confidence"},
            ],
            "call_to_action": "Join our Series A",
        },
        "slide_plan": [
            {"slide_id": 0, "section": "intro", "purpose": "Title slide", "type": "title_slide"},
            {"slide_id": 1, "section": "problem", "purpose": "Problem statement", "type": "problem_slide"},
            {"slide_id": 2, "section": "solution", "purpose": "Solution overview", "type": "feature_slide"},
        ],
    }
    defaults.update(overrides)
    return PresentationState(**defaults)


def _make_consistent_deck() -> PresentationState:
    """State with a consistent, high-quality deck."""
    state = _make_state()
    return state.model_copy(update={
        "structured_slides": [
            {
                "slide_id": 0,
                "type": "title_slide",
                "content": {
                    "title": "Behavioral Biometric Fraud Shield",
                    "subtitle": "Real-time transaction authentication via keystroke and mouse dynamics",
                    "presenter": "",
                },
            },
            {
                "slide_id": 1,
                "type": "problem_slide",
                "content": {
                    "title": "The Growing Banking Fraud Crisis",
                    "cards": [
                        {"icon": "⚠", "label": "CNP fraud surge",
                         "description": "Card-not-present fraud rose 35% in 2024 as synthetic identity attacks bypass static KYC checks"},
                        {"icon": "🔓", "label": "Credential stuffing at scale",
                         "description": "Automated bots attempt 100M+ stolen credential logins daily against top-10 US retail banks"},
                        {"icon": "⏱", "label": "Slow detection latency",
                         "description": "Legacy rule engines take 48 hours average to flag suspicious patterns causing cascading losses"},
                    ],
                },
            },
            {
                "slide_id": 2,
                "type": "feature_slide",
                "content": {
                    "title": "Behavioral Biometric Authentication Engine",
                    "features": [
                        {"icon": "⚡", "label": "Keystroke timing analysis",
                         "description": "Measures inter-key latency and hold-time patterns across 200ms windows to build per-user typing profiles"},
                        {"icon": "📊", "label": "Mouse trajectory entropy scoring",
                         "description": "Computes path randomness entropy from cursor movement vectors to distinguish human from bot sessions"},
                        {"icon": "🔒", "label": "Multi-signal device fingerprinting",
                         "description": "Combines 40 passive signals including GPU hash and WebGL renderer ID for session identity verification"},
                    ],
                },
            },
        ],
        "metadata": {
            "slide_evaluations": [
                {"slide_id": 0, "overall_score": 4.5},
                {"slide_id": 1, "overall_score": 4.8},
                {"slide_id": 2, "overall_score": 4.7},
            ],
        },
    })


def _make_inconsistent_deck() -> PresentationState:
    """State with inconsistent slides — one weak, one with generic phrases."""
    state = _make_state()
    return state.model_copy(update={
        "structured_slides": [
            {
                "slide_id": 0,
                "type": "title_slide",
                "content": {
                    "title": "Behavioral Biometric Fraud Shield",
                    "subtitle": "Real-time transaction authentication via keystroke and mouse dynamics",
                    "presenter": "",
                },
            },
            {
                "slide_id": 1,
                "type": "problem_slide",
                "content": {
                    "title": "The Problem",
                    "cards": [
                        {"icon": "⚠", "label": "Fraud",
                         "description": "Our robust platform enhances security using scalable architecture"},
                        {"icon": "🔓", "label": "Security",
                         "description": "Bad actors exploit the system"},
                    ],
                },
            },
            {
                "slide_id": 2,
                "type": "feature_slide",
                "content": {
                    "title": "Behavioral Biometric Authentication Engine",
                    "features": [
                        {"icon": "⚡", "label": "Keystroke timing analysis",
                         "description": "Measures inter-key latency and hold-time patterns across 200ms windows to build per-user typing profiles"},
                        {"icon": "📊", "label": "Mouse trajectory entropy scoring",
                         "description": "Computes path randomness entropy from cursor movement vectors to distinguish human from bot sessions"},
                    ],
                },
            },
        ],
        "metadata": {
            "slide_evaluations": [
                {"slide_id": 0, "overall_score": 4.5},
                {"slide_id": 1, "overall_score": 2.5},  # Weak slide
                {"slide_id": 2, "overall_score": 4.8},
            ],
        },
    })


# ═══════════════════════════════════════════════════════════════════════
# Step 1: Weak slide detection
# ═══════════════════════════════════════════════════════════════════════

class TestFindWeakSlides:
    def test_no_weak_slides_when_all_similar(self):
        slides = [{"slide_id": 0}, {"slide_id": 1}, {"slide_id": 2}]
        evals = [
            {"slide_id": 0, "overall_score": 4.5},
            {"slide_id": 1, "overall_score": 4.3},
            {"slide_id": 2, "overall_score": 4.7},
        ]
        result = _find_weak_slides(slides, evals)
        assert result == []  # All within threshold of 1.0

    def test_weak_slide_detected_by_score_gap(self):
        slides = [{"slide_id": 0}, {"slide_id": 1}, {"slide_id": 2}]
        evals = [
            {"slide_id": 0, "overall_score": 4.8},
            {"slide_id": 1, "overall_score": 2.5},  # Gap >= 1.0 from best
            {"slide_id": 2, "overall_score": 4.5},
        ]
        result = _find_weak_slides(slides, evals)
        assert 1 in result  # Slide at index 1 is weak

    def test_empty_evaluations(self):
        slides = [{"slide_id": 0}]
        assert _find_weak_slides(slides, []) == []

    def test_single_slide_no_weakness(self):
        slides = [{"slide_id": 0}]
        evals = [{"slide_id": 0, "overall_score": 3.0}]
        result = _find_weak_slides(slides, evals)
        assert result == []  # Only one slide, nothing to compare

    def test_all_weak_returns_all(self):
        slides = [{"slide_id": 0}, {"slide_id": 1}, {"slide_id": 2}]
        evals = [
            {"slide_id": 0, "overall_score": 5.0},
            {"slide_id": 1, "overall_score": 2.0},
            {"slide_id": 2, "overall_score": 3.0},
        ]
        result = _find_weak_slides(slides, evals)
        assert 1 in result  # 5.0 - 2.0 = 3.0 >= 1.0
        assert 2 in result  # 5.0 - 3.0 = 2.0 >= 1.0


# ═══════════════════════════════════════════════════════════════════════
# Step 3: Leftover generic phrase scanning
# ═══════════════════════════════════════════════════════════════════════

class TestScanLeftoverGenerics:
    def test_clean_deck_no_issues(self):
        slides = [
            {"content": {"title": "Specific Title", "body": "Concrete mechanism with detail"}},
        ]
        result = _scan_leftover_generics(slides)
        assert result == []

    def test_detects_banned_phrases(self):
        slides = [
            {"content": {"title": "Our Robust Platform", "body": "Enhances everything"}},
        ]
        result = _scan_leftover_generics(slides)
        assert len(result) >= 2  # "robust" + "enhances"

    def test_multiple_slides_scanned(self):
        slides = [
            {"content": {"body": "Clean specific content about fraud detection"}},
            {"content": {"body": "Our scalable AI-powered solution"}},
        ]
        result = _scan_leftover_generics(slides)
        # Only slide 1 has issues
        assert all(r["slide_index"] == 1 for r in result)
        assert len(result) >= 2  # scalable + ai-powered

    def test_case_insensitive(self):
        slides = [
            {"content": {"body": "ROBUST and SEAMLESS platform"}},
        ]
        result = _scan_leftover_generics(slides)
        assert len(result) >= 2


# ═══════════════════════════════════════════════════════════════════════
# Step 4: Bullet structure analysis
# ═══════════════════════════════════════════════════════════════════════

class TestAnalyzeBulletStructure:
    def test_consistent_bullets_no_issues(self):
        slides = [
            {"content": {"features": [
                {"description": "Measures inter-key latency and hold-time patterns for per-user profiling"},
                {"description": "Computes path entropy from cursor vectors to detect bot sessions"},
            ]}},
            {"content": {"features": [
                {"description": "Combines 40 passive signals including GPU hash for identity verification"},
                {"description": "Uses WebGL renderer analysis for device fingerprinting across sessions"},
            ]}},
        ]
        result = _analyze_bullet_structure(slides)
        assert result == []

    def test_detects_too_short_slide(self):
        # Slide 0: normal bullets, Slide 1: very short bullets
        slides = [
            {"content": {"features": [
                {"description": "Measures inter-key latency and hold-time patterns for per-user profiling"},
                {"description": "Computes path entropy from cursor vectors to detect bot sessions efficiently"},
            ]}},
            {"content": {"features": [
                {"description": "Fast"},
                {"description": "Quick"},
            ]}},
        ]
        result = _analyze_bullet_structure(slides)
        # Slide 1 should be flagged for too-short bullets
        assert any(r["slide_index"] == 1 for r in result)

    def test_no_bullets_no_issues(self):
        slides = [
            {"content": {"title": "Only titles here"}},
            {"content": {"title": "Another title"}},
        ]
        result = _analyze_bullet_structure(slides)
        assert result == []


# ═══════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════

class TestHelpers:
    def test_flatten_content(self):
        result = _flatten_content({"title": "Hello", "body": "World"})
        assert "title: Hello" in result
        assert "body: World" in result

    def test_extract_bullets_descriptions_only(self):
        content = {
            "features": [
                {"label": "Speed", "description": "Processes 10K transactions per second"},
            ],
            "title": "Should be skipped",
        }
        bullets = _extract_bullets(content)
        assert any("10K" in b for b in bullets)
        assert "Should be skipped" not in bullets

    def test_build_deck_text(self):
        slides = [
            {"type": "title_slide", "content": {"title": "Hello"}},
            {"type": "feature_slide", "content": {"title": "World"}},
        ]
        result = _build_deck_text(slides)
        assert "Slide 0" in result
        assert "Slide 1" in result
        assert "Hello" in result
        assert "World" in result

    def test_find_plan_entry(self):
        state = _make_state()
        entry = _find_plan_entry(state, 1)
        assert entry["section"] == "problem"

    def test_find_plan_entry_missing(self):
        state = _make_state()
        entry = _find_plan_entry(state, 999)
        assert entry["section"] == "unknown"

    def test_collect_issues_for_slide(self):
        issues = _collect_issues_for_slide(
            idx=1,
            weak_indices=[1],
            terminology_issues=[{"slide_indices": [1], "description": "drift", "suggested_term": "x"}],
            generic_issues=[{"slide_index": 1, "detail": "banned phrase"}],
            structural_issues=[{"slide_index": 1, "detail": "too short"}],
        )
        assert len(issues) == 4  # weakness + terminology + generic + structural
        assert any("WEAKNESS" in i for i in issues)
        assert any("TERMINOLOGY" in i for i in issues)
        assert any("GENERIC" in i for i in issues)
        assert any("STRUCTURE" in i for i in issues)

    def test_collect_issues_ignores_other_slides(self):
        issues = _collect_issues_for_slide(
            idx=0,
            weak_indices=[1],
            terminology_issues=[{"slide_indices": [1], "description": "drift", "suggested_term": "x"}],
            generic_issues=[{"slide_index": 1, "detail": "banned"}],
            structural_issues=[{"slide_index": 1, "detail": "short"}],
        )
        assert issues == []


# ═══════════════════════════════════════════════════════════════════════
# Full pipeline: optimize_deck_consistency
# ═══════════════════════════════════════════════════════════════════════

class TestOptimizeDeckConsistency:
    @pytest.mark.asyncio
    async def test_consistent_deck_unchanged(self, monkeypatch):
        """A consistent deck should pass through with zero rewrites."""
        rewrite_count = 0

        async def mock_call_llm_json(system_prompt: str, user_prompt: str) -> dict:
            nonlocal rewrite_count
            if "consistency reviewer" in system_prompt.lower():
                return {"issues": []}
            if "consistency optimizer" in system_prompt.lower():
                rewrite_count += 1
                return {}
            return {}

        monkeypatch.setattr(
            "pipeline.deck_consistency_optimizer.call_llm_json",
            mock_call_llm_json,
        )

        state = _make_consistent_deck()
        result = await optimize_deck_consistency(state)

        assert result.metadata is not None
        consistency = result.metadata["deck_consistency"]
        assert consistency["slides_rewritten"] == 0
        assert rewrite_count == 0

    @pytest.mark.asyncio
    async def test_inconsistent_deck_triggers_rewrites(self, monkeypatch):
        """Inconsistent deck should trigger rewrites for weak/generic slides."""
        rewrite_count = 0

        async def mock_call_llm_json(system_prompt: str, user_prompt: str) -> dict:
            nonlocal rewrite_count
            if "consistency reviewer" in system_prompt.lower():
                return {"issues": []}
            if "consistency optimizer" in system_prompt.lower():
                rewrite_count += 1
                return {
                    "title": "Improved Problem Statement",
                    "cards": [
                        {"icon": "⚠", "label": "CNP fraud surge",
                         "description": "Card-not-present fraud rose 35% in 2024 via synthetic identity attacks"},
                    ],
                }
            return {}

        monkeypatch.setattr(
            "pipeline.deck_consistency_optimizer.call_llm_json",
            mock_call_llm_json,
        )

        state = _make_inconsistent_deck()
        result = await optimize_deck_consistency(state)

        assert result.metadata is not None
        consistency = result.metadata["deck_consistency"]
        assert consistency["slides_rewritten"] >= 1
        assert rewrite_count >= 1

    @pytest.mark.asyncio
    async def test_metadata_stored(self, monkeypatch):
        """Verify deck_consistency metadata is stored."""
        async def mock_call_llm_json(system_prompt: str, user_prompt: str) -> dict:
            if "consistency reviewer" in system_prompt.lower():
                return {"issues": []}
            return {}

        monkeypatch.setattr(
            "pipeline.deck_consistency_optimizer.call_llm_json",
            mock_call_llm_json,
        )

        state = _make_consistent_deck()
        result = await optimize_deck_consistency(state)

        assert "deck_consistency" in result.metadata
        dc = result.metadata["deck_consistency"]
        assert "weak_slides" in dc
        assert "terminology_issues" in dc
        assert "generic_issues" in dc
        assert "structural_issues" in dc
        assert "slides_rewritten" in dc

    @pytest.mark.asyncio
    async def test_single_slide_skipped(self, monkeypatch):
        """Single-slide decks should be skipped."""
        state = _make_state()
        state = state.model_copy(update={
            "structured_slides": [
                {"slide_id": 0, "type": "title_slide", "content": {"title": "Only one"}},
            ],
        })
        result = await optimize_deck_consistency(state)
        # Should return unchanged — no deck_consistency in metadata
        assert result.structured_slides is not None
        assert len(result.structured_slides) == 1

    @pytest.mark.asyncio
    async def test_empty_slides_skipped(self, monkeypatch):
        """Empty structured_slides should return unchanged."""
        state = _make_state()
        result = await optimize_deck_consistency(state)
        assert result.structured_slides is None

    @pytest.mark.asyncio
    async def test_llm_failure_handled_gracefully(self, monkeypatch):
        """LLM failures should not crash the pipeline."""
        async def mock_call_llm_json(system_prompt: str, user_prompt: str) -> dict:
            raise RuntimeError("LLM unavailable")

        monkeypatch.setattr(
            "pipeline.deck_consistency_optimizer.call_llm_json",
            mock_call_llm_json,
        )

        state = _make_inconsistent_deck()
        result = await optimize_deck_consistency(state)

        # Should still return slides
        assert result.structured_slides is not None
        assert len(result.structured_slides) == 3

    @pytest.mark.asyncio
    async def test_preserves_slide_metadata(self, monkeypatch):
        """Slide metadata (image_path, type) should be preserved."""
        async def mock_call_llm_json(system_prompt: str, user_prompt: str) -> dict:
            if "consistency reviewer" in system_prompt.lower():
                return {"issues": []}
            return {}

        monkeypatch.setattr(
            "pipeline.deck_consistency_optimizer.call_llm_json",
            mock_call_llm_json,
        )

        state = _make_consistent_deck()
        slides = list(state.structured_slides)
        slides[1] = {**slides[1], "image_path": "/tmp/test.png"}
        state = state.model_copy(update={"structured_slides": slides})

        result = await optimize_deck_consistency(state)

        assert result.structured_slides[1].get("image_path") == "/tmp/test.png"
        assert result.structured_slides[1]["type"] == "problem_slide"

    @pytest.mark.asyncio
    async def test_weak_slides_identified_in_metadata(self, monkeypatch):
        """Weak slides should be recorded in metadata."""
        async def mock_call_llm_json(system_prompt: str, user_prompt: str) -> dict:
            if "consistency reviewer" in system_prompt.lower():
                return {"issues": []}
            if "consistency optimizer" in system_prompt.lower():
                return {
                    "title": "Improved",
                    "cards": [{"icon": "⚠", "label": "Better",
                               "description": "Specific mechanism with concrete detail about fraud detection"}],
                }
            return {}

        monkeypatch.setattr(
            "pipeline.deck_consistency_optimizer.call_llm_json",
            mock_call_llm_json,
        )

        state = _make_inconsistent_deck()
        result = await optimize_deck_consistency(state)

        dc = result.metadata["deck_consistency"]
        assert 1 in dc["weak_slides"]  # Slide index 1 is weak


# ═══════════════════════════════════════════════════════════════════════
# Integration: constants
# ═══════════════════════════════════════════════════════════════════════

class TestConstants:
    def test_banned_phrases_non_empty(self):
        assert len(BANNED_PHRASES) > 0

    def test_banned_phrases_lowercase(self):
        for phrase in BANNED_PHRASES:
            assert phrase == phrase.lower(), f"Not lowercase: {phrase}"

    def test_weakness_threshold_reasonable(self):
        assert 0.5 <= WEAKNESS_THRESHOLD <= 2.0
