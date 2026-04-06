"""Tests for the strict-mode pipeline (schema parser, planner, content, validator)."""

import pytest
from unittest.mock import AsyncMock, patch

from models.presentation_state import PresentationState
from pipeline.schema_parser import UserSchema, parse_user_schema
from pipeline.state_builder import build_state, StrictSchemaError
from pipeline.strict_slide_planner import plan_slides_strict
from pipeline.content_validator import (
    _run_checks,
    _content_to_text,
    _set_validation_status,
    validate_content,
    ValidationError,
    MAX_WORDS_PER_FIELD,
)


# =====================================================================
# Phase 1: UserSchema model
# =====================================================================

class TestUserSchema:
    def test_schema_defaults(self):
        schema = UserSchema(topic="food commodities")
        assert schema.topic == "food commodities"
        assert schema.examples_required == 0
        assert schema.fields_required == []
        assert schema.forbidden_content == []
        assert schema.is_structured_request is False

    def test_schema_full(self):
        schema = UserSchema(
            topic="food commodities",
            examples_required=3,
            fields_required=["origin", "history"],
            forbidden_content=["market analysis", "investment"],
            is_structured_request=True,
        )
        assert schema.examples_required == 3
        assert schema.fields_required == ["origin", "history"]
        assert len(schema.forbidden_content) == 2

    def test_schema_to_dict(self):
        schema = UserSchema(
            topic="test", examples_required=2,
            fields_required=["a", "b"], is_structured_request=True,
        )
        d = schema.model_dump()
        assert d["topic"] == "test"
        assert d["examples_required"] == 2


# =====================================================================
# Phase 1: parse_user_schema (LLM mocked)
# =====================================================================

class TestParseUserSchema:
    @pytest.mark.asyncio
    async def test_structured_request_returns_schema(self):
        mock_response = {
            "topic": "food commodities",
            "examples_required": 3,
            "fields_required": ["origin", "history"],
            "forbidden_content": ["market analysis"],
            "is_structured_request": True,
        }
        with patch("pipeline.schema_parser.call_llm_json", new_callable=AsyncMock, return_value=mock_response):
            result = await parse_user_schema("food commodities with 3 examples, origin, history")
        assert result is not None
        assert result.topic == "food commodities"
        assert result.examples_required == 3
        assert result.fields_required == ["origin", "history"]

    @pytest.mark.asyncio
    async def test_generic_request_returns_none(self):
        mock_response = {
            "topic": "AI",
            "examples_required": 0,
            "fields_required": [],
            "forbidden_content": [],
            "is_structured_request": False,
        }
        with patch("pipeline.schema_parser.call_llm_json", new_callable=AsyncMock, return_value=mock_response):
            result = await parse_user_schema("make me a presentation about AI")
        assert result is None

    @pytest.mark.asyncio
    async def test_llm_failure_returns_none(self):
        with patch("pipeline.schema_parser.call_llm_json", new_callable=AsyncMock, side_effect=Exception("LLM down")):
            result = await parse_user_schema("anything")
        assert result is None

    @pytest.mark.asyncio
    async def test_no_examples_returns_none(self):
        mock_response = {
            "topic": "test",
            "examples_required": 0,
            "fields_required": ["origin"],
            "forbidden_content": [],
            "is_structured_request": True,
        }
        with patch("pipeline.schema_parser.call_llm_json", new_callable=AsyncMock, return_value=mock_response):
            result = await parse_user_schema("test with origin")
        assert result is None


# =====================================================================
# Phase 2 & 8: PresentationState + build_state
# =====================================================================

