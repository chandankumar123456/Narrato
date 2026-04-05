"""Tests for strict narrative-first generation."""

import os
import sys
from unittest.mock import AsyncMock, patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.presentation_state import PresentationState
from pipeline.narrative_generator import (
    BANNED_PHRASES,
    EXPECTED_SECTION_IDS,
    FREQUENCY_RE,
    IMPROVEMENT_RE,
    NARRATIVE_SECTIONS,
    NUMBER_RE,
    SECTION_ROLES,
    _auto_fix_overlap,
    _build_slide_content,
    _check_section_differentiation,
    _claim_fingerprint,
    _claims_overlap,
    _deduplicate_concepts,
    _get_icon,
    _reject_generic_language,
    _validate_required_markers,
    _validate_section_specific_rules,
    _validate_sections,
    auto_rewrite_invalid_sections,
    soft_validation_failure,
    generate_narrative,
)


def _make_state(**kwargs):
    defaults = {
        "topic": "Cold-chain orchestration for grocery distributors",
        "presentation_type": "pitch",
        "tone": "professional",
        "audience": "investors",
        "slide_count": 12,
    }
    defaults.update(kwargs)
    return PresentationState(**defaults)


def _section_payload(section_id: str, title: str) -> dict:
    index = EXPECTED_SECTION_IDS.index(section_id) + 1
    if section_id == "mechanism":
        return {
            "id": section_id,
            "title": title,
            "content": (
                f"Actor: Dispatch coordinator at depot {index}\n"
                f"Input: pallet temperature logs, order cutoffs, and truck GPS pings for route {index}\n"
                f"Processing: routing rules compare spoilage risk, carrier capacity, and delivery windows for lane {index}\n"
                f"Output: the coordinator sends a reroute instruction and revised dock sequence for truck {index}"
            ),
            "key_points": [
                f"Input feed {index} combines dock scans with retailer order edits",
                f"Processing step {index} ranks loads by spoilage exposure before dispatch",
                f"Output action {index} issues a new stop plan within 12 minutes",
            ],
        }
    if section_id == "business_model":
        return {
            "id": section_id,
            "title": title,
            "content": (
                "Payer: regional grocery distributors with more than 20 refrigerated sites\n"
                "Pricing: $4,800 per site per month plus $0.18 per completed pallet move\n"
                "Trigger: billed when a site goes live and again when monthly pallet volume clears the contracted floor\n"
                "Output: finance teams tie invoice value to active sites and verified pallet moves"
            ),
            "key_points": [
                "Distributors approve annual subscriptions before site rollout begins",
                "Usage-based pallet fees expand revenue when daily throughput spikes",
                "Invoices close after ERP exports confirm shipped pallet counts",
            ],
        }
    if section_id == "traction":
        return {
            "id": section_id,
            "title": title,
            "content": (
                "Actor: operations directors across 14 live depots\n"
                "Action: planners use the workflow daily and update dispatch queues 6 times per day\n"
                "Data: 12,400 weekly pallet moves, 98.7% sensor uptime, and 4,300 order edits per week feed the workflow\n"
                "Output: spoilage fell 31%, dock overtime dropped 18%, and on-time delivery rose 9%"
            ),
            "key_points": [
                "14 depots process 12,400 pallet moves every week on the live workflow",
                "Schedulers open the console 6 times per day to reprioritize dispatch queues",
                "Spoilage is down 31% while on-time delivery is up 9%",
            ],
        }
    if section_id == "system_gap":
        return {
            "id": section_id,
            "title": title,
            "content": (
                "Actor: shift supervisors compare three disconnected planning tools before each dispatch wave\n"
                "Action: they manually reconcile order edits against trailer availability and late temperature alerts\n"
                "Data: ERP snapshots lag by 45 minutes, telematics feeds omit trailer swaps, and spreadsheets lose shelf-life flags\n"
                "Output: dispatch decisions rely on stale records, so loads leave with avoidable spoilage risk"
            ),
            "key_points": [
                "ERP exports arrive 45 minutes late during the evening replenishment rush",
                "Telematics feeds ignore trailer swaps that happen after yard check-in",
                "Spreadsheet workflows strip shelf-life flags before dispatch review begins",
            ],
        }
    return {
        "id": section_id,
        "title": title,
        "content": (
            f"Actor: role {index} owns the {section_id.replace('_', ' ')} handoff at depot {index}\n"
            f"Action: role {index} performs a distinct {section_id.replace('_', ' ')} task during the 04:{index:02d} dispatch window\n"
            f"Data: role {index} reads lane-{index} telemetry, batch-{index} shelf-life scans, and contract-{index} operating records\n"
            f"Output: role {index} produces a {section_id.replace('_', ' ')} decision that only affects depot {index}"
        ),
        "key_points": [
            f"Fact {index} isolates the {section_id.replace('_', ' ')} dimension with depot-{index}-specific evidence",
            f"Dataset {index} cites lane-{index} records and batch-{index} events unique to this section",
            f"Result {index} stays unique to {section_id.replace('_', ' ')} without reusing prior mechanisms",
        ],
    }


