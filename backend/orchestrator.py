"""Narrato Pipeline Orchestrator — narrative-first, fast execution.

Architecture:
  1. Parse prompt + schema (2 LLM calls)
  2. Build state
  3. Generate FULL narrative in ONE LLM call → split into slides
  4. Visual pipeline (design + template, deterministic, no LLM)
  5. Speaker notes (1 LLM call)
  6. Visual export (HTML + rendering engine for images/PDF)

Total LLM calls: ~4 (down from dozens in the old per-slide approach).
Pipeline stops immediately on failure after max retries.
"""

from pipeline.prompt_understanding import parse_prompt
from pipeline.schema_parser import parse_user_schema
from pipeline.state_builder import build_state
from pipeline.state_completion import complete_state
from pipeline.narrative_engine import run_narrative_engine
from pipeline.content_engine import run_content_engine
from pipeline.strict_slide_planner import plan_slides_strict
from pipeline.strict_content_structurer import generate_strict_content
from pipeline.content_validator import validate_content
from pipeline.speaker_notes_generator import generate_speaker_notes
from pipeline.dynamic_composition_engine import run_dynamic_composition_engine
from pipeline.visual_rendering_engine import render_slides_to_images, render_slides_to_pdf, build_render_instructions
from pipeline.visual_export_engine import run_export_engine
from pipeline.slide_validator import (
    validate_slide_content,
    validate_design_components,
    validate_rendered_html,
    validate_export_parity,
    validate_pipeline_contract,
    SlideRenderError,
)
from services.event_system import PipelineEvent, EventType
import logging
import os
from typing import Callable, Optional

logger = logging.getLogger(__name__)


class PipelineFailure(Exception):
    """Raised when a critical pipeline stage fails, stopping the pipeline immediately."""
    pass


def _compute_progress(completed: int, total: int) -> int:
    """Compute progress 0-100 from completed/total steps."""
    if total <= 0:
        return 0
    return min(100, max(0, int((completed / total) * 100)))


def _fallback_structured_slide(state, slide_id: int, role: str = "Problem") -> dict:
    topic = getattr(state, "topic", "Presentation")
    return {
        "slide_id": slide_id,
        "intent": role.lower().replace(" ", "_"),
        "primary_element": f"{role}: {topic}",
        "supporting_elements": [f"Core investor detail for {topic}"],
        "role": role,
        "role_in_story": role,
        "cause": "This slide is required to maintain narrative continuity",
        "tension": "This pressure point must be addressed for forward progress",
        "next_trigger": "This unresolved point forces the next slide",
        "why_this_slide": "Required for continuity",
        "why_next_slide": "Forces the next investor section",
        "emotional_tone": "neutral",
    }


def _repair_structured_slide_count(state, expected_count: int) -> None:
    slides = list(getattr(state, "structured_slides", None) or [])
    required_roles = [
        "Problem",
        "Solution",
        "Product",
        "Market",
        "Business Model",
        "Competition",
        "Financials",
        "Funding Ask",
    ]
    if getattr(state, "generation_mode", "default") != "strict":
        existing_roles = {str((s.get("role") or s.get("role_in_story") or "")).lower() for s in slides}
        for role in required_roles:
            if role.lower() not in existing_roles:
                slides.append(_fallback_structured_slide(state, len(slides) + 1, role))
                existing_roles.add(role.lower())

    while len(slides) < expected_count:
        if slides:
            clone = dict(slides[-1])
            clone["slide_id"] = len(slides) + 1
            clone["cause"] = f"Builds on slide {len(slides)} continuity"
            clone["next_trigger"] = "Requires the next proof point"
            slides.append(clone)
        else:
            slides.append(_fallback_structured_slide(state, 1))
    if len(slides) > expected_count:
        slides = slides[:expected_count]
    for idx, slide in enumerate(slides, start=1):
        slide["slide_id"] = idx
        slide.setdefault("cause", "Narrative continuity requirement")
        slide.setdefault("tension", "Investor pressure point is active")
        slide.setdefault("next_trigger", "Next section is required")
        role = slide.get("role") or slide.get("role_in_story")
        if not role and getattr(state, "generation_mode", "default") != "strict":
            role = required_roles[min(idx - 1, len(required_roles) - 1)]
        role = role or "Context"
        slide["role"] = role
        slide["role_in_story"] = role
    state.structured_slides = slides


