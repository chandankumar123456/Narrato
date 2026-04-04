"""
Tests for the Visual & Rendering Engine (4 stages).

Covers:
  - Stage 1: Design Engine (layout mapping, component extraction, theme)
  - Stage 2: Template Engine (HTML generation, Tailwind classes)
  - Stage 3: Rendering Engine (render instructions)
  - Stage 4: Export Engine (PPT structure, HTML saving)
  - Integration: Full 4-stage pipeline
"""

import os
import sys
import tempfile
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pipeline.visual_design_engine import (
    run_design_engine,
    select_layout,
    map_components,
    enforce_design_rules,
    resolve_theme,
    VISUAL_THEMES,
    MAX_ITEMS,
)
from pipeline.visual_template_engine import (
    run_template_engine,
    render_slide_html,
)
from pipeline.visual_rendering_engine import build_render_instructions
from pipeline.visual_export_engine import (
    build_ppt_structure,
    save_html_slides,
    run_export_engine,
)
from pipeline.visual_rendering_pipeline import run_visual_pipeline


# ── Sample slide data ────────────────────────────────────────────────

SAMPLE_SLIDES = [
    {
        "type": "title_slide",
        "intent": "vision",
        "content": {
            "title": "The Future of AI",
            "subtitle": "How artificial intelligence is transforming industries",
        },
    },
    {
        "type": "problem_slide",
        "intent": "problem",
        "content": {
            "title": "Key Challenges",
            "bullet_points": [
                "Data quality remains a bottleneck",
                "Talent shortage in AI/ML engineering",
                "Ethical concerns around bias",
                "Integration with legacy systems",
                "Extra item that should be trimmed",
            ],
        },
    },
    {
        "type": "stats_slide",
        "intent": "market",
        "content": {
            "title": "Market Opportunity",
            "stats": [
                {"value": "$150B", "label": "Global AI Market by 2028"},
                {"value": "42%", "label": "CAGR Growth Rate"},
                {"value": "85%", "label": "Enterprise Adoption"},
            ],
        },
    },
    {
        "type": "feature_slide",
        "intent": "product",
        "content": {
            "title": "Our Approach",
            "body": "A three-step process",
            "bullets": [
                "Collect and clean data",
                "Train models with feedback loops",
                "Deploy with monitoring",
            ],
        },
    },
    {
        "type": "timeline_slide",
        "intent": "timeline",
        "content": {
            "title": "Roadmap",
            "events": [
                {"date": "Q1 2026", "description": "Beta launch"},
                {"date": "Q2 2026", "description": "Enterprise release"},
                {"date": "Q4 2026", "description": "Global expansion"},
            ],
        },
    },
]


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Stage 1: Design Engine
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestLayoutSelection:
    def test_intent_maps_correctly(self):
        assert select_layout({"intent": "vision"}) == "hero_center"
        assert select_layout({"intent": "problem"}) == "grid_cards"
        assert select_layout({"intent": "solution"}) == "split_left_text_right_visual"
        assert select_layout({"intent": "product"}) == "step_flow"
        assert select_layout({"intent": "market"}) == "stats_blocks"
        assert select_layout({"intent": "timeline"}) == "timeline_flow"

    def test_slide_type_fallback(self):
        assert select_layout({"type": "title_slide"}) == "hero_center"
        assert select_layout({"type": "stats_slide"}) == "stats_blocks"
        assert select_layout({"type": "timeline_slide"}) == "timeline_flow"

    def test_unknown_defaults_to_hero(self):
        assert select_layout({}) == "hero_center"
        assert select_layout({"intent": "unknown"}) == "hero_center"

    def test_intent_takes_priority_over_type(self):
        slide = {"type": "feature_slide", "intent": "market"}
        assert select_layout(slide) == "stats_blocks"


class TestComponentMapping:
    def test_hero_center_components(self):
        slide = SAMPLE_SLIDES[0]
        comp = map_components(slide, "hero_center")
        assert comp["type"] == "hero"
        assert comp["title"] == "The Future of AI"
        assert "subtitle" in comp

    def test_grid_cards_components(self):
        slide = SAMPLE_SLIDES[1]
        comp = map_components(slide, "grid_cards")
        assert comp["type"] == "card_grid"
        assert len(comp["items"]) <= MAX_ITEMS

    def test_stats_blocks_components(self):
        slide = SAMPLE_SLIDES[2]
        comp = map_components(slide, "stats_blocks")
        assert comp["type"] == "stats"
        assert len(comp["items"]) == 3
        assert comp["items"][0]["value"] == "$150B"

    def test_step_flow_components(self):
        slide = SAMPLE_SLIDES[3]
        comp = map_components(slide, "step_flow")
        assert comp["type"] == "steps"
        assert len(comp["steps"]) == 3
        assert comp["steps"][0]["step"] == 1

    def test_timeline_flow_components(self):
        slide = SAMPLE_SLIDES[4]
        comp = map_components(slide, "timeline_flow")
        assert comp["type"] == "timeline"
        assert len(comp["events"]) == 3
        assert comp["events"][0]["date"] == "Q1 2026"

    def test_split_components(self):
        slide = {
            "type": "example_slide",
            "content": {
                "title": "Case Study",
                "body": "An example of our technology in action",
                "bullets": ["Point A", "Point B"],
            },
        }
        comp = map_components(slide, "split_left_text_right_visual")
        assert comp["type"] == "split"
        assert "body" in comp
        assert len(comp["items"]) == 2


