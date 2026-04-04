"""Tests for the slide evaluator (upgraded validation engine).

Tests cover:
- Phase 1A: Deterministic hard checks (generic phrases, bullet length)
- Phase 1B: Semantic repetition checks (LLM-based)
- Phase 2: Scoring system (specificity, mechanism, uniqueness, clarity)
- Phase 3: Strict critic (investor mode)
- Phase 4: Targeted regeneration with specific fix instructions
- Phase 5: Intent enforcement
- Phase 6: Full evaluation + improvement pipeline
- Integration: Orchestrator integration
"""

import json
import pytest

from models.presentation_state import PresentationState
from pipeline.slide_evaluator import (
    GENERIC_PHRASES,
    MIN_BULLET_WORDS,
    MIN_ACCEPTABLE_SCORE,
    MAX_IMPROVEMENT_ATTEMPTS,
    _deterministic_checks,
    _extract_bullets,
    _flatten_content,
    _find_plan_entry,
    _build_fix_instructions,
    evaluate_and_improve_slides,
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


def _make_state_with_good_content() -> PresentationState:
    """State with specific, mechanism-driven content that should pass."""
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
                        {"icon": "⏱", "label": "Slow rule-based detection",
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
    })


def _make_state_with_generic_content() -> PresentationState:
    """State with generic content containing banned phrases."""
    state = _make_state()
    return state.model_copy(update={
        "structured_slides": [
            {
                "slide_id": 0,
                "type": "title_slide",
                "content": {
                    "title": "AI-Powered Solution",
                    "subtitle": "Our robust and scalable platform",
                    "presenter": "",
                },
            },
            {
                "slide_id": 1,
                "type": "problem_slide",
                "content": {
                    "title": "The Problem",
                    "cards": [
                        {"icon": "⚠", "label": "Inefficiency",
                         "description": "Current systems are not efficient and improves efficiency is needed"},
                        {"icon": "🔓", "label": "Security gaps",
                         "description": "Bad security"},
                        {"icon": "⏱", "label": "Slow processes",
                         "description": "Things are slow"},
                    ],
                },
            },
        ],
    })


# ═══════════════════════════════════════════════════════════════════════
# Phase 1A: Deterministic checks
# ═══════════════════════════════════════════════════════════════════════

class TestDeterministicChecks:
    def test_clean_content_passes(self):
        content = {
            "title": "Behavioral Biometric Engine",
            "features": [
                {"description": "Measures keystroke timing patterns across 200ms windows for per-user profiling"},
            ],
        }
        result = _deterministic_checks(content)
        assert result["passed"] is True
        assert result["failures"] == []

    def test_generic_phrase_detected(self):
        content = {"title": "Our AI-powered Platform", "body": "We improve everything"}
        result = _deterministic_checks(content)
        assert result["passed"] is False
        assert any("ai-powered" in f for f in result["failures"])

    def test_multiple_generic_phrases_detected(self):
        content = {
            "title": "Robust and Scalable Solution",
            "body": "Our seamless platform enhances productivity",
        }
        result = _deterministic_checks(content)
        assert result["passed"] is False
        # Should catch: robust, scalable, seamless, enhances
        generic_failures = [f for f in result["failures"] if "generic_phrase" in f]
        assert len(generic_failures) >= 3

    def test_short_bullet_detected(self):
        content = {
            "features": [
                {"description": "Fast processing"},  # Only 2 words
                {"description": "Measures keystroke patterns across 200ms sampling windows"},
            ],
        }
        result = _deterministic_checks(content)
        assert result["passed"] is False
        assert any("short_bullet" in f for f in result["failures"])

    def test_all_banned_phrases_caught(self):
        for phrase in GENERIC_PHRASES:
            content = {"body": f"Our system uses {phrase} to deliver results"}
            result = _deterministic_checks(content)
            assert result["passed"] is False, f"Failed to catch: {phrase}"

    def test_case_insensitive_detection(self):
        content = {"body": "Our AI-POWERED platform is SEAMLESS and ROBUST"}
        result = _deterministic_checks(content)
        assert result["passed"] is False


# ═══════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════