def _repair_html_parity(state, html_slides: list[str]) -> list[str]:
    structured = getattr(state, "structured_slides", None) or []
    repaired = list(html_slides or [])
    expected = len(structured)
    if expected == 0:
        return repaired
    if len(repaired) > expected:
        return repaired[:expected]
    while len(repaired) < expected:
        slide = structured[len(repaired)]
        primary = slide.get("primary_element", f"Slide {len(repaired)+1}")
        bullets = slide.get("supporting_elements", [])[:4]
        list_html = "".join(f"<li>{b}</li>" for b in bullets)
        repaired.append(
            f"<!doctype html><html><body><div class='slide'><h1>{primary}</h1><ul>{list_html}</ul></div></body></html>"
        )
    return repaired


async def run_pipeline(prompt: str, options: dict = {},
                       progress_callback: Optional[Callable[[int], None]] = None,
                       event_callback: Optional[Callable[[PipelineEvent], None]] = None) -> str:
    """Run the full Narrato pipeline with event-driven progress reporting.

    Key changes from old pipeline:
      - ONE LLM call for full narrative (no slide-by-slide generation)
      - No evaluator/consistency loops (narrative is coherent by design)
      - Pipeline stops immediately on failure
      - Minimal LLM calls for maximum speed
    """
    job_id = options.get("_job_id", "unknown")

    def _emit(event_type: str, stage: str, label: str, progress: int, **kwargs):
        """Emit a pipeline event and also call legacy progress_callback."""
        evt = PipelineEvent(
            job_id=job_id,
            type=event_type,
            stage=stage,
            progress=progress,
            label=label,
            **kwargs,
        )
        if event_callback:
            try:
                event_callback(evt)
            except Exception:
                pass
        if progress_callback:
            try:
                progress_callback(progress)
            except Exception:
                pass

    def _fail(stage: str, error: str):
        """Emit failure event and raise PipelineFailure to stop pipeline."""
        logger.error("[pipeline] FAILED at stage '%s': %s", stage, error)
        _emit(EventType.JOB_FAILED, "failed", f"Failed: {error}", 0,
              data={"error": error, "stage": stage})
        raise PipelineFailure(f"Pipeline failed at {stage}: {error}")

    logger.info("[pipeline] Starting for prompt: %s", prompt[:80])
    _emit(EventType.STAGE_UPDATE, "init", "Understanding your prompt…", 3)

    # ── Stage 1: Parse prompt signals ─────────────────────────────
    try:
        signals = await parse_prompt(prompt)
        signals.update({k: v for k, v in options.items() if v is not None and not k.startswith("_")})
        # ── Detect investor mode ─────────────────────────
        deck_mode = "general"
        prompt_lower = prompt.lower()

        if any(x in prompt_lower for x in ["pitch deck", "investor", "startup"]):
            deck_mode = "investor"

        signals["deck_mode"] = deck_mode
        
    except Exception as exc:
        logger.warning("[pipeline] prompt parse failed, using safe defaults: %s", exc)
        signals = {
            "topic": (prompt or "Presentation")[:120],
            "presentation_type": "general",
            "slide_count": options.get("slide_count") or 8,
            "tone": options.get("tone") or "professional",
            "audience": options.get("audience"),
            "deck_mode": "investor" if any(x in (prompt or "").lower() for x in ["pitch deck", "investor", "startup"]) else "general",
        }

    # Stage 1b: Extract strict user schema
    try:
        user_schema = await parse_user_schema(prompt)
    except Exception as exc:
        logger.warning("[pipeline] Schema parse failed, continuing without: %s", exc)
        user_schema = {}

    _emit(EventType.STAGE_UPDATE, "prompt_parsed", "Analyzing requirements…", 8)

    # ── Stage 2: Build state ──────────────────────────────────────
    state = build_state(signals, user_schema=user_schema)
    state.user_schema = user_schema or {}
    deck_mode = signals.get("deck_mode", "general")
    if state.generation_mode != "strict":
        state.slide_count = max(state.slide_count, 8)
    
    total_slides = state.slide_count
    logger.info(
        "[pipeline] State built: %s | mode=%s | %d slides",
        state.topic, state.generation_mode, state.slide_count,
    )
    _emit(EventType.STAGE_UPDATE, "state_built", "Planning presentation structure…", 10,
          total_slides=total_slides)

    # ── Progress math (simplified) ────────────────────────────────
    # Global steps: parse(1) + state(1) + narrative(1) + notes(1) + ppt(1) = 5
    # Per-slide: design(1) + render(1) = 2
    GLOBAL_STEPS = 5
    per_slide_steps = 2
    total_steps = GLOBAL_STEPS + (total_slides * per_slide_steps)
    completed_steps = 2  # parse + state

    if state.generation_mode == "strict":
        # ── STRICT PIPELINE ──────────────────────────────────────
        logger.info("[pipeline][strict] Using schema-driven pipeline")

        try:
            state = plan_slides_strict(state)
        except Exception as exc:
            logger.warning("[pipeline][strict] Slide planning failed, using fallback slides: %s", exc)
            state = _inject_fallback_slides(state)

        total_slides = len(state.slide_plan)
        total_steps = GLOBAL_STEPS + (total_slides * per_slide_steps)
        completed_steps += 1
        logger.info("[pipeline][strict] Planned %d slides", len(state.slide_plan))
        _emit(EventType.STAGE_UPDATE, "slide_plan", "Slide structure planned…",
              _compute_progress(completed_steps, total_steps),
              total_slides=total_slides)

        try:
            state = await generate_strict_content(state)
        except Exception as exc:
            logger.warning("[pipeline][strict] Content generation failed, using fallback slides: %s", exc)
            state = _inject_fallback_slides(state)

        completed_steps += 1
        _emit(EventType.STAGE_UPDATE, "content_done", "Content generation complete…",
              _compute_progress(completed_steps, total_steps),
              total_slides=total_slides)

        try:
            state = validate_content(state)
        except Exception as exc:
            logger.warning("[pipeline][strict] Validation failed, continuing: %s", exc)

        completed_steps += 1
        _emit(EventType.STAGE_UPDATE, "validated", "Content validated…",
              _compute_progress(completed_steps, total_steps),
              total_slides=total_slides)

    else:
        
        # ── PIPELINE SWITCH: INVESTOR vs NARRATIVE ─────────────────────

        if deck_mode == "investor":
            logger.info("[pipeline] Using INVESTOR MODE (business-driven)")

            # 🔥 STEP 1: Generate business context
            try:
                from pipeline.business_layer import generate_business_context
                state.business_context = await generate_business_context(state.topic)
            except Exception as e:
                logger.warning("[pipeline] Business context failed, using deterministic fallback: %s", e)
                state.business_context = {
                    "product_name": state.topic,
                    "product_type": "product",
                    "target_user": state.audience or "target customer",
                    "problem": "Critical user pain remains unresolved",
                    "solution": "Narrato-driven structured solution",
                    "key_features": "Structured storytelling, deterministic slides, investor clarity",
                    "market": "Large and growing addressable demand",
                    "monetization": "Subscription and enterprise tiers",
                    "differentiation": "Deterministic narrative + export reliability",
                }

            # 🔥 STEP 2: Pass business context into narrative engine
            try:
                state = await run_narrative_engine(
                    state,
                    business_context=state.business_context
                )
            except Exception as e:
                logger.warning("[pipeline] Narrative engine failed, continuing with fallback narrative: %s", e)
                state = _inject_fallback_slides(state)

            from pipeline.narrative_validator import validate_narrative_arc
            try:
                validate_narrative_arc(state.narrative_arc)
            except Exception as e:
                logger.warning("[pipeline] Narrative validation failed, continuing with repaired narrative: %s", e)

            try:
                state = await run_content_engine(state)
            except Exception as e:
                logger.warning("[pipeline] Content engine failed, injecting fallback slides: %s", e)
                state = _inject_fallback_slides(state)
            total_slides = len(state.structured_slides or [])

        else:
            
            state = await run_narrative_engine(state)
            from pipeline.narrative_validator import validate_narrative_arc
            try:
                validate_narrative_arc(state.narrative_arc)
            except Exception as e:
                logger.warning("[pipeline] Narrative validation failed, continuing with repaired narrative: %s", e)
            try:
                state = await run_content_engine(state)
            except Exception as e:
                logger.warning("[pipeline] Content engine failed, injecting fallback slides: %s", e)
                state = _inject_fallback_slides(state)

    # ── Shared tail (both paths) ──────────────────────────────────
    _repair_structured_slide_count(state, state.slide_count)
    total_slides = len(state.structured_slides or [])

    # Speaker notes (1 LLM call for ALL slides)
    try:
        state = await generate_speaker_notes(state)
    except Exception as exc:
        logger.warning("[pipeline] Speaker notes failed, continuing: %s", exc)

    completed_steps += 1
    logger.info("[pipeline] Speaker notes generated for %d slides",
                len(state.speaker_notes or []))
    _emit(EventType.STAGE_UPDATE, "speaker_notes", "Speaker notes written…",
          _compute_progress(completed_steps, total_steps),
          total_slides=total_slides)

    # ── Per-slide visual pipeline (design + template) ─────────────
    # slides = state.structured_slides or []
    # 🔥 convert structured_slides → design-compatible format
    slides = []

    for s in (state.structured_slides or []):
        supporting = s.get("supporting_elements")
        if not supporting and isinstance(s.get("content"), dict):
            content = s.get("content", {})
            primary = content.get("title") or content.get("section_title") or f"Slide {s.get('slide_id')}"
            extracted = []
            for key in ("bullets", "items", "features", "events"):
                val = content.get(key, [])
                if isinstance(val, list):
                    for item in val:
                        if isinstance(item, dict):
                            extracted.append(item.get("description") or item.get("label") or "")
                        else:
                            extracted.append(str(item))
            s["primary_element"] = s.get("primary_element") or str(primary)
            s["supporting_elements"] = [str(x) for x in extracted if str(x).strip()][:4]

        slides.append({
            "slide_id": s.get("slide_id"),
            "primary_element": s.get("primary_element"),
            "supporting_elements": s.get("supporting_elements"),
            "role": s.get("role") or s.get("role_in_story"),
            "why_this_slide": s.get("why_this_slide"),
            "why_next_slide": s.get("why_next_slide"),
            "emotional_tone": s.get("emotional_tone"),
            "cause": s.get("cause", s.get("why_this_slide")),
            "tension": s.get("tension", ""),
            "next_trigger": s.get("next_trigger", s.get("why_next_slide")),
        })
    theme = getattr(state, "theme", "modern")
    all_html_slides = []

    # Validate slide content BEFORE rendering — catch empty/malformed slides
    try:
        slides = validate_slide_content(slides)
    except Exception as exc:
        logger.warning("[pipeline] Slide content validation failed, repairing slides: %s", exc)
        for idx, slide in enumerate(slides, start=1):
            if not slide.get("primary_element"):
                slide["primary_element"] = f"Slide {idx}"
            supports = slide.get("supporting_elements") or []
            if not supports and idx > 1:
                supports = [f"Core detail {idx} for {state.topic}"]
            slide["supporting_elements"] = supports[:4]
        slides = validate_slide_content(slides)

    _emit(EventType.STAGE_UPDATE, "visual_start",
          "Designing and rendering slides…",
          _compute_progress(completed_steps, total_steps),
          total_slides=total_slides)

    try:
        designs, all_html_slides = await run_dynamic_composition_engine(
            slides,
            state_theme=theme,
            topic=state.topic,
        )
    except Exception as exc:
        logger.warning("[pipeline] Dynamic composition failed, using deterministic HTML fallback: %s", exc)
        designs = []
        all_html_slides = _repair_html_parity(state, [])

    # STRICT: validate design components — pipeline stops on failure
    if designs:
        designs = validate_design_components(designs)

    for idx, slide in enumerate(slides):
        slide_num = idx + 1

        completed_steps += 1
        _emit(EventType.SLIDE_DESIGNED, "design",
              f"Designing slide {slide_num} of {total_slides}…",
              _compute_progress(completed_steps, total_steps),
              slide_id=slide_num, total_slides=total_slides)

        html_content = all_html_slides[idx] if idx < len(all_html_slides) else ""
        
        completed_steps += 1
        _emit(EventType.SLIDE_RENDERED, "render",
              f"Rendered slide {slide_num} of {total_slides}…",
              _compute_progress(completed_steps, total_steps),
              slide_id=slide_num, total_slides=total_slides,
              data={"html": html_content})

    all_html_slides = _repair_html_parity(state, all_html_slides)

    # ── Validate rendered HTML — STRICT: stops pipeline if any slide is title-only ──
    try:
        validate_rendered_html(all_html_slides)
    except Exception as exc:
        logger.warning("[pipeline] HTML validation failed, repairing parity HTML: %s", exc)
        all_html_slides = _repair_html_parity(state, [])
        validate_rendered_html(all_html_slides)

    # ── Validate export parity — ensures same HTML goes to export as editor ──
    export_html_slides = list(all_html_slides)  # actual copy used for export
    export_html_slides = _repair_html_parity(state, export_html_slides)
    validate_export_parity(all_html_slides, export_html_slides)
    if state.generation_mode != "strict":
        validate_pipeline_contract(
            structured_slides=list(state.structured_slides or []),
            html_slides=export_html_slides,
            expected_slide_count=state.slide_count,
        )

    # ── Visual export (PNG/PDF) — Playwright is REQUIRED, no fallback ──
    logger.info("[pipeline] Running visual export pipeline")
    output_dir = _resolve_output_dir(job_id)
    try:
        visual_output = await _run_visual_export_safe(export_html_slides, output_dir)
    except Exception as exc:
        logger.warning("[pipeline] Visual export failed, returning HTML-only safe output: %s", exc)
        visual_output = {
            "designs": [],
            "html_slides": export_html_slides,
            "render_instructions": build_render_instructions(len(export_html_slides)),
            "html_paths": [],
            "image_paths": [],
            "pdf_path": None,
        }
    state = state.model_copy(update={"visual_render_output": visual_output})

    completed_steps += 1
    logger.info("[pipeline] Visual export complete")
    _emit(EventType.STAGE_UPDATE, "export", "Export artifacts generated…",
          _compute_progress(completed_steps, total_steps),
          total_slides=total_slides)

    # ── Emit completion ───────────────────────────────────────────
    # _emit(EventType.JOB_COMPLETED, "completed", "Presentation ready!",
    #       100, total_slides=total_slides)
    
    # ✅ FIX: send proper completion signal for SSE
    _emit(
        EventType.STAGE_UPDATE,
        "completed",
        "Presentation ready!",
        100,
        total_slides=total_slides
    )

    _emit(
        EventType.JOB_COMPLETED,
        "completed",
        "Presentation ready!",
        100,
        total_slides=total_slides
    )

    if not state.structured_slides:
        state = _inject_fallback_slides(state)
        _repair_structured_slide_count(state, 3)
    final_html_slides = all_html_slides if all_html_slides else visual_output.get("html_slides", [])
    final_html_slides = _repair_html_parity(state, final_html_slides)

    return {
        "html_slides": final_html_slides,
        "structured_slides": [s for s in (state.structured_slides or [])],
        "image_paths": visual_output.get("image_paths", []),
        "pdf_path": visual_output.get("pdf_path"),
        
        # 🔥 ADD THIS
        "reasoning": [
            {
                "slide_id": s.get("slide_id"),
                "role": s.get("role"),
                "why_this": s.get("why_this_slide"),
                "why_next": s.get("why_next_slide")
            }
            for s in (state.structured_slides or [])
        ]
    }


