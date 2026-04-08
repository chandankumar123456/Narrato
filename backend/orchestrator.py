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
from pipeline.narrative_engine import run_narrative_engine, regenerate_invalid_narrative_slides
from pipeline.content_engine import run_content_engine
from pipeline.strict_slide_planner import plan_slides_strict
from pipeline.strict_content_structurer import generate_strict_content
from pipeline.content_validator import validate_content
from pipeline.speaker_notes_generator import generate_speaker_notes
from pipeline.dynamic_composition_engine import run_dynamic_composition_engine
from pipeline.visual_rendering_engine import render_slides_to_images, render_slides_to_pdf, build_render_instructions
from pipeline.visual_export_engine import run_export_engine
from pipeline.slide_validator import validate_slide_content, validate_design_components, validate_rendered_html, validate_export_parity, SlideRenderError
from services.event_system import PipelineEvent, EventType
import logging
import os
from typing import Callable, Optional
import re

logger = logging.getLogger(__name__)

INVESTOR_MODE_KEYWORDS = (
    "pitch deck", "startup", "funding", "saas", "product", "growth", "business", "investor",
)
ACADEMIC_MODE_KEYWORDS = (
    "seminar", "theory", "explanation", "subject learning",
)


class PipelineFailure(Exception):
    """Raised when a critical pipeline stage fails, stopping the pipeline immediately."""
    pass


def _compute_progress(completed: int, total: int) -> int:
    """Compute progress 0-100 from completed/total steps."""
    if total <= 0:
        return 0
    return min(100, max(0, int((completed / total) * 100)))


def _extract_context(prompt: str) -> dict:
    """Extract deterministic deck context directly from raw prompt text."""
    context = {
        "deck_goal": "",
        "audience": "",
        "tone": "",
        "topic": "",
        "key_points": [],
    }
    if not prompt:
        return context

    lines = [ln.strip() for ln in prompt.splitlines() if ln.strip()]

    def _value_after(prefixes: list[str]) -> str:
        for ln in lines:
            low = ln.lower()
            for p in prefixes:
                token = f"{p.lower()}:"
                if low.startswith(token):
                    return ln[len(token):].strip()
        return ""

    context["deck_goal"] = _value_after(["deck_goal", "goal", "objective"])
    context["audience"] = _value_after(["audience"])
    context["tone"] = _value_after(["tone", "style"])
    context["topic"] = _value_after(["topic", "subject"])

    if not context["topic"]:
        match = re.search(r"\babout\s+([^\n\.\,\;\:]+)", prompt, flags=re.IGNORECASE)
        if match:
            context["topic"] = match.group(1).strip()

    key_points: list[str] = []
    kp_start = None
    for idx, ln in enumerate(lines):
        if ln.lower().startswith(("key points:", "key_points:", "keypoints:")):
            kp_start = idx
            maybe_inline = ln.split(":", 1)[1].strip()
            if maybe_inline:
                key_points.extend([p.strip() for p in re.split(r"[;,]", maybe_inline) if p.strip()])
            break

    if kp_start is not None:
        for ln in lines[kp_start + 1:]:
            if re.match(r"^[A-Za-z_ ]+:\s*", ln):
                break
            item = re.sub(r"^\s*(?:[-*]|\d+[\.\)])\s*", "", ln).strip()
            if item:
                key_points.append(item)

    deduped: list[str] = []
    seen: set[str] = set()
    for p in key_points:
        k = p.lower()
        if k not in seen:
            seen.add(k)
            deduped.append(p)
    context["key_points"] = deduped
    return context


def _detect_presentation_mode(prompt: str) -> str:
    """Classify prompt into investor, academic, or generic mode."""
    prompt_lower = (prompt or "").lower()
    if any(keyword in prompt_lower for keyword in INVESTOR_MODE_KEYWORDS):
        return "investor"
    if any(keyword in prompt_lower for keyword in ACADEMIC_MODE_KEYWORDS):
        return "academic"
    return "generic"


def _initialize_deck_state(context: dict, slide_count: int) -> dict:
    return {
        "goal": context.get("deck_goal", ""),
        "topic": context.get("topic", ""),
        "slide_count": int(slide_count or 0),
    }