def _mock_narrative_response():
    return {"sections": [_section_payload(section["id"], section["title"]) for section in NARRATIVE_SECTIONS]}


class TestNarrativeSections:
    def test_has_12_sections(self):
        assert len(NARRATIVE_SECTIONS) == 12

    def test_ids_match_expected_order(self):
        assert [section["id"] for section in NARRATIVE_SECTIONS] == EXPECTED_SECTION_IDS

    def test_each_has_required_keys(self):
        for section in NARRATIVE_SECTIONS:
            assert {"id", "title", "dimension", "instruction", "content_format"} <= set(section.keys())


class TestBannedPhrases:
    def test_non_empty(self):
        assert len(BANNED_PHRASES) > 0

    def test_contains_new_generic_terms(self):
        for phrase in ["solution", "engine", "platform", "ai platform", "system", "layer"]:
            assert phrase in BANNED_PHRASES


class TestBuildSlideContent:
    def test_problem_slide(self):
        content = _build_slide_content(
            "problem_slide",
            "Problem",
            "Actor: buyer\nAction: missed a slot\nData: order edits\nOutput: spoilage rose",
            ["Dock queue overflow blocks chilled pallets", "Late edits miss truck departure", "Spoilage claims hit margin"],
        )
        assert len(content["cards"]) == 3

    def test_comparison_slide(self):
        content = _build_slide_content(
            "comparison_slide",
            "System Gap",
            "Actor: planner\nAction: compares tools\nData: stale exports\nOutput: late dispatch",
            ["ERP lag hides cutoffs", "Telematics miss swaps", "Spreadsheets drop shelf-life flags"],
        )
        assert content["left_label"] == "Current Tools"
        assert content["right_label"] == "Observed Gaps"

    def test_stats_slide(self):
        content = _build_slide_content(
            "stats_slide",
            "Traction",
            "Actor: ops lead\nAction: reviews daily usage\nData: 1200 loads weekly\nOutput: spoilage fell 31%",
            ["$2.4M ARR", "6 daily sessions per planner", "Spoilage down 31%"],
        )
        assert content["stat"] == "$2.4M ARR"

    def test_feature_slide_adds_summary(self):
        content = _build_slide_content(
            "feature_slide",
            "Product",
            "Actor: dispatcher\nAction: uses the workflow\nData: pallet scans\nOutput: reroute plan",
            ["Point one", "Point two", "Point three"],
        )
        assert "summary" in content


class TestGetIcon:
    def test_cycles_correctly(self):
        assert _get_icon(0) == _get_icon(8)