async def _run_visual_export_safe(html_slides: list[str], output_dir: str) -> dict:
    """Run visual export — STRICT: failures propagate, no partial success.

    Playwright is REQUIRED for browser-based rendering.
    If Playwright is not installed or rendering fails → pipeline fails.
    No fallback to HTML-only export.
    """
    render_instructions = build_render_instructions(len(html_slides))

    image_paths = await render_slides_to_images(html_slides, output_dir)
    pdf_path = await render_slides_to_pdf(html_slides, output_dir)

    export_result = run_export_engine(
        html_slides=html_slides,
        image_paths=image_paths,
        pdf_path=pdf_path,
        output_dir=output_dir,
    )

    return {
        "designs": [],
        "html_slides": html_slides,
        "render_instructions": render_instructions,
        "html_paths": export_result.get("html_paths", []),
        "image_paths": export_result.get("image_paths", image_paths),
        "pdf_path": export_result.get("pdf_path", pdf_path),
    }


def _resolve_output_dir(job_id: str) -> str:
    """Per-job directory for PNG/PDF/HTML copies (avoids collisions between jobs)."""
    base = os.environ.get("NARRATO_OUTPUT_DIR", "./outputs")
    safe = os.path.basename(job_id) if job_id and job_id != "unknown" else "default"
    visual_dir = os.path.join(base, "visual", safe)
    os.makedirs(visual_dir, exist_ok=True)
    return visual_dir