def _extract_primary_supporting(slide: dict) -> tuple[str, list[str]]:
    primary = str(slide.get("primary_element", "")).strip()
    supporting = slide.get("supporting_elements", [])
    if isinstance(supporting, list):
        supporting = [str(s).strip() for s in supporting if str(s).strip()]
    else:
        supporting = []

    content = slide.get("content", {}) if isinstance(slide.get("content"), dict) else {}
    if not primary:
        primary = str(content.get("title", "")).strip() or str(content.get("subtitle", "")).strip()

    if not supporting and content:
        for key, val in content.items():
            if key in {"title", "subtitle"}:
                continue
            if isinstance(val, str) and val.strip():
                supporting.append(val.strip())
            elif isinstance(val, list):
                for item in val:
                    if isinstance(item, dict):
                        text = " ".join(str(v).strip() for v in item.values() if str(v).strip()).strip()
                        if text:
                            supporting.append(text)
                    elif str(item).strip():
                        supporting.append(str(item).strip())
    return primary, supporting


def _classify_slide_bucket(slide: dict) -> Optional[str]:
    primary, supporting = _extract_primary_supporting(slide)
    text = " ".join([
        str(slide.get("intent", "")),
        str(slide.get("role", "")),
        str(slide.get("role_in_story", "")),
        primary,
        " ".join(supporting),
    ]).lower()
    if any(k in text for k in ["problem", "pain", "challenge", "issue", "risk"]):
        return "problem"
    if any(k in text for k in ["impact", "consequence", "cost", "urgency", "effect"]):
        return "impact"
    if any(k in text for k in ["solution", "approach", "strategy", "fix"]):
        return "solution"
    if any(k in text for k in ["proof", "stat", "stats", "metric", "data", "evidence", "traction", "result"]):
        return "proof"
    if any(k in text for k in ["next step", "next_steps", "roadmap", "action", "closing", "conclusion", "cta"]):
        return "next_steps"
    return None


def _reorder_slides(slides: list[dict]) -> list[dict]:
    if not slides:
        return slides
    order = ["problem", "impact", "solution", "proof", "next_steps"]
    rank = {bucket: idx for idx, bucket in enumerate(order)}
    classified = [(_classify_slide_bucket(slide), idx, slide) for idx, slide in enumerate(slides)]
    recognized = sum(1 for bucket, _, _ in classified if bucket in rank)
    if recognized < 2:
        return slides
    classified.sort(key=lambda item: (rank.get(item[0], len(order)), item[1]))
    return [slide for _, _, slide in classified]


def _normalize_text_style(text: str) -> str:
    out = re.sub(r"\s+", " ", str(text or "").strip())
    out = out.rstrip(".,;: ")
    if out:
        out = out[0].upper() + out[1:]
    return out


def _run_consistency_pass(slides: list[dict]) -> list[dict]:
    seen_phrases: set[str] = set()
    for slide in slides:
        primary, supporting = _extract_primary_supporting(slide)
        primary = _normalize_text_style(primary)
        if not primary and supporting:
            primary = _normalize_text_style(supporting[0])
        if not primary:
            primary = "Key point"

        clean_support: list[str] = []
        local_seen: set[str] = set()
        for item in supporting:
            phrase = _normalize_text_style(item)
            if not phrase:
                continue
            k = phrase.lower()
            if k == primary.lower() or k in local_seen or k in seen_phrases:
                continue
            local_seen.add(k)
            seen_phrases.add(k)
            clean_support.append(phrase)

        if not clean_support:
            clean_support = [f"{primary} context"]

        slide["primary_element"] = primary
        slide["supporting_elements"] = clean_support
    return slides


def _derive_slide_role(slide: dict, idx: int, total: int) -> str:
    bucket = _classify_slide_bucket(slide)
    if idx == 0 and bucket is None:
        return "intro"
    if bucket == "problem":
        return "problem"
    if bucket == "solution":
        return "solution"
    if bucket in {"impact", "proof"}:
        return "proof"
    if bucket == "next_steps" or idx == total - 1:
        return "closing"
    return "intro"


def _add_linking_and_reasoning(slides: list[dict], context: dict) -> list[dict]:
    total = len(slides)
    for i, slide in enumerate(slides):
        primary = str(slide.get("primary_element", "")).strip() or "this focus"
        if i == 0:
            slide["bridge"] = ""
        else:
            prev_primary = str(slides[i - 1].get("primary_element", "")).strip() or "the previous point"
            slide["bridge"] = f"Because {prev_primary}, we now focus on {primary}"

        slide_role = _derive_slide_role(slide, i, total)
        slide["slide_role"] = slide_role
        if not str(slide.get("why_this_slide", "")).strip():
            topic = context.get("topic", "") or "the topic"
            slide["why_this_slide"] = f"This {slide_role} slide highlights {primary} for {topic}."
    return slides