class TestExtractBullets:
    def test_extracts_descriptions_from_features(self):
        content = {
            "features": [
                {"label": "Speed", "description": "Processes 10K transactions per second"},
                {"label": "Accuracy", "description": "99.7% fraud detection rate with 0.01% false positives"},
            ],
        }
        bullets = _extract_bullets(content)
        # Should extract descriptions but NOT labels (labels are headings)
        assert len(bullets) == 2
        assert any("10K" in b for b in bullets)
        assert "Speed" not in bullets

    def test_extracts_string_bullets(self):
        content = {"bullets": ["First point here", "Second point here"]}
        bullets = _extract_bullets(content)
        assert "First point here" in bullets
        assert "Second point here" in bullets

    def test_extracts_body_text(self):
        content = {"body": "This is the body text with mechanism details"}
        bullets = _extract_bullets(content)
        assert "This is the body text with mechanism details" in bullets

    def test_skips_title_and_metadata_fields(self):
        content = {
            "title": "Should be skipped",
            "presenter": "Should be skipped",
            "description": "Should be included with mechanism detail",
        }
        bullets = _extract_bullets(content)
        assert "Should be skipped" not in bullets
        assert any("Should be included" in b for b in bullets)

    def test_empty_content(self):
        assert _extract_bullets({}) == []


class TestFlattenContent:
    def test_basic_dict(self):
        result = _flatten_content({"title": "Hello", "body": "World"})
        assert "title: Hello" in result
        assert "body: World" in result

    def test_list_of_dicts(self):
        result = _flatten_content({
            "features": [{"label": "A", "description": "B"}]
        })
        assert "A" in result
        assert "B" in result

    def test_empty(self):
        assert _flatten_content({}) == ""


class TestFindPlanEntry:
    def test_finds_matching_entry(self):
        state = _make_state()
        entry = _find_plan_entry(state, 1)
        assert entry["section"] == "problem"
        assert entry["purpose"] == "Problem statement"

    def test_returns_default_for_missing(self):
        state = _make_state()
        entry = _find_plan_entry(state, 999)
        assert entry["section"] == "unknown"

    def test_handles_no_slide_plan(self):
        state = _make_state(slide_plan=None)
        # Needs to create state without slide_plan
        state = state.model_copy(update={"slide_plan": None})
        entry = _find_plan_entry(state, 0)
        assert entry["section"] == "unknown"


class TestBuildFixInstructions:
    def test_repetition_fix(self):
        result = _build_fix_instructions(
            failures=["repeated_idea: same concept as slide 1"],
            scores={},
            critic={},
        )
        assert "REPETITION FIX" in result

    def test_generic_fix(self):
        result = _build_fix_instructions(
            failures=["generic_phrase: 'scalable'"],
            scores={},
            critic={},
        )
        assert "GENERIC FIX" in result
        assert "scalable" in result

    def test_short_bullet_fix(self):
        result = _build_fix_instructions(
            failures=["short_bullet[0]: 'Fast processing'"],
            scores={},
            critic={},
        )
        assert "DEPTH FIX" in result

    def test_critic_fix(self):
        result = _build_fix_instructions(
            failures=["critic_rejected: too vague"],
            scores={},
            critic={"weaknesses": ["no mechanism", "too generic"]},
        )
        assert "INVESTOR FIX" in result

    def test_intent_fix(self):
        result = _build_fix_instructions(
            failures=["intent_violation: solution in problem slide"],
            scores={},
            critic={},
        )
        assert "INTENT FIX" in result

    def test_score_based_fixes(self):
        result = _build_fix_instructions(
            failures=[],
            scores={"specificity": 2, "mechanism": 2, "uniqueness": 2, "clarity": 2},
            critic={},
        )
        assert "SPECIFICITY FIX" in result
        assert "MECHANISM FIX" in result
        assert "UNIQUENESS FIX" in result
        assert "CLARITY FIX" in result

    def test_general_fix_when_no_specific_failures(self):
        result = _build_fix_instructions(failures=[], scores={}, critic={})
        assert "GENERAL FIX" in result

    def test_multiple_fixes_combined(self):
        result = _build_fix_instructions(
            failures=["generic_phrase: 'robust'", "short_bullet[0]: 'short'"],
            scores={"specificity": 2},
            critic={},
        )
        assert "GENERIC FIX" in result
        assert "DEPTH FIX" in result
        assert "SPECIFICITY FIX" in result


# ═══════════════════════════════════════════════════════════════════════
# Full pipeline: evaluate_and_improve_slides
# ═══════════════════════════════════════════════════════════════════════

