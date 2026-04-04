"""Tests for the multi-stage content pipeline (Phases 1-5).

Tests cover:
- Phase 1: Content generation with mechanism-driven output
- Phase 2: Self-validation (repetition, generic, depth)
- Phase 3: Critic loop (investor evaluation)
- Phase 4: Slide intent enforcement
- Phase 5: Intelligence report generation
- Integration: Full multi-stage pipeline flow
"""

import json
import pytest

from models.presentation_state import PresentationState
from pipeline.multi_stage_content import (
    MAX_ATTEMPTS,
    _flatten_content,
    _get_schema_for_type,
    generate_multi_stage_content,
)
from pipeline.intelligence_report import (
    generate_intelligence_report,
    _fallback_report,
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


def _make_state_with_content() -> PresentationState:
    """Create a PresentationState with pre-generated content."""
    state = _make_state()
    state = state.model_copy(update={
        "structured_slides": [
            {
                "slide_id": 0,
                "type": "title_slide",
                "content": {
                    "title": "AI Fraud Detection",
                    "subtitle": "Behavioral biometrics for real-time banking security",
                    "presenter": "",
                },
            },
            {
                "slide_id": 1,
                "type": "problem_slide",
                "content": {
                    "title": "The Fraud Problem",
                    "cards": [
                        {"icon": "⚠", "label": "Card-not-present fraud",
                         "description": "CNP fraud rose 35% in 2024 due to synthetic identity attacks"},
                        {"icon": "🔓", "label": "Account takeover",
                         "description": "Credential stuffing bots attempt 100M+ logins daily across top-10 banks"},
                        {"icon": "⏱", "label": "Detection latency",
                         "description": "Average rule-based systems take 48 hours to flag suspicious transactions"},
                    ],
                },
            },
            {
                "slide_id": 2,
                "type": "feature_slide",
                "content": {
                    "title": "Behavioral Biometric Engine",
                    "features": [
                        {"icon": "⚡", "label": "Keystroke dynamics",
                         "description": "Measures typing rhythm and dwell-time patterns per user"},
                        {"icon": "📊", "label": "Mouse trajectory analysis",
                         "description": "Tracks cursor path entropy to detect bot-driven sessions"},
                        {"icon": "🔒", "label": "Device fingerprinting",
                         "description": "Combines 40+ signals (GPU hash, font list, WebGL) for session identity"},
                    ],
                },
            },
        ],
    })
    return state


# Async mock helper
class _FakeLLMResponse:
    """Mock for LLM calls that returns canned JSON."""

    def __init__(self, responses: list[dict]):
        self._responses = list(responses)
        self._call_count = 0

    async def __call__(self, system_prompt: str, user_prompt: str) -> dict:
        idx = min(self._call_count, len(self._responses) - 1)
        self._call_count += 1
        return self._responses[idx]


# ═══════════════════════════════════════════════════════════════════════
# Unit tests: helpers
# ═══════════════════════════════════════════════════════════════════════

class TestFlattenContent:
    def test_flat_strings(self):
        content = {"title": "Hello", "body": "World"}
        result = _flatten_content(content)
        assert "title: Hello" in result
        assert "body: World" in result

    def test_nested_list_of_dicts(self):
        content = {
            "features": [
                {"label": "Speed", "description": "Fast"},
                {"label": "Security", "description": "Safe"},
            ]
        }
        result = _flatten_content(content)
        assert "Speed" in result
        assert "Safe" in result

    def test_list_of_strings(self):
        content = {"bullets": ["Point 1", "Point 2"]}
        result = _flatten_content(content)
        assert "Point 1" in result
        assert "Point 2" in result

    def test_empty_content(self):
        result = _flatten_content({})
        assert result == ""


class TestGetSchemaForType:
    def test_known_types(self):
        for slide_type in [
            "title_slide", "section_header", "agenda_slide",
            "problem_slide", "stats_slide", "feature_slide",
            "comparison_slide", "timeline_slide", "example_slide",
            "conclusion_slide", "cta_slide", "quote_slide",
            "image_slide", "thank_you_slide",
        ]:
            schema = _get_schema_for_type(slide_type)
            assert "Return:" in schema
            assert "{" in schema

    def test_unknown_type_returns_fallback(self):
        schema = _get_schema_for_type("nonexistent_slide")
        assert "title" in schema
        assert "body" in schema


# ═══════════════════════════════════════════════════════════════════════
# Unit tests: multi-stage content generation
# ═══════════════════════════════════════════════════════════════════════

class TestMultiStageGeneration:
    @pytest.mark.asyncio
    async def test_generates_content_for_all_slides(self, monkeypatch):
        """Verify that multi-stage generates content for every slide in the plan."""
        call_count = 0

        async def mock_call_llm_json(system_prompt: str, user_prompt: str) -> dict:
            nonlocal call_count
            call_count += 1

            # Phase 1: content generation
            if "content architect" in system_prompt.lower():
                return {
                    "title": f"Slide Content {call_count}",
                    "features": [
                        {"icon": "⚡", "label": "Feature A",
                         "description": "Specific mechanism detail"},
                    ],
                }
            # Phase 2: validation
            if "validator" in system_prompt.lower():
                return {"passed": True, "reason": "all checks passed"}
            # Phase 3: critic
            if "investor" in system_prompt.lower():
                return {"accepted": True, "reason": "specific and convincing"}
            # Phase 4: intent enforcement
            if "intent enforcer" in system_prompt.lower():
                return {"compliant": True, "reason": "matches section"}
            return {}

        monkeypatch.setattr(
            "pipeline.multi_stage_content.call_llm_json",
            mock_call_llm_json,
        )

        state = _make_state()
        result = await generate_multi_stage_content(state)

        assert result.structured_slides is not None
        assert len(result.structured_slides) == len(state.slide_plan)
        for slide in result.structured_slides:
            assert "content" in slide
            assert "type" in slide
            assert "slide_id" in slide

    @pytest.mark.asyncio
    async def test_regenerates_on_validation_failure(self, monkeypatch):
        """Verify that content is regenerated when validation fails."""
        generation_count = 0

        async def mock_call_llm_json(system_prompt: str, user_prompt: str) -> dict:
            nonlocal generation_count

            if "content architect" in system_prompt.lower():
                generation_count += 1
                return {"title": f"Attempt {generation_count}", "body": "content"}
            if "validator" in system_prompt.lower():
                # Fail first attempt, pass second
                if generation_count <= 1:
                    return {"passed": False, "reason": "too generic"}
                return {"passed": True, "reason": "all checks passed"}
            if "investor" in system_prompt.lower():
                return {"accepted": True, "reason": "ok"}
            if "intent enforcer" in system_prompt.lower():
                return {"compliant": True, "reason": "ok"}
            return {}

        monkeypatch.setattr(
            "pipeline.multi_stage_content.call_llm_json",
            mock_call_llm_json,
        )

        state = _make_state(slide_plan=[
            {"slide_id": 0, "section": "intro", "purpose": "Title", "type": "title_slide"},
        ])
        result = await generate_multi_stage_content(state)

        assert result.structured_slides is not None
        assert len(result.structured_slides) == 1
        # Should have been regenerated (attempt 2+)
        assert generation_count >= 2

    @pytest.mark.asyncio
    async def test_regenerates_on_critic_rejection(self, monkeypatch):
        """Verify that content is regenerated when critic rejects."""
        generation_count = 0

        async def mock_call_llm_json(system_prompt: str, user_prompt: str) -> dict:
            nonlocal generation_count

            if "content architect" in system_prompt.lower():
                generation_count += 1
                return {"title": f"Content {generation_count}", "body": "data"}
            if "validator" in system_prompt.lower():
                return {"passed": True, "reason": "ok"}
            if "investor" in system_prompt.lower():
                # Reject first attempt
                if generation_count <= 1:
                    return {"accepted": False, "reason": "too vague"}
                return {"accepted": True, "reason": "specific enough"}
            if "intent enforcer" in system_prompt.lower():
                return {"compliant": True, "reason": "ok"}
            return {}

        monkeypatch.setattr(
            "pipeline.multi_stage_content.call_llm_json",
            mock_call_llm_json,
        )

        state = _make_state(slide_plan=[
            {"slide_id": 0, "section": "intro", "purpose": "Title", "type": "title_slide"},
        ])
        result = await generate_multi_stage_content(state)
        assert generation_count >= 2

    @pytest.mark.asyncio
    async def test_regenerates_on_intent_violation(self, monkeypatch):
        """Verify that content is regenerated on intent violation."""
        generation_count = 0

        async def mock_call_llm_json(system_prompt: str, user_prompt: str) -> dict:
            nonlocal generation_count

            if "content architect" in system_prompt.lower():
                generation_count += 1
                return {"title": "Content", "body": "data"}
            if "validator" in system_prompt.lower():
                return {"passed": True, "reason": "ok"}
            if "investor" in system_prompt.lower():
                return {"accepted": True, "reason": "ok"}
            if "intent enforcer" in system_prompt.lower():
                # Fail first, pass second
                if generation_count <= 1:
                    return {"compliant": False, "reason": "solution content in problem slide"}
                return {"compliant": True, "reason": "aligned"}
            return {}

        monkeypatch.setattr(
            "pipeline.multi_stage_content.call_llm_json",
            mock_call_llm_json,
        )

        state = _make_state(slide_plan=[
            {"slide_id": 1, "section": "problem", "purpose": "Problem", "type": "problem_slide"},
        ])
        result = await generate_multi_stage_content(state)
        assert generation_count >= 2

    @pytest.mark.asyncio
    async def test_max_attempts_exhaustion(self, monkeypatch):
        """After MAX_ATTEMPTS failures, uses best-effort content."""
        generation_count = 0

        async def mock_call_llm_json(system_prompt: str, user_prompt: str) -> dict:
            nonlocal generation_count

            if "content architect" in system_prompt.lower():
                generation_count += 1
                return {"title": "Fallback", "body": "best effort"}
            if "validator" in system_prompt.lower():
                return {"passed": False, "reason": "always fails"}
            if "investor" in system_prompt.lower():
                return {"accepted": True, "reason": "ok"}
            if "intent enforcer" in system_prompt.lower():
                return {"compliant": True, "reason": "ok"}
            return {}

        monkeypatch.setattr(
            "pipeline.multi_stage_content.call_llm_json",
            mock_call_llm_json,
        )

        state = _make_state(slide_plan=[
            {"slide_id": 0, "section": "intro", "purpose": "Title", "type": "title_slide"},
        ])
        result = await generate_multi_stage_content(state)

        # Should still produce output even after exhausting attempts
        assert result.structured_slides is not None
        assert len(result.structured_slides) == 1
        assert generation_count == MAX_ATTEMPTS

    @pytest.mark.asyncio
    async def test_empty_slide_plan(self, monkeypatch):
        """No slides → no content generated."""
        state = _make_state(slide_plan=[])
        result = await generate_multi_stage_content(state)
        assert result.structured_slides is None or result.structured_slides == []

    @pytest.mark.asyncio
    async def test_previous_content_context_grows(self, monkeypatch):
        """Verify that previous slide content is passed to later slides."""
        user_prompts_seen = []

        async def mock_call_llm_json(system_prompt: str, user_prompt: str) -> dict:
            if "content architect" in system_prompt.lower():
                user_prompts_seen.append(user_prompt)
                return {"title": "Content", "body": "data"}
            if "validator" in system_prompt.lower():
                return {"passed": True, "reason": "ok"}
            if "investor" in system_prompt.lower():
                return {"accepted": True, "reason": "ok"}
            if "intent enforcer" in system_prompt.lower():
                return {"compliant": True, "reason": "ok"}
            return {}

        monkeypatch.setattr(
            "pipeline.multi_stage_content.call_llm_json",
            mock_call_llm_json,
        )

        state = _make_state()
        await generate_multi_stage_content(state)

        # First slide should have "None yet"
        assert "None yet" in user_prompts_seen[0]
        # Third slide should reference previous content
        assert "None yet" not in user_prompts_seen[2]

    @pytest.mark.asyncio
    async def test_llm_failure_produces_fallback_content(self, monkeypatch):
        """LLM failure in content generation produces fallback."""
        async def mock_call_llm_json(system_prompt: str, user_prompt: str) -> dict:
            if "content architect" in system_prompt.lower():
                raise RuntimeError("LLM unavailable")
            # Validation/critic/intent pass by default on error
            return {"passed": True, "accepted": True, "compliant": True, "reason": "ok"}

        monkeypatch.setattr(
            "pipeline.multi_stage_content.call_llm_json",
            mock_call_llm_json,
        )

        state = _make_state(slide_plan=[
            {"slide_id": 0, "section": "intro", "purpose": "Title slide", "type": "title_slide"},
        ])
        result = await generate_multi_stage_content(state)

        assert result.structured_slides is not None
        assert len(result.structured_slides) == 1
        # Fallback content
        assert result.structured_slides[0]["content"]["body"] == "Content unavailable"


# ═══════════════════════════════════════════════════════════════════════
# Unit tests: intelligence report
# ═══════════════════════════════════════════════════════════════════════

class TestIntelligenceReport:
    @pytest.mark.asyncio
    async def test_generates_report(self, monkeypatch):
        """Verify intelligence report is generated and attached to state."""
        async def mock_call_llm(system_prompt: str, user_prompt: str) -> str:
            return "# Narrato Phase 1 Intelligence Report\n\n## 1. Input Understanding\nTest report content"

        monkeypatch.setattr(
            "pipeline.intelligence_report.call_llm",
            mock_call_llm,
        )

        state = _make_state_with_content()
        result = await generate_intelligence_report(state)

        assert result.intelligence_report is not None
        assert "Intelligence Report" in result.intelligence_report

    @pytest.mark.asyncio
    async def test_report_includes_required_sections(self, monkeypatch):
        """Verify the report prompt requests all 9 sections."""
        captured_prompts = []

        async def mock_call_llm(system_prompt: str, user_prompt: str) -> str:
            captured_prompts.append(user_prompt)
            return "# Report"

        monkeypatch.setattr(
            "pipeline.intelligence_report.call_llm",
            mock_call_llm,
        )

        state = _make_state_with_content()
        await generate_intelligence_report(state)

        prompt = captured_prompts[0]
        for section in [
            "Input Understanding",
            "Slide Intent Handling",
            "Content Strategy",
            "Repetition Avoidance",
            "Validation Decisions",
            "Critic Evaluation",
            "Improvements Made",
            "Final Quality Justification",
            "Limitations",
        ]:
            assert section in prompt, f"Missing section: {section}"

    @pytest.mark.asyncio
    async def test_fallback_report_on_llm_failure(self, monkeypatch):
        """Verify fallback report is generated when LLM fails."""
        async def mock_call_llm(system_prompt: str, user_prompt: str) -> str:
            raise RuntimeError("LLM unavailable")

        monkeypatch.setattr(
            "pipeline.intelligence_report.call_llm",
            mock_call_llm,
        )

        state = _make_state_with_content()
        result = await generate_intelligence_report(state)

        assert result.intelligence_report is not None
        assert "Intelligence Report" in result.intelligence_report
        assert "fallback" in result.intelligence_report.lower()

    def test_fallback_report_structure(self):
        """Verify fallback report includes all 9 sections."""
        state = _make_state_with_content()
        report = _fallback_report(state)

        for section in [
            "Input Understanding",
            "Slide Intent Handling",
            "Content Strategy",
            "Repetition Avoidance",
            "Validation Decisions",
            "Critic Evaluation",
            "Improvements Made",
            "Final Quality Justification",
            "Limitations",
        ]:
            assert section in report, f"Missing section in fallback: {section}"

    @pytest.mark.asyncio
    async def test_no_slides_skips_report(self, monkeypatch):
        """No structured slides → report generation skipped."""
        state = _make_state()
        # No structured_slides set
        result = await generate_intelligence_report(state)
        assert result.intelligence_report is None


# ═══════════════════════════════════════════════════════════════════════
# Integration tests: state model
# ═══════════════════════════════════════════════════════════════════════

class TestStateModel:
    def test_intelligence_report_field_exists(self):
        """PresentationState has the intelligence_report field."""
        state = PresentationState(topic="Test")
        assert state.intelligence_report is None

    def test_intelligence_report_can_be_set(self):
        """intelligence_report field can be populated via model_copy."""
        state = PresentationState(topic="Test")
        updated = state.model_copy(update={"intelligence_report": "# Report"})
        assert updated.intelligence_report == "# Report"