class TestStrictState:
    def test_state_has_strict_fields(self):
        state = PresentationState(topic="Test")
        assert state.user_schema is None
        assert state.generation_mode is None

    def test_state_strict_fields_set(self):
        state = PresentationState(
            topic="Test",
            user_schema={"topic": "Test", "examples_required": 2, "fields_required": ["a"]},
            generation_mode="strict",
        )
        assert state.generation_mode == "strict"
        assert state.user_schema["examples_required"] == 2

    def test_build_state_default_mode(self):
        state = build_state({"topic": "AI"})
        assert state.generation_mode == "default"
        assert state.user_schema is None

    def test_build_state_strict_mode(self):
        schema = UserSchema(
            topic="food commodities",
            examples_required=3,
            fields_required=["origin", "history"],
            is_structured_request=True,
        )
        state = build_state({"topic": "ignored"}, user_schema=schema)
        assert state.generation_mode == "strict"
        assert state.topic == "food commodities"
        assert state.examples_count == 3
        # title + definition + 3 examples + summary = 6, EXACT (no clamping)
        assert state.slide_count == 6
        assert state.user_schema is not None

    def test_build_state_strict_exact_slide_count_no_min_guard(self):
        """With 1 example: 2 + 1 + 1 = 4.  No min(5) guard in strict mode."""
        schema = UserSchema(
            topic="test_topic", examples_required=1,
            fields_required=["field_a"], is_structured_request=True,
        )
        state = build_state({}, user_schema=schema)
        # EXACT: 2 + 1 + 1 = 4, NOT clamped to 5
        assert state.slide_count == 4

    def test_build_state_strict_fails_without_topic(self):
        schema = UserSchema(
            topic="",
            examples_required=2,
            fields_required=["a"],
            is_structured_request=True,
        )
        with pytest.raises(StrictSchemaError, match="topic"):
            build_state({}, user_schema=schema)

    def test_build_state_strict_fails_without_examples(self):
        schema = UserSchema(
            topic="test",
            examples_required=0,
            fields_required=["a"],
            is_structured_request=True,
        )
        with pytest.raises(StrictSchemaError, match="examples_required"):
            build_state({}, user_schema=schema)

    def test_build_state_strict_fails_without_fields(self):
        schema = UserSchema(
            topic="test",
            examples_required=2,
            fields_required=[],
            is_structured_request=True,
        )
        with pytest.raises(StrictSchemaError, match="fields_required"):
            build_state({}, user_schema=schema)


# =====================================================================
# Phase 3: Strict Slide Planner
# =====================================================================

class TestStrictSlidePlanner:
    def _make_strict_state(self, n_examples=3, fields=None):
        schema = UserSchema(
            topic="food commodities",
            examples_required=n_examples,
            fields_required=fields or ["origin", "history"],
            is_structured_request=True,
        )
        return build_state({"tone": "professional"}, user_schema=schema)

    def test_slide_count_matches(self):
        state = self._make_strict_state(n_examples=3)
        state = plan_slides_strict(state)
        # title + definition + 3 examples + summary = 6
        assert len(state.slide_plan) == 6

    def test_first_slide_is_title(self):
        state = self._make_strict_state()
        state = plan_slides_strict(state)
        assert state.slide_plan[0]["type"] == "title_slide"

    def test_second_slide_is_definition(self):
        state = self._make_strict_state()
        state = plan_slides_strict(state)
        assert state.slide_plan[1]["type"] == "feature_slide"
        assert state.slide_plan[1]["purpose"] == "Definition of topic"

    def test_example_slides_exact_count(self):
        state = self._make_strict_state(n_examples=5)
        state = plan_slides_strict(state)
        example_slides = [s for s in state.slide_plan if s["type"] == "example_detail_slide"]
        assert len(example_slides) == 5

    def test_last_slide_is_summary(self):
        state = self._make_strict_state()
        state = plan_slides_strict(state)
        assert state.slide_plan[-1]["type"] == "conclusion_slide"

    def test_no_section_headers(self):
        state = self._make_strict_state()
        state = plan_slides_strict(state)
        types = [s["type"] for s in state.slide_plan]
        assert "section_header" not in types

    def test_no_cta_slide(self):
        state = self._make_strict_state()
        state = plan_slides_strict(state)
        types = [s["type"] for s in state.slide_plan]
        assert "cta_slide" not in types

    def test_no_agenda_slide(self):
        state = self._make_strict_state()
        state = plan_slides_strict(state)
        types = [s["type"] for s in state.slide_plan]
        assert "agenda_slide" not in types

    def test_raises_without_schema(self):
        state = PresentationState(topic="test")
        with pytest.raises(ValueError, match="user_schema"):
            plan_slides_strict(state)

    def test_raises_with_zero_examples(self):
        state = PresentationState(
            topic="test",
            user_schema={"examples_required": 0},
            generation_mode="strict",
        )
        with pytest.raises(ValueError, match="examples_required"):
            plan_slides_strict(state)

    def test_slide_ids_sequential(self):
        state = self._make_strict_state(n_examples=4)
        state = plan_slides_strict(state)
        ids = [s["slide_id"] for s in state.slide_plan]
        assert ids == list(range(len(ids)))

    def test_exact_slide_count_formula(self):
        """Slide count is EXACTLY 2 + N + 1 for any N."""
        for n in [1, 2, 3, 5, 10]:
            state = self._make_strict_state(n_examples=n)
            state = plan_slides_strict(state)
            assert len(state.slide_plan) == 2 + n + 1