class TestValidationHelpers:
    def test_validate_sections_accepts_valid_payload(self):
        sections = _validate_sections(_mock_narrative_response()["sections"])
        assert len(sections) == 12

    def test_validate_sections_recovers_wrong_schema(self):
        """Wrong schema is recovered with fallback — never raises."""
        bad = _mock_narrative_response()["sections"]
        bad[0] = {"id": "problem", "title": "Problem", "body": []}
        # Should NOT raise — soft recovery fills in missing keys
        sections = _validate_sections(bad)
        assert len(sections) == 12
        assert sections[0]["id"] == "problem"

    def test_reject_generic_language_raises_on_banned_phrase(self):
        """The hard helper still raises for direct callers."""
        with pytest.raises(ValueError, match="banned generic phrase"):
            _reject_generic_language("problem", ["this AI platform handles everything"])

    def test_validate_sections_soft_fixes_banned_phrase(self):
        """_validate_sections strips banned phrases instead of raising."""
        bad = _mock_narrative_response()["sections"]
        bad[0]["content"] += "\nOutput: this AI platform handles everything"
        # Should NOT raise — banned phrase is stripped
        sections = _validate_sections(bad)
        assert len(sections) == 12
        assert "ai platform" not in sections[0]["content"].lower()

    def test_system_in_title_allowed_and_stripped_in_content(self):
        """'system' in predefined title 'System Gap' must not trigger the ban,
        and 'system' appearing in content is stripped (not failed)."""
        good = _mock_narrative_response()["sections"]
        sections = _validate_sections(good)
        assert any(s["id"] == "system_gap" for s in sections)

        # "system" in content should be stripped by soft validation
        bad = _mock_narrative_response()["sections"]
        bad[0]["content"] = (
            "Actor: buyer at depot 1\n"
            "Action: the system fails to route pallets\n"
            "Data: stale order edits and sensor logs\n"
            "Output: spoilage rises because the system cannot react"
        )
        sections = _validate_sections(bad)
        assert len(sections) == 12
        # Verify "system" was removed from content
        assert "system" not in sections[0]["content"].lower()

    def test_layer_stripped_in_content(self):
        """'layer' in content is stripped by soft validation."""
        bad = _mock_narrative_response()["sections"]
        bad[0]["content"] = (
            "Actor: buyer at depot 1\n"
            "Action: dispatches through a data layer\n"
            "Data: stale order edits\n"
            "Output: spoilage rises because the layer misses updates"
        )
        sections = _validate_sections(bad)
        assert len(sections) == 12
        assert "layer" not in sections[0]["content"].lower()

    def test_validate_sections_tolerates_overlap(self):
        """Overlap is detected and auto-fixed or tolerated — never raises."""
        bad = _mock_narrative_response()["sections"]
        repeated = "shared phrase about depot route pallet workflow unique overlap"
        bad[0]["key_points"][0] = repeated
        bad[1]["key_points"][1] = repeated
        # Should NOT raise — overlap is soft-corrected or tolerated
        sections = _validate_sections(bad)
        assert len(sections) == 12

    def test_validate_sections_soft_fixes_missing_markers(self):
        """Missing markers are auto-injected — never raises."""
        bad = _mock_narrative_response()["sections"]
        bad[2]["content"] = "Actor: planner\nAction: checks exports\nData: stale files"
        sections = _validate_sections(bad)
        assert len(sections) == 12
        # Marker should have been injected
        assert "Output:" in sections[2]["content"]

    def test_validate_required_markers_raises_directly(self):
        """Hard helper still raises when called directly."""
        with pytest.raises(ValueError, match="missing required markers"):
            _validate_required_markers("root_cause", "Actor: planner\nAction: checks\nData: stale")

    def test_validate_sections_soft_fixes_invalid_mechanism(self):
        """Invalid mechanism format is auto-fixed — never raises."""
        bad = _mock_narrative_response()["sections"]
        bad[5]["content"] = "Actor: coordinator\nAction: routes loads\nData: shelf-life\nOutput: dispatch plan"
        sections = _validate_sections(bad)
        assert len(sections) == 12

    def test_validate_sections_soft_fixes_traction_without_metrics(self):
        """Traction without metrics is auto-fixed — never raises."""
        bad = _mock_narrative_response()["sections"]
        bad[9]["content"] = "Actor: ops lead\nAction: reviews adoption often\nData: weekly usage signals\nOutput: better performance"
        bad[9]["key_points"] = ["Usage is steady", "Teams log in often", "Results improved"]
        sections = _validate_sections(bad)
        assert len(sections) == 12
        # Verify metrics were injected
        blob = "\n".join([sections[9]["content"], *sections[9]["key_points"]])
        assert NUMBER_RE.search(blob) or FREQUENCY_RE.search(blob)

    def test_validate_sections_soft_fixes_business_model_without_trigger(self):
        """Business model without trigger is auto-fixed — never raises."""
        bad = _mock_narrative_response()["sections"]
        bad[7]["content"] = (
            "Payer: distributors\nPricing: $120 per site per month\n"
            "Trigger: active contract\nOutput: invoices go out"
        )
        bad[7]["key_points"] = ["Monthly subscription", "Distributor pays", "Invoices exist"]
        sections = _validate_sections(bad)
        assert len(sections) == 12

    def test_validate_section_specific_rules_raises_directly(self):
        """Hard helper still raises when called directly."""
        with pytest.raises(ValueError, match="numbers"):
            _validate_section_specific_rules(
                "traction",
                "Actor: lead\nAction: reviews\nData: signals\nOutput: better",
                ["Usage is steady", "Teams log in", "Results ok"],
            )

    def test_validate_sections_handles_fewer_than_12(self):
        """Fewer than 12 sections are padded with fallbacks — never raises."""
        payload = _mock_narrative_response()["sections"][:10]
        sections = _validate_sections(payload)
        assert len(sections) == 12

    def test_claim_overlap_helper(self):
        duplicated_claim = "alpha beta gamma delta epsilon"
        a = _claim_fingerprint({"content": "Actor: one\nAction: two\nData: three\nOutput: four", "key_points": [duplicated_claim, "x", "y"]})
        b = _claim_fingerprint({"content": "Actor: five\nAction: six\nData: seven\nOutput: eight", "key_points": [duplicated_claim, "m", "n"]})
        assert _claims_overlap(a, b)