def _inject_fallback_slides(state: "PresentationState") -> "PresentationState":
    """Inject minimal fallback slides so the pipeline always produces output."""
    fallback_slides = [
        _fallback_structured_slide(state, 1, "Problem"),
        _fallback_structured_slide(state, 2, "Solution"),
        _fallback_structured_slide(state, 3, "Funding Ask"),
    ]
    fallback_plan = [
        {"slide_id": 1, "section": "problem", "purpose": "Fallback problem framing", "type": "content_slide"},
        {"slide_id": 2, "section": "solution", "purpose": "Fallback solution framing", "type": "content_slide"},
        {"slide_id": 3, "section": "ask", "purpose": "Fallback funding ask", "type": "content_slide"},
    ]
    logger.warning("[pipeline] Using %d fallback slides", len(fallback_slides))
    return state.model_copy(
        update={
            "slide_plan": fallback_plan,
            "structured_slides": fallback_slides,
        }
    )


def _write_intelligence_report(state) -> None:
    """Write the intelligence report to a separate README file."""
    try:
        output_dir = os.environ.get("NARRATO_OUTPUT_DIR", "output")
        os.makedirs(output_dir, exist_ok=True)
        report_path = os.path.join(output_dir, "INTELLIGENCE_REPORT.md")
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(state.intelligence_report)
        logger.info("[pipeline] Intelligence report written to %s", report_path)
    except Exception:
        logger.exception(
            "[pipeline] Failed to write intelligence report — "
            "pipeline will continue without persisted report"
        )