# =====================================================================
# Phase 5: Content Validator checks (assertion-only, non-corrective)
# =====================================================================

class TestContentValidator:
    def _make_valid_state(self, n_examples=3, fields=None):
        fields = fields or ["origin", "history"]
        schema_dict = {
            "topic": "food commodities",
            "examples_required": n_examples,
            "fields_required": fields,
            "forbidden_content": ["market analysis", "investment"],
            "is_structured_request": True,
        }
        slides = [
            {"slide_id": 0, "type": "title_slide", "content": {"title": "Food", "subtitle": "Overview"}},
            {"slide_id": 1, "type": "feature_slide", "content": {"title": "Definition", "features": []}},
        ]
        for i in range(n_examples):
            content = {"name": f"Example {i+1}"}
            for f in fields:
                content[f] = f"Short {f} info here"
            slides.append({"slide_id": 2 + i, "type": "example_detail_slide", "content": content})

        slides.append({
            "slide_id": 2 + n_examples,
            "type": "conclusion_slide",
            "content": {"title": "Summary", "bullets": ["b1"], "key_takeaway": "Key insight"},
        })

        return PresentationState(
            topic="food commodities",
            user_schema=schema_dict,
            generation_mode="strict",
            structured_slides=slides,
            slide_plan=[{"slide_id": s["slide_id"], "type": s["type"]} for s in slides],
        )

    def test_valid_state_passes(self):
        state = self._make_valid_state()
        errors = _run_checks(state)
        assert errors == []

    def test_validate_content_passes_valid(self):
        """validate_content returns state with passed status on valid input."""
        state = self._make_valid_state()
        result = validate_content(state)
        assert result.metadata["validation_status"] == "passed"

    def test_validate_content_raises_on_invalid(self):
        """validate_content raises ValidationError on violations — no fixing."""
        state = self._make_valid_state()
        slides = list(state.structured_slides)
        bad_content = dict(slides[2]["content"])
        del bad_content["history"]
        slides[2] = {**slides[2], "content": bad_content}
        state = state.model_copy(update={"structured_slides": slides})
        with pytest.raises(ValidationError):
            validate_content(state)

    def test_wrong_slide_count_detected(self):
        state = self._make_valid_state()
        # Remove one slide
        slides = state.structured_slides[:-1]
        state = state.model_copy(update={"structured_slides": slides})
        errors = _run_checks(state)
        assert any("Slide count mismatch" in e for e in errors)

    def test_missing_field_detected(self):
        state = self._make_valid_state()
        slides = list(state.structured_slides)
        bad_content = dict(slides[2]["content"])
        del bad_content["history"]
        slides[2] = {**slides[2], "content": bad_content}
        state = state.model_copy(update={"structured_slides": slides})
        errors = _run_checks(state)
        assert any("missing required field 'history'" in e for e in errors)

    def test_forbidden_content_detected(self):
        state = self._make_valid_state()
        slides = list(state.structured_slides)
        bad_content = dict(slides[2]["content"])
        bad_content["origin"] = "market analysis of wheat origins"
        slides[2] = {**slides[2], "content": bad_content}
        state = state.model_copy(update={"structured_slides": slides})
        errors = _run_checks(state)
        assert any("forbidden content" in e for e in errors)

    def test_word_count_exceeded_detected(self):
        state = self._make_valid_state()
        slides = list(state.structured_slides)
        bad_content = dict(slides[2]["content"])
        bad_content["origin"] = " ".join(["word"] * (MAX_WORDS_PER_FIELD + 1))
        slides[2] = {**slides[2], "content": bad_content}
        state = state.model_copy(update={"structured_slides": slides})
        errors = _run_checks(state)
        assert any(f"exceeds {MAX_WORDS_PER_FIELD} words" in e for e in errors)

    def test_example_count_mismatch_detected(self):
        state = self._make_valid_state(n_examples=3)
        slides = list(state.structured_slides)
        # Remove one example slide
        slides.pop(3)
        state = state.model_copy(update={"structured_slides": slides})
        errors = _run_checks(state)
        assert any("Example count mismatch" in e for e in errors)

    def test_no_schema_returns_empty(self):
        state = PresentationState(topic="test")
        errors = _run_checks(state)
        assert errors == []

    def test_extra_keys_detected(self):
        """Extra keys in example content should be flagged."""
        state = self._make_valid_state()
        slides = list(state.structured_slides)
        bad_content = dict(slides[2]["content"])
        bad_content["description"] = "should not be here"
        slides[2] = {**slides[2], "content": bad_content}
        state = state.model_copy(update={"structured_slides": slides})
        errors = _run_checks(state)
        assert any("unexpected extra keys" in e for e in errors)