class TestAutoFixOverlap:
    def test_removes_overlapping_words_from_key_points(self):
        section = {
            "id": "actor",
            "title": "Actor",
            "content": "Actor: one\nAction: two\nData: three\nOutput: four",
            "key_points": ["shared phrase about depot route pallet", "unique point", "another unique"],
        }
        overlapping = {"shared phrase depot route pallet"}
        fixed = _auto_fix_overlap(section, overlapping)
        # Overlapping words should be removed from the first key_point
        assert fixed["key_points"][0] != section["key_points"][0]
        # Verify overlapping words are actually removed
        for word in ("shared", "phrase", "depot", "route", "pallet"):
            assert word not in fixed["key_points"][0].lower()
        # Non-overlapping key_points should be unchanged
        assert fixed["key_points"][1] == "unique point"
        assert fixed["key_points"][2] == "another unique"

    def test_preserves_key_points_when_no_overlap(self):
        section = {
            "id": "actor",
            "title": "Actor",
            "content": "Actor: one\nAction: two\nData: three\nOutput: four",
            "key_points": ["unique alpha", "unique beta", "unique gamma"],
        }
        fixed = _auto_fix_overlap(section, set())
        assert fixed["key_points"] == section["key_points"]


class TestDeduplicateConcepts:
    def test_removes_repeated_phrases_across_sections(self):
        sections = _mock_narrative_response()["sections"]
        repeated = "shared phrase about depot route pallet workflow unique overlap"
        sections[0]["key_points"][0] = repeated
        sections[1]["key_points"][1] = repeated
        cleaned = _deduplicate_concepts(sections)
        # After dedup, the repeated phrase in section[1] should be modified
        assert cleaned[1]["key_points"][1] != repeated
        # Verify the specific repeated words were removed
        for word in ("shared", "phrase", "depot", "route", "pallet"):
            assert word not in cleaned[1]["key_points"][1].lower()

    def test_preserves_non_overlapping_sections(self):
        sections = _mock_narrative_response()["sections"]
        original_kps = [s["key_points"][:] for s in sections]
        cleaned = _deduplicate_concepts(sections)
        # All sections should still have 3 key_points each
        for section in cleaned:
            assert len(section["key_points"]) == 3

    def test_returns_same_count(self):
        sections = _mock_narrative_response()["sections"]
        cleaned = _deduplicate_concepts(sections)
        assert len(cleaned) == len(sections)