class TestDesignRules:
    def test_max_items_enforced(self):
        comp = {
            "items": [{"text": f"item {i}"} for i in range(8)],
        }
        result = enforce_design_rules(comp)
        assert len(result["items"]) == MAX_ITEMS

    def test_steps_capped(self):
        comp = {
            "steps": [{"step": i, "text": f"s{i}"} for i in range(6)],
        }
        result = enforce_design_rules(comp)
        assert len(result["steps"]) == MAX_ITEMS


class TestThemeResolution:
    def test_modern_to_dark(self):
        assert resolve_theme("modern") == "dark_modern"

    def test_corporate_to_minimal(self):
        assert resolve_theme("corporate") == "minimal_light"

    def test_direct_theme_names(self):
        assert resolve_theme("dark_modern") == "dark_modern"
        assert resolve_theme("bold_gradient") == "bold_gradient"

    def test_unknown_defaults(self):
        assert resolve_theme("unknown") == "dark_modern"


class TestDesignEngine:
    def test_full_run(self):
        designs = run_design_engine(SAMPLE_SLIDES)
        assert len(designs) == 5
        # All use same theme
        themes = {d["theme"] for d in designs}
        assert len(themes) == 1
        assert "dark_modern" in themes

    def test_each_design_has_layout(self):
        designs = run_design_engine(SAMPLE_SLIDES)
        for d in designs:
            assert d["layout"] in {
                "hero_center", "grid_cards", "split_left_text_right_visual",
                "step_flow", "stats_blocks", "timeline_flow",
            }

    def test_each_design_has_components(self):
        designs = run_design_engine(SAMPLE_SLIDES)
        for d in designs:
            assert "components" in d
            assert "title" in d["components"]

    def test_empty_slides(self):
        designs = run_design_engine([])
        assert designs == []


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Stage 2: Template Engine
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestTemplateEngine:
    def test_generates_html_per_slide(self):
        designs = run_design_engine(SAMPLE_SLIDES)
        html_slides = run_template_engine(designs)
        assert len(html_slides) == 5

    def test_html_is_complete_document(self):
        designs = run_design_engine(SAMPLE_SLIDES)
        html_slides = run_template_engine(designs)
        for h in html_slides:
            assert "<!DOCTYPE html>" in h
            assert "</html>" in h
            assert "tailwindcss" in h

    def test_slide_has_full_screen_class(self):
        designs = run_design_engine(SAMPLE_SLIDES)
        html_slides = run_template_engine(designs)
        for h in html_slides:
            assert 'class="slide' in h

    def test_dark_modern_theme_classes(self):
        designs = run_design_engine(SAMPLE_SLIDES, state_theme="modern")
        html_slides = run_template_engine(designs)
        for h in html_slides:
            assert "from-black" in h or "bg-gradient" in h

    def test_minimal_light_theme(self):
        designs = run_design_engine(SAMPLE_SLIDES, state_theme="corporate")
        html_slides = run_template_engine(designs)
        for h in html_slides:
            assert "bg-white" in h

    def test_bold_gradient_theme(self):
        designs = run_design_engine(SAMPLE_SLIDES, state_theme="bold_gradient")
        html_slides = run_template_engine(designs)
        for h in html_slides:
            assert "from-indigo-900" in h or "bg-gradient" in h

    def test_html_contains_slide_content(self):
        designs = run_design_engine(SAMPLE_SLIDES[:1])
        html_slides = run_template_engine(designs)
        assert "The Future of AI" in html_slides[0]

    def test_stats_rendered(self):
        designs = run_design_engine([SAMPLE_SLIDES[2]])
        html_slides = run_template_engine(designs)
        assert "$150B" in html_slides[0]
        assert "42%" in html_slides[0]

    def test_html_escapes_special_chars(self):
        slide = {
            "type": "title_slide",
            "content": {"title": "A <b>bold</b> & dangerous title"},
        }
        designs = run_design_engine([slide])
        html_slides = run_template_engine(designs)
        assert "&lt;b&gt;" in html_slides[0]
        assert "&amp;" in html_slides[0]

    def test_render_single_slide(self):
        design = {
            "layout": "hero_center",
            "theme": "dark_modern",
            "components": {"type": "hero", "title": "Test", "subtitle": "Sub"},
        }
        html = render_slide_html(design)
        assert "Test" in html
        assert "Sub" in html


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Stage 3: Rendering Engine
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestRenderingEngine:
    def test_render_instructions(self):
        instr = build_render_instructions(5)
        assert instr["viewport"] == "1920x1080"
        assert instr["slide_count"] == 5
        assert "png" in instr["export"]
        assert "pdf" in instr["export"]
        assert "ppt" in instr["export"]
        assert instr["quality"]["no_overflow"] is True
        assert instr["quality"]["fixed_viewport"] is True

    def test_render_instructions_zero_slides(self):
        instr = build_render_instructions(0)
        assert instr["slide_count"] == 0


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Stage 4: Export Engine
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestExportEngine:
    def test_ppt_structure(self):
        paths = ["/tmp/slide_1.png", "/tmp/slide_2.png", "/tmp/slide_3.png"]
        structure = build_ppt_structure(paths)
        assert len(structure["slides"]) == 3
        assert structure["slides"][0]["image"] == "slide_1.png"
        assert structure["slides"][2]["image"] == "slide_3.png"

    def test_ppt_structure_empty(self):
        structure = build_ppt_structure([])
        assert structure["slides"] == []

    def test_save_html_slides(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            html_slides = [
                "<html><body>Slide 1</body></html>",
                "<html><body>Slide 2</body></html>",
            ]
            paths = save_html_slides(html_slides, tmpdir)
            assert len(paths) == 2
            assert os.path.isfile(paths[0])
            assert os.path.isfile(paths[1])
            with open(paths[0]) as f:
                assert "Slide 1" in f.read()

    def test_run_export_engine(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            html_slides = ["<html><body>Test</body></html>"]
            result = run_export_engine(
                html_slides=html_slides,
                image_paths=[],
                pdf_path=None,
                output_dir=tmpdir,
            )
            assert len(result["html_paths"]) == 1
            assert result["ppt_structure"]["slides"] == []
            assert result["ppt_path"] is None


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Integration: Full 4-Stage Pipeline
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class _MockState:
    """Minimal mock matching PresentationState interface."""
    def __init__(self, slides, theme="modern"):
        self.structured_slides = slides
        self.theme = theme


class TestVisualPipeline:
    @pytest.mark.asyncio
    async def test_full_pipeline(self):
        state = _MockState(SAMPLE_SLIDES)
        result = await run_visual_pipeline(state)

        # Designs
        assert len(result["designs"]) == 5
        for d in result["designs"]:
            assert "layout" in d
            assert "theme" in d
            assert "components" in d

        # HTML slides
        assert len(result["html_slides"]) == 5
        for h in result["html_slides"]:
            assert "<!DOCTYPE html>" in h

        # Render instructions
        assert result["render_instructions"]["viewport"] == "1920x1080"
        assert result["render_instructions"]["slide_count"] == 5

        # PPT structure
        assert "slides" in result["ppt_structure"]

        # HTML paths (saved to disk)
        for p in result["html_paths"]:
            assert os.path.isfile(p)

    @pytest.mark.asyncio
    async def test_pipeline_empty_slides(self):
        state = _MockState([])
        result = await run_visual_pipeline(state)
        assert result["designs"] == []
        assert result["html_slides"] == []

    @pytest.mark.asyncio
    async def test_pipeline_theme_consistency(self):
        state = _MockState(SAMPLE_SLIDES, theme="bold_gradient")
        result = await run_visual_pipeline(state)
        themes = {d["theme"] for d in result["designs"]}
        assert themes == {"bold_gradient"}

    @pytest.mark.asyncio
    async def test_pipeline_layout_mapping(self):
        state = _MockState(SAMPLE_SLIDES)
        result = await run_visual_pipeline(state)
        layouts = [d["layout"] for d in result["designs"]]
        assert layouts[0] == "hero_center"      # vision intent
        assert layouts[1] == "grid_cards"        # problem intent
        assert layouts[2] == "stats_blocks"      # market intent
        assert layouts[3] == "step_flow"         # product intent
        assert layouts[4] == "timeline_flow"     # timeline intent

    @pytest.mark.asyncio
    async def test_pipeline_html_quality(self):
        """Verify HTML output meets visual quality requirements."""
        state = _MockState(SAMPLE_SLIDES)
        result = await run_visual_pipeline(state)

        for html_str in result["html_slides"]:
            # Full-screen slide class
            assert 'class="slide' in html_str
            # Tailwind CDN loaded
            assert "tailwindcss" in html_str
            # Font loaded
            assert "Inter" in html_str
            # No scrolling
            assert "overflow:hidden" in html_str