# =====================================================================
# Helper tests
# =====================================================================

class TestHelpers:
    def test_content_to_text_strings(self):
        content = {"title": "Hello", "body": "World"}
        assert "Hello" in _content_to_text(content)
        assert "World" in _content_to_text(content)

    def test_content_to_text_nested(self):
        content = {"features": [{"label": "Foo", "desc": "Bar"}]}
        text = _content_to_text(content)
        assert "Foo" in text
        assert "Bar" in text

    def test_set_validation_status(self):
        state = PresentationState(topic="test")
        updated = _set_validation_status(state, "passed")
        assert updated.metadata["validation_status"] == "passed"

    def test_set_validation_status_with_errors(self):
        state = PresentationState(topic="test")
        updated = _set_validation_status(state, "partial", ["err1"])
        assert updated.metadata["validation_status"] == "partial"
        assert "err1" in updated.metadata["validation_errors"]


# =====================================================================
# Phase 7: Visual rendering with strict slides (replaces PPT test)
# =====================================================================

class TestStrictSlideVisualRendering:
    @pytest.mark.asyncio
    async def test_visual_pipeline_with_strict_slides(self):
        """Verify that a strict-mode state renders through the visual design + template pipeline."""
        from pipeline.dynamic_composition_engine import run_dynamic_composition_engine

        slides = [
            {"slide_id": 0, "type": "title_slide",
             "content": {"title": "Food Commodities", "subtitle": "Overview", "presenter": ""}, "image_path": None},
            {"slide_id": 1, "type": "feature_slide",
             "content": {"title": "What is Food Commodities?",
                         "features": [{"icon": "\U0001F4D6", "label": "Definition",
                                       "description": "Basic agricultural products traded globally."}]},
             "image_path": None},
            {"slide_id": 2, "type": "example_detail_slide",
             "content": {"name": "Rice", "origin": "Southeast Asia", "history": "Cultivated for over 5000 years",
                         "image_url": "file:///tmp/test_rice.png"},
             "image_path": None},
            {"slide_id": 3, "type": "example_detail_slide",
             "content": {"name": "Wheat", "origin": "Fertile Crescent", "history": "Domesticated around 10000 years ago",
                         "image_url": "file:///tmp/test_wheat.png"},
             "image_path": None},
            {"slide_id": 4, "type": "conclusion_slide",
             "content": {"title": "Summary", "bullets": ["Rice", "Wheat"], "key_takeaway": "Key food staples."},
             "image_path": None},
        ]

        designs, html_slides = await run_dynamic_composition_engine(slides, state_theme="modern")
        assert len(designs) == 5
        assert len(html_slides) == 5

        for html in html_slides:
            assert "<!DOCTYPE html>" in html
            assert "slide-frame" in html
            assert "data-theme=" in html