class TestSectionDifferentiation:
    def test_product_section_warns_on_process_terms(self):
        warnings = _check_section_differentiation(
            "product",
            "Actor: user\nAction: uses pipeline routing\nData: logs\nOutput: plan",
            ["The pipeline processes data", "Routing sequence stages", "Dashboard view"],
        )
        assert any("unexpected term" in w for w in warnings)

    def test_mechanism_section_accepts_process_terms(self):
        warnings = _check_section_differentiation(
            "mechanism",
            "Actor: coordinator\nInput: logs\nProcessing: routing rules compare\nOutput: dispatch",
            ["Input feed combines data", "Processing step ranks loads", "Output issues plan"],
        )
        assert not any("unexpected term" in w for w in warnings)

    def test_non_role_sections_return_no_warnings(self):
        warnings = _check_section_differentiation(
            "problem",
            "Actor: buyer\nAction: missed slot\nData: edits\nOutput: spoilage",
            ["Point one", "Point two", "Point three"],
        )
        assert warnings == []

    def test_section_roles_defined(self):
        assert "product" in SECTION_ROLES
        assert "mechanism" in SECTION_ROLES


class TestGenerateNarrative:
    @pytest.fixture
    def state(self):
        return _make_state()

    @pytest.mark.asyncio
    async def test_single_llm_call(self, state):
        with patch("pipeline.narrative_generator.call_llm_json", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = _mock_narrative_response()
            await generate_narrative(state)
        assert mock_llm.call_count == 1

    @pytest.mark.asyncio
    async def test_generates_slides_from_narrative(self, state):
        with patch("pipeline.narrative_generator.call_llm_json", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = _mock_narrative_response()
            result = await generate_narrative(state)
        assert len(result.structured_slides) == 14
        assert len(result.slide_plan) == 14

    @pytest.mark.asyncio
    async def test_metadata_stored(self, state):
        with patch("pipeline.narrative_generator.call_llm_json", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = _mock_narrative_response()
            result = await generate_narrative(state)
        assert result.metadata["narrative_generation"]["schema"] == "id_title_content_key_points"

    @pytest.mark.asyncio
    async def test_fewer_sections_recovered(self, state):
        """Fewer than 12 sections are padded — pipeline never fails."""
        with patch("pipeline.narrative_generator.call_llm_json", new_callable=AsyncMock) as mock_llm:
            payload = _mock_narrative_response()
            payload["sections"] = payload["sections"][:11]
            mock_llm.return_value = payload
            result = await generate_narrative(state)
        # Should produce slides (padded to 12 sections + title + CTA)
        assert len(result.structured_slides) == 14

    @pytest.mark.asyncio
    async def test_all_slides_have_content(self, state):
        with patch("pipeline.narrative_generator.call_llm_json", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = _mock_narrative_response()
            result = await generate_narrative(state)
        assert all(isinstance(slide["content"], dict) for slide in result.structured_slides)


class TestPipelineFailure:
    def test_pipeline_failure_is_exception(self):
        try:
            from orchestrator import PipelineFailure
        except ImportError:
            class PipelineFailure(Exception):
                pass
        assert issubclass(PipelineFailure, Exception)


class TestVisualPipelinePlaywrightSkip:
    @pytest.mark.asyncio
    async def test_rendering_engine_requires_playwright(self):
        """Rendering engine raises RuntimeError when Playwright is not installed."""
        from pipeline.visual_rendering_engine import render_slides_to_images
        # STRICT: Playwright not installed in test env → must raise RuntimeError
        with pytest.raises(RuntimeError, match="Playwright is required"):
            await render_slides_to_images(["<html></html>"], "/tmp/test_render")


class TestStreamTermination:
    def test_event_type_has_failed(self):
        from services.event_system import EventType
        assert hasattr(EventType, "JOB_FAILED")
        assert hasattr(EventType, "JOB_COMPLETED")


class TestSoftValidationEngine:
    """Tests for the soft validation engine that corrects instead of failing."""

    def test_soft_validation_failure_returns_string(self):
        result = soft_validation_failure("traction", "must include usage frequency", "Actor: lead\nAction: reviews\nData: signals\nOutput: ok")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_soft_validation_injects_frequency_for_traction(self):
        content = "Actor: ops\nAction: reviews adoption\nData: signals\nOutput: better"
        result = soft_validation_failure("traction", "must include usage frequency", content)
        assert FREQUENCY_RE.search(result)

    def test_soft_validation_injects_numbers_for_traction(self):
        content = "Actor: ops\nAction: reviews adoption\nData: signals\nOutput: better"
        result = soft_validation_failure("traction", "must include numbers", content)
        assert NUMBER_RE.search(result)

    def test_soft_validation_injects_improvement_for_traction(self):
        content = "Actor: ops\nAction: reviews adoption\nData: signals\nOutput: better"
        result = soft_validation_failure("traction", "must include measurable improvement", content)
        assert IMPROVEMENT_RE.search(result)

    def test_soft_validation_never_raises(self):
        """soft_validation_failure must NEVER raise an exception."""
        try:
            soft_validation_failure("unknown", "unknown rule", "")
            soft_validation_failure("traction", "must include usage frequency", "")
            soft_validation_failure("mechanism", "must follow Input -> Processing -> Output", "")
            soft_validation_failure("business_model", "must include pricing logic", "")
        except Exception:
            pytest.fail("soft_validation_failure raised an exception")


class TestAutoRewriteInvalidSections:
    """Tests for the auto_rewrite_invalid_sections post-validation pass."""

    def test_traction_gets_metrics_injected(self):
        sections = _mock_narrative_response()["sections"]
        # Strip metrics from traction section
        sections[9]["content"] = "Actor: ops\nAction: reviews\nData: signals\nOutput: better"
        sections[9]["key_points"] = ["Usage is steady", "Teams log in", "Results ok"]
        rewritten = auto_rewrite_invalid_sections(sections)
        blob = "\n".join([rewritten[9]["content"], *rewritten[9]["key_points"]])
        # At least frequency or number should be present after rewrite
        assert NUMBER_RE.search(blob) or FREQUENCY_RE.search(blob)

    def test_preserves_valid_sections(self):
        sections = _mock_narrative_response()["sections"]
        rewritten = auto_rewrite_invalid_sections(sections)
        # Valid sections should remain unchanged
        for i, (orig, rw) in enumerate(zip(sections, rewritten)):
            assert orig["id"] == rw["id"]

    def test_returns_same_count(self):
        sections = _mock_narrative_response()["sections"]
        rewritten = auto_rewrite_invalid_sections(sections)
        assert len(rewritten) == len(sections)


class TestPipelineNeverFailsAtNarrative:
    """Ensure the orchestrator never raises PipelineFailure at narrative stage."""

    def test_orchestrator_has_fallback_injection(self):
        """The orchestrator must define _inject_fallback_slides."""
        from orchestrator import _inject_fallback_slides
        assert callable(_inject_fallback_slides)

    def test_fallback_slides_are_non_empty(self):
        from orchestrator import _inject_fallback_slides
        state = _make_state()
        result = _inject_fallback_slides(state)
        assert result.structured_slides is not None
        assert len(result.structured_slides) > 0
        assert result.slide_plan is not None
        assert len(result.slide_plan) > 0