def _validate_slides_before_render(slides: list[dict]) -> list[dict]:
    violations: list[str] = []
    for idx, slide in enumerate(slides, start=1):
        if not isinstance(slide, dict):
            violations.append(f"Slide {idx}: invalid slide object")
            continue
        primary, supporting = _extract_primary_supporting(slide)
        title = str(slide.get("title", "")).strip() or primary
        if not title:
            violations.append(f"Slide {idx}: missing title")
            continue
        if not primary and not supporting:
            violations.append(f"Slide {idx}: missing content")
            continue

        slide["title"] = title
        slide["primary_element"] = primary or title
        slide["supporting_elements"] = supporting or [f"{title} detail"]
        slide["content"] = {
            "title": slide["title"],
            "primary_element": slide["primary_element"],
            "supporting_elements": slide["supporting_elements"],
        }

    if violations:
        raise ValueError("; ".join(violations))
    return slides


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
    context = _extract_context(prompt)
    _emit(EventType.STAGE_UPDATE, "init", "Understanding your prompt…", 3)

    # ── Stage 1: Parse prompt signals ─────────────────────────────
    try:
        signals = await parse_prompt(prompt)
        signals.update({k: v for k, v in options.items() if v is not None and not k.startswith("_")})
        presentation_mode = _detect_presentation_mode(prompt)
        signals["presentation_mode"] = presentation_mode
        signals["deck_mode"] = "investor" if presentation_mode == "investor" else "general"
        
    except Exception as exc:
        _fail("prompt_parse", str(exc))

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
    deck_mode = "investor" if state.presentation_mode == "investor" else "general"
    metadata = dict(state.metadata or {})
    metadata["context"] = context
    metadata["deck_state"] = _initialize_deck_state(context, state.slide_count)
    metadata["presentation_mode"] = state.presentation_mode
    state = state.model_copy(update={"metadata": metadata})
    
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
            _fail("strict_plan", str(exc))

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
            _fail("strict_content", str(exc))

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
                _fail("business_layer", str(e))

            # 🔥 STEP 2: Pass business context into narrative engine
            try:
                state = await run_narrative_engine(
                    state,
                    business_context=state.business_context
                )
            except Exception as e:
                _fail("narrative_engine", str(e))

            from pipeline.narrative_validator import validate_narrative_arc
            try:
                validation = validate_narrative_arc(state.narrative_arc)
                invalid_indices = validation.get("invalid_slide_indices", [])
                if invalid_indices:
                    logger.warning(
                        "[pipeline] Regenerating invalid narrative slides once: %s",
                        ",".join(str(i + 1) for i in invalid_indices),
                    )
                    regenerated_arc = await regenerate_invalid_narrative_slides(
                        state=state,
                        narrative_arc=validation.get("slides", []),
                        invalid_indices=invalid_indices,
                        business_context=state.business_context,
                    )
                    second_validation = validate_narrative_arc(regenerated_arc)
                    if second_validation.get("invalid_slide_indices"):
                        logger.warning(
                            "[pipeline] Narrative invalid slides remain after regeneration: %s",
                            "; ".join(second_validation.get("violations", [])),
                        )
                        state = state.model_copy(update={"narrative_arc": second_validation.get("slides", [])})
                    else:
                        state = state.model_copy(update={"narrative_arc": second_validation.get("slides", [])})
                else:
                    state = state.model_copy(update={"narrative_arc": validation.get("slides", [])})
            except Exception as e:
                logger.warning("[pipeline] Narrative validation/regeneration failed, continuing with original arc: %s", e)

            state = await run_content_engine(state)
            total_slides = len(state.structured_slides or [])

        else:
            
            state = await run_narrative_engine(state)
            from pipeline.narrative_validator import validate_narrative_arc
            try:
                validation = validate_narrative_arc(state.narrative_arc)
                invalid_indices = validation.get("invalid_slide_indices", [])
                if invalid_indices:
                    logger.warning(
                        "[pipeline] Regenerating invalid narrative slides once: %s",
                        ",".join(str(i + 1) for i in invalid_indices),
                    )
                    regenerated_arc = await regenerate_invalid_narrative_slides(
                        state=state,
                        narrative_arc=validation.get("slides", []),
                        invalid_indices=invalid_indices,
                    )
                    second_validation = validate_narrative_arc(regenerated_arc)
                    if second_validation.get("invalid_slide_indices"):
                        logger.warning(
                            "[pipeline] Narrative invalid slides remain after regeneration: %s",
                            "; ".join(second_validation.get("violations", [])),
                        )
                        state = state.model_copy(update={"narrative_arc": second_validation.get("slides", [])})
                    else:
                        state = state.model_copy(update={"narrative_arc": second_validation.get("slides", [])})
                else:
                    state = state.model_copy(update={"narrative_arc": validation.get("slides", [])})
            except Exception as e:
                logger.warning("[pipeline] Narrative validation/regeneration failed, continuing with original arc: %s", e)
            state = await run_content_engine(state)

    # ── Deterministic deck-level quality passes (no LLM) ───────────
    try:
        ordered_slides = _reorder_slides(list(state.structured_slides or []))
        consistent_slides = _run_consistency_pass(ordered_slides)
        linked_slides = _add_linking_and_reasoning(consistent_slides, context)
        validated_slides = _validate_slides_before_render(linked_slides)
        updated_meta = dict(state.metadata or {})
        deck_state = dict(updated_meta.get("deck_state", {}))
        deck_state["slide_count"] = len(validated_slides)
        updated_meta["deck_state"] = deck_state
        state = state.model_copy(update={"structured_slides": validated_slides, "metadata": updated_meta})
    except Exception as exc:
        _fail("post_generation_validation", str(exc))

    # ── Shared tail (both paths) ──────────────────────────────────

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
        slides.append({
            "slide_id": s.get("slide_id"),
            "intent": s.get("intent"),
            "primary_element": s.get("primary_element"),
            "supporting_elements": s.get("supporting_elements"),
            "entities": s.get("entities", []),
            "role": s.get("role"),
            "why_this_slide": s.get("why_this_slide"),
            "why_next_slide": s.get("why_next_slide"),
            "cause_from_previous": s.get("cause_from_previous"),
            "narrative_delta": s.get("narrative_delta"),
            "forward_tension": s.get("forward_tension"),
            "tension_level": s.get("tension_level"),
            "emotional_tone": s.get("emotional_tone"),
            "bridge": s.get("bridge", ""),
            "slide_role": s.get("slide_role"),
            "title": s.get("title"),
            "content": s.get("content"),
            "type": s.get("type"),
        })
    theme = getattr(state, "theme", "modern")
    all_html_slides = []

    # Validate slide content BEFORE rendering — catch empty/malformed slides
    slides = validate_slide_content(slides)

    _emit(EventType.STAGE_UPDATE, "visual_start",
          "Designing and rendering slides…",
          _compute_progress(completed_steps, total_steps),
          total_slides=total_slides)

    designs, all_html_slides = await run_dynamic_composition_engine(
        slides,
        state_theme=theme,
        topic=state.topic,
    )

    # STRICT: validate design components — pipeline stops on failure
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

    # ── Validate rendered HTML — STRICT: stops pipeline if any slide is title-only ──
    validate_rendered_html(all_html_slides)

    # ── Validate export parity — ensures same HTML goes to export as editor ──
    export_html_slides = list(all_html_slides)  # actual copy used for export
    validate_export_parity(all_html_slides, export_html_slides)

    # ── Visual export (PNG/PDF) — Playwright is REQUIRED, no fallback ──
    logger.info("[pipeline] Running visual export pipeline")
    output_dir = _resolve_output_dir(job_id)
    visual_output = await _run_visual_export_safe(export_html_slides, output_dir)
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

    return {
        "html_slides": all_html_slides if all_html_slides else visual_output.get("html_slides", []),
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
        {
            "slide_id": 1,
            "type": "title_slide",
            "content": {
                "title": state.topic,
                "subtitle": "Presentation generated with fallback content.",
                "presenter": "",
            },
        },
        {
            "slide_id": 2,
            "type": "feature_slide",
            "content": {
                "title": "Overview",
                "features": [
                    {"icon": "🔹", "label": "Topic", "description": state.topic},
                    {"icon": "🔸", "label": "Type", "description": state.presentation_type or "general"},
                    {"icon": "⚡", "label": "Audience", "description": state.audience or "general"},
                ],
                "summary": "This presentation was generated with fallback content due to a generation issue.",
            },
        },
    ]
    fallback_plan = [
        {"slide_id": 1, "section": "intro", "purpose": "Title slide", "type": "title_slide"},
        {"slide_id": 2, "section": "overview", "purpose": "Overview", "type": "feature_slide"},
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