# =====================================================================
# Default mode preservation
# =====================================================================

class TestDefaultModePreserved:
    def test_build_state_default_unchanged(self):
        """Generic signals produce the same state as before."""
        state = build_state({"topic": "AI", "slide_count": 10, "tone": "casual"})
        assert state.topic == "AI"
        assert state.tone == "casual"
        assert state.slide_count == 10
        assert state.generation_mode == "default"
        assert state.user_schema is None

    def test_default_pipeline_still_works(self):
        """The default planner still works for default-mode states."""
        from pipeline.slide_planner import plan_slides
        from pipeline.slide_type_assigner import assign_slide_types
        from pipeline.story_generator import _default_story

        state = build_state({
            "topic": "AI in Healthcare",
            "presentation_type": "pitch",
            "slide_count": 10,
            "sections": ["intro", "problem", "solution", "benefits", "conclusion"],
        })
        state = state.model_copy(update={"story": _default_story(state)})
        state = plan_slides(state)
        state = assign_slide_types(state)
        assert state.slide_plan[0]["type"] == "title_slide"
        assert state.slide_plan[-1]["type"] == "cta_slide"


# =====================================================================
# Strict content structurer (field-level generation, mocked LLM)
# =====================================================================

class TestStrictContentStructurer:
    @pytest.mark.asyncio
    async def test_per_field_generation(self):
        """Each field is generated independently via call_llm."""
        from pipeline.strict_content_structurer import generate_strict_content

        schema = UserSchema(
            topic="food commodities",
            examples_required=2,
            fields_required=["origin", "history"],
            is_structured_request=True,
        )
        state = build_state({"tone": "professional"}, user_schema=schema)
        state = plan_slides_strict(state)

        async def mock_call_llm(system, user):
            # Return short valid answers for any prompt
            if "BULLET" in system:
                return "Rice overview\nWheat overview"
            return "Short factual answer"

        with patch("pipeline.strict_content_structurer.call_llm", side_effect=mock_call_llm):
            state = await generate_strict_content(state)

        assert state.structured_slides is not None
        assert len(state.structured_slides) == 5  # title + definition + 2 examples + summary

        # Check example slides have ONLY name + required fields
        for slide in state.structured_slides:
            if slide["type"] == "example_detail_slide":
                content = slide["content"]
                assert "name" in content
                assert "origin" in content
                assert "history" in content
                # No extra keys allowed
                assert set(content.keys()) == {"name", "origin", "history"}

    @pytest.mark.asyncio
    async def test_no_fallback_content(self):
        """Strict mode raises error on LLM failure - no fallback."""
        from pipeline.strict_content_structurer import generate_strict_content, StrictContentError

        schema = UserSchema(
            topic="food commodities",
            examples_required=1,
            fields_required=["origin"],
            is_structured_request=True,
        )
        state = build_state({"tone": "professional"}, user_schema=schema)
        state = plan_slides_strict(state)

        async def always_fail(system, user):
            raise RuntimeError("LLM down")

        with patch("pipeline.strict_content_structurer.call_llm", side_effect=always_fail):
            with pytest.raises((StrictContentError, RuntimeError)):
                await generate_strict_content(state)