class TestEvaluateAndImproveSlides:
    @pytest.mark.asyncio
    async def test_good_content_passes_without_regeneration(self, monkeypatch):
        """Good content should pass evaluation without needing improvement."""
        regen_count = 0

        async def mock_call_llm_json(system_prompt: str, user_prompt: str) -> dict:
            nonlocal regen_count
            # Semantic checks
            if "repetition detector" in system_prompt.lower():
                return {"has_overlap": False, "overlapping_ideas": []}
            # Scoring
            if "quality scorer" in system_prompt.lower():
                return {"specificity": 5, "mechanism": 5, "uniqueness": 5, "clarity": 5}
            # Strict critic
            if "tier-1" in system_prompt.lower():
                return {"accepted": True, "reason": "excellent", "weaknesses": []}
            # Intent
            if "intent enforcer" in system_prompt.lower():
                return {"compliant": True, "reason": "perfect match"}
            # If regeneration is called
            if "improver" in system_prompt.lower():
                regen_count += 1
                return {}
            return {}

        monkeypatch.setattr(
            "pipeline.slide_evaluator.call_llm_json",
            mock_call_llm_json,
        )

        state = _make_state_with_good_content()
        result = await evaluate_and_improve_slides(state)

        assert result.structured_slides is not None
        assert len(result.structured_slides) == 3
        assert regen_count == 0  # No regeneration needed
        assert result.metadata is not None
        assert "slide_evaluations" in result.metadata
        assert len(result.metadata["slide_evaluations"]) == 3

    @pytest.mark.asyncio
    async def test_generic_content_triggers_improvement(self, monkeypatch):
        """Generic content should trigger targeted regeneration."""
        regen_count = 0

        async def mock_call_llm_json(system_prompt: str, user_prompt: str) -> dict:
            nonlocal regen_count
            if "repetition detector" in system_prompt.lower():
                return {"has_overlap": False, "overlapping_ideas": []}
            if "quality scorer" in system_prompt.lower():
                # First evaluation: low scores; second: acceptable
                if regen_count == 0:
                    return {"specificity": 2, "mechanism": 2, "uniqueness": 2, "clarity": 2}
                return {"specificity": 5, "mechanism": 5, "uniqueness": 5, "clarity": 5}
            if "tier-1" in system_prompt.lower():
                if regen_count == 0:
                    return {"accepted": False, "reason": "too generic", "weaknesses": ["no detail"]}
                return {"accepted": True, "reason": "improved", "weaknesses": []}
            if "intent enforcer" in system_prompt.lower():
                return {"compliant": True, "reason": "ok"}
            if "improver" in system_prompt.lower():
                regen_count += 1
                return {
                    "title": "Improved Title",
                    "subtitle": "Specific mechanism-driven subtitle with concrete details about the process",
                    "presenter": "",
                }
            return {}

        monkeypatch.setattr(
            "pipeline.slide_evaluator.call_llm_json",
            mock_call_llm_json,
        )

        state = _make_state_with_generic_content()
        result = await evaluate_and_improve_slides(state)

        assert result.structured_slides is not None
        # At least some slides should have been regenerated
        assert regen_count >= 1

    @pytest.mark.asyncio
    async def test_evaluations_stored_in_metadata(self, monkeypatch):
        """Evaluation results should be stored in state.metadata."""
        async def mock_call_llm_json(system_prompt: str, user_prompt: str) -> dict:
            if "repetition detector" in system_prompt.lower():
                return {"has_overlap": False, "overlapping_ideas": []}
            if "quality scorer" in system_prompt.lower():
                return {"specificity": 4, "mechanism": 4, "uniqueness": 4, "clarity": 4}
            if "tier-1" in system_prompt.lower():
                return {"accepted": True, "reason": "ok", "weaknesses": []}
            if "intent enforcer" in system_prompt.lower():
                return {"compliant": True, "reason": "ok"}
            return {}

        monkeypatch.setattr(
            "pipeline.slide_evaluator.call_llm_json",
            mock_call_llm_json,
        )

        state = _make_state_with_good_content()
        result = await evaluate_and_improve_slides(state)

        evals = result.metadata["slide_evaluations"]
        assert len(evals) == 3
        for ev in evals:
            assert "slide_id" in ev
            assert "is_valid" in ev
            assert "scores" in ev
            assert "overall_score" in ev
            assert "critic_feedback" in ev
            assert "intent_check" in ev
            assert "validation_failures" in ev

    @pytest.mark.asyncio
    async def test_scores_in_evaluation(self, monkeypatch):
        """Verify score structure in evaluations."""
        async def mock_call_llm_json(system_prompt: str, user_prompt: str) -> dict:
            if "repetition detector" in system_prompt.lower():
                return {"has_overlap": False, "overlapping_ideas": []}
            if "quality scorer" in system_prompt.lower():
                return {"specificity": 4, "mechanism": 5, "uniqueness": 4, "clarity": 5}
            if "tier-1" in system_prompt.lower():
                return {"accepted": True, "reason": "ok", "weaknesses": []}
            if "intent enforcer" in system_prompt.lower():
                return {"compliant": True, "reason": "ok"}
            return {}

        monkeypatch.setattr(
            "pipeline.slide_evaluator.call_llm_json",
            mock_call_llm_json,
        )

        state = _make_state_with_good_content()
        result = await evaluate_and_improve_slides(state)

        ev = result.metadata["slide_evaluations"][0]
        scores = ev["scores"]
        assert "specificity" in scores
        assert "mechanism" in scores
        assert "uniqueness" in scores
        assert "clarity" in scores
        assert "overall" in scores
        assert 1 <= scores["overall"] <= 5

    @pytest.mark.asyncio
    async def test_empty_slides_returns_unchanged(self, monkeypatch):
        """Empty structured_slides should pass through unchanged."""
        state = _make_state()
        # No structured_slides
        result = await evaluate_and_improve_slides(state)
        assert result.structured_slides is None

    @pytest.mark.asyncio
    async def test_image_path_preserved(self, monkeypatch):
        """Image paths should be preserved through evaluation."""
        async def mock_call_llm_json(system_prompt: str, user_prompt: str) -> dict:
            if "repetition detector" in system_prompt.lower():
                return {"has_overlap": False, "overlapping_ideas": []}
            if "quality scorer" in system_prompt.lower():
                return {"specificity": 5, "mechanism": 5, "uniqueness": 5, "clarity": 5}
            if "tier-1" in system_prompt.lower():
                return {"accepted": True, "reason": "ok", "weaknesses": []}
            if "intent enforcer" in system_prompt.lower():
                return {"compliant": True, "reason": "ok"}
            return {}

        monkeypatch.setattr(
            "pipeline.slide_evaluator.call_llm_json",
            mock_call_llm_json,
        )

        state = _make_state_with_good_content()
        # Add image_path to a slide
        slides = list(state.structured_slides)
        slides[1] = {**slides[1], "image_path": "/tmp/test_image.png"}
        state = state.model_copy(update={"structured_slides": slides})

        result = await evaluate_and_improve_slides(state)
        assert result.structured_slides[1].get("image_path") == "/tmp/test_image.png"

    @pytest.mark.asyncio
    async def test_llm_failures_handled_gracefully(self, monkeypatch):
        """LLM failures in evaluation should not crash the pipeline."""
        async def mock_call_llm_json(system_prompt: str, user_prompt: str) -> dict:
            raise RuntimeError("LLM unavailable")

        monkeypatch.setattr(
            "pipeline.slide_evaluator.call_llm_json",
            mock_call_llm_json,
        )

        state = _make_state_with_good_content()
        result = await evaluate_and_improve_slides(state)

        # Should still return slides (with default scores)
        assert result.structured_slides is not None
        assert len(result.structured_slides) == 3

    @pytest.mark.asyncio
    async def test_previous_content_grows_across_slides(self, monkeypatch):
        """Verify semantic checks receive growing context of previous slides."""
        semantic_prompts = []

        async def mock_call_llm_json(system_prompt: str, user_prompt: str) -> dict:
            if "repetition detector" in system_prompt.lower():
                semantic_prompts.append(user_prompt)
                return {"has_overlap": False, "overlapping_ideas": []}
            if "quality scorer" in system_prompt.lower():
                return {"specificity": 5, "mechanism": 5, "uniqueness": 5, "clarity": 5}
            if "tier-1" in system_prompt.lower():
                return {"accepted": True, "reason": "ok", "weaknesses": []}
            if "intent enforcer" in system_prompt.lower():
                return {"compliant": True, "reason": "ok"}
            return {}

        monkeypatch.setattr(
            "pipeline.slide_evaluator.call_llm_json",
            mock_call_llm_json,
        )

        state = _make_state_with_good_content()
        await evaluate_and_improve_slides(state)

        # First slide has no previous context → no semantic check called
        # Slides 2+ should have semantic checks with previous content
        assert len(semantic_prompts) >= 1  # At least one slide checked
        # Last semantic prompt should mention more previous slide IDs
        if len(semantic_prompts) >= 2:
            # Second prompt should reference slides 0 and 1, first only slide 0
            assert "Slide 1" in semantic_prompts[-1]
            assert "Slide 0" in semantic_prompts[-1]


# ═══════════════════════════════════════════════════════════════════════
# Integration: deterministic check + scoring interaction
# ═══════════════════════════════════════════════════════════════════════

class TestIntegration:
    def test_banned_phrase_constants(self):
        """Verify GENERIC_PHRASES list is non-empty and lowercase."""
        assert len(GENERIC_PHRASES) > 0
        for phrase in GENERIC_PHRASES:
            assert phrase == phrase.lower(), f"Phrase not lowercase: {phrase}"

    def test_min_bullet_words_is_reasonable(self):
        assert MIN_BULLET_WORDS >= 4
        assert MIN_BULLET_WORDS <= 10

    def test_min_acceptable_score_is_strict(self):
        assert MIN_ACCEPTABLE_SCORE >= 3.5
        assert MIN_ACCEPTABLE_SCORE <= 5.0

    def test_max_improvement_attempts_bounded(self):
        assert 1 <= MAX_IMPROVEMENT_ATTEMPTS <= 5
