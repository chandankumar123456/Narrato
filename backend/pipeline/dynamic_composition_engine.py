import logging
import asyncio
from pathlib import Path
import html
from services.llm_client import call_llm_json
from pipeline.visual_narrative_control import compute_visual_plan, format_visual_plan_for_renderer
from pipeline.narrative_transform import transform_narrative
from pipeline.content_integrity import verify_narrative_to_preprocess, verify_preprocess_to_render

logger = logging.getLogger(__name__)

def _load_slides_css() -> str:
    css_path = Path(__file__).resolve().parent / "static" / "slides.css"
    if css_path.exists():
        return css_path.read_text(encoding="utf-8")
    return ""

_HTML_WRAPPER = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=1920,height=1080"/>
<title>Slide</title>
<style>
{slides_css}
</style>
{custom_style}
</head>
<body>
<div class="slide" data-theme="{theme}">
{inner_html}
</div>
</body>
</html>"""

def _esc(text: str) -> str:
    return html.escape(str(text)) if text else ""

THEME_GENERATION_PROMPT = """You are a Visual System Architect. Generate a strictly consistent theme structure for the entire presentation.

Return a JSON object with EXACTLY these keys:
- "background": string ("dark" or "light")
- "primary_color": string (hex code or descriptive like "vibrant blue")
- "font_scale": string (e.g. "massive headers, constrained body")
- "spacing_scale": string (e.g. "cozy", "spacious", "dense")

IMPORTANT: Only return JSON. No markdown backticks or preamble.
"""

PREPROCESS_PROMPT = """You are a Content Structure and Hierarchy Engine. Your goal is to map presentation content into strictly controlled, structured textual elements WITHOUT semantic loss.

IMPORTANT — NARRATIVE ENRICHMENT:
If the input contains a `_narrative_text` field, this has ALREADY been transformed into story-driven language by a Narrative Transformation Layer. You MUST:
- Use `_narrative_text` as your PRIMARY source of meaning for `primary_element` and `supporting_elements`.
- The `_narrative_angle` tells you the storytelling angle — respect it in how you structure the hierarchy.
- Still reference the original content fields (title, punchline, etc.) for factual accuracy, but the narrative text carries the EXPRESSION.

MANDATORY RULES:
1. CONTENT PRESERVATION: Keep meaning intact. Preserve causal or explanatory depth. NEVER reduce content to single words, abstract labels (like "Growth"), or remove explanatory meaning.
2. CONTENT STRUCTURE: Output must contain "intent", "title", "primary_element", "supporting_elements", and "entities".
3. PRIMARY ELEMENT VS TITLE: `primary_element` MUST contain the strongest meaning. `title` and `primary_element` must NOT overwrite each other. If a title is missing, derive it from the primary_element.
4. SUPPORTING ELEMENTS: Every non-initial slide MUST have 1 to 3 "supporting_elements". Each element must be a meaningful line of 8-12 words. Extract these from the narrative text — each should carry a distinct supporting idea.
5. NARRATIVE DEPTH: If `_narrative_text` is present, your output MUST reflect its depth. Do NOT flatten the narrative back into shallow bullet points.

Output a JSON object with:
- "intent": the overall layout intent. Only the first slide may behave as a minimal (hero) slide.
- "title": string (derive from primary_element if missing).
- "primary_element": a string representation of the dominant focal point (meaning intact).
- "supporting_elements": an array of short strings strictly supporting the primary point.
- "entities": an array of 1-3 key entities.

IMPORTANT: Only return JSON. No markdown backticks or preamble.
"""

RENDER_PROMPT = """You are a master presentation designer. Your task is to output the perfect, custom HTML and CSS for a single presentation slide, using the highly controlled content provided.
Do NOT use rigid templates or structured gridding unless mathematically necessary.

CRITICAL: A VISUAL PLAN is provided with each slide. You MUST follow it EXACTLY:
- LAYOUT: Use the specified layout type and its positioning directive. DO NOT deviate.
- DENSITY: Respect the density level (minimal/medium/high) — do not add or remove content beyond what it specifies.
- EMPHASIS: Follow the emphasis mode (primary/supporting/balanced) to control visual weight.
- ALIGNMENT: Use the specified alignment (center/left/right/mixed).
- NARRATIVE ROLE: The visual intent describes the emotional feel — your design must reflect it.

DESIGN RULES (MANDATORY):
1. ONE DOMINANT ELEMENT: Use the provided `primary_element`. You MUST style it to be 2x-4x larger or more prominent than secondary elements.
2. ALL SUPPORTING ELEMENTS VISIBLE: Ensure every item in `supporting_elements` is explicitly rendered in the HTML. No summarization, omission, or transformation. Output the exact or semantically equivalent text.
3. LAYOUT FROM VISUAL PLAN: Follow the layout directive from the VISUAL PLAN section. Do NOT default to centered vertical stacking unless the plan says center_focus.
4. WHITESPACE ENFORCEMENT: Maintain 40-60% empty space across the layout. Do not make the slide dense.
5. DESIGN CONSISTENCY: Enforce spacing, typography, and color palette from the theme exactly. Use relative sizing (rem, em) or percentages (%), not random fixed pixel sets.

Context constraints: No images. Only vanilla CSS/HTML. 

Return a JSON object with:
- "html": The body content of the layout. (Do not wrap in <html> or <body>).
- "css": Any custom CSS you want placed in a <style> block specific to this layout. Use classes.

IMPORTANT: Only return JSON. No markdown backticks or preamble.
"""

VALIDATE_PROMPT = """You are a Visual Design Validator. Analyze the generated HTML and CSS. You are verifying strict visual design goals.

The slide has a VISUAL PLAN that the renderer was required to follow. Verify compliance.

CRITERIA:
1. dominant_element_present: Does the HTML/CSS clearly contain ONE element structured as the primary element and styled distinctly larger?
2. all_supporting_elements_present: Are ALL supporting elements from the structured content explicitly present and visible in the HTML without omission or collapsing?
3. layout_follows_plan: Does the rendered HTML follow the VISUAL PLAN's layout directive? (e.g. center_focus = centered, left_heavy = left-anchored, split = two-column, etc.)
4. whitespace_present: Does the layout logically contain 40-60% breathing space given the CSS constraints?
5. thesis_preserved: Is the narrative meaning and explanatory depth fully preserved (no single words/abstract reductions without context)?
6. theme_consistent: Does the HTML/CSS precisely use the provided theme (background, primary_color, font_scale, spacing_scale)?

Output a JSON object with:
- "dominant_element_present": boolean
- "all_supporting_elements_present": boolean
- "layout_follows_plan": boolean
- "whitespace_present": boolean
- "thesis_preserved": boolean
- "theme_consistent": boolean
- "critique": If any boolean is false, write a strictly brief 1-2 sentence direction to fix it. If all true, return empty string.

IMPORTANT: Only return JSON. No markdown backticks or preamble.
"""

async def generate_slide_html(slide_data: dict, slide_index: int, total_slides: int, theme_dict: dict, continuity_context: dict, layout_history: list[str], topic: str = "") -> tuple[dict, str, dict]:
    """Generates custom HTML and CSS for a single slide using a multi-step control layer."""
    content = slide_data.get("content", {})
    intent_str = slide_data.get("intent", "")
    
    # Step 7: Enforce Role -> Design Binding (role and emotional_tone are within intent_str if mapped perfectly)
    emotional_tone = slide_data.get("emotional_tone", "")
    role_in_story = slide_data.get("role_in_story", "")
    
    # ── Phase 0: Narrative Transformation (understand → interpret → express) ──
    # Runs BEFORE preprocessing to convert shallow content into story-driven text.
    # This is the "thinking layer" that was missing.
    narrative_result = await transform_narrative(
        raw_content=content,
        slide_index=slide_index,
        total_slides=total_slides,
        topic=topic,
        narrative_role=role_in_story,
        emotional_tone=emotional_tone,
    )
    
    narrative_text = narrative_result.get("narrative_text", "")
    narrative_entities = narrative_result.get("key_entities", [])
    narrative_angle = narrative_result.get("narrative_angle", "")
    
    # Enrich the content with the narrative transformation output.
    # The preprocessor will now receive deeper, story-driven text instead of raw data.
    if narrative_text and narrative_angle != "passthrough":
        # Inject the narrative text into the content so the preprocessor structures it
        enriched_content = dict(content) if isinstance(content, dict) else {"raw": str(content)}
        enriched_content["_narrative_text"] = narrative_text
        enriched_content["_narrative_angle"] = narrative_angle
        logger.info(
            "Slide %d: Narrative enrichment applied — angle='%s'",
            slide_index + 1, narrative_angle,
        )
    else:
        enriched_content = content
    
    # Feed narrative entities into continuity context early
    if isinstance(narrative_entities, list) and narrative_entities:
        continuity_context["entities"].extend(narrative_entities)
        continuity_context["entities"] = list(set(continuity_context["entities"]))[-10:]
    
    base_prompt = f"Intent/Role/Tone: {intent_str} | {role_in_story} | {emotional_tone}\nNarrative Angle: {narrative_angle}\nPrevious Entities: {continuity_context.get('entities', [])}\nGlobal Keywords: {continuity_context.get('global_keywords', [])}\nContent:\n{enriched_content}"
    
    # Phase 1: Preprocessing & Content Reduction
    preprocessing_result = {}
    preprocess_feedback = ""
    for attempt in range(max_retries := 3):
        prompt = base_prompt
        if preprocess_feedback:
            prompt += f"\n\nPREVIOUS ATTEMPT FAILED. FIX:\n{preprocess_feedback}"
            
        try:
            preprocessing_result = await call_llm_json(PREPROCESS_PROMPT, prompt)
            
            # Extract and validate
            title = preprocessing_result.get("title", "").strip()
            primary = preprocessing_result.get("primary_element", "").strip()
            sups = preprocessing_result.get("supporting_elements", [])
            
            if not title and primary:
                title = primary
                preprocessing_result["title"] = title
            if not primary and title:
                primary = title
                preprocessing_result["primary_element"] = primary
                
            if not title and not primary:
                raise ValueError("Both title and primary element are empty.")
                
            if slide_index > 0:
                if not sups or not isinstance(sups, list) or len(sups) == 0:
                    raise ValueError("Supporting elements are empty on non-initial slide.")
                for s in sups:
                    words = len(str(s).split())
                    if words <= 2:
                        raise ValueError("Supporting element is a single word or empty.")
            
            # Passed strict validation
            break
        except Exception as e:
            logger.warning(f"Slide {slide_index + 1}: Preprocessing attempt {attempt + 1} failed: {e}")
            preprocess_feedback = str(e)
            if attempt == max_retries - 1:
                logger.error(f"Slide {slide_index + 1}: Preprocessing failed validation after {max_retries} attempts.")
                # Fallback must NEVER produce empty or single-word outputs
                safe_title = content.get("title", f"Slide {slide_index + 1}")
                if not str(safe_title).strip():
                    safe_title = "Important Concept"
                preprocessing_result = {
                    "intent": intent_str or "content",
                    "title": safe_title,
                    "primary_element": safe_title,
                    "supporting_elements": ["This section covers key points about the topic."] if slide_index > 0 else [],
                    "entities": []
                }

    # Step 8: Update memory tracking
    new_entities = preprocessing_result.get("entities", [])
    if isinstance(new_entities, list):
        continuity_context["entities"].extend(new_entities)
        continuity_context["entities"] = list(set(continuity_context["entities"]))[-10:] # keep last 10
        continuity_context["global_keywords"].extend(new_entities)
        continuity_context["global_keywords"] = list(set(continuity_context["global_keywords"]))[-20:]

    # ── INTEGRITY CHECKPOINT 1: Narrative → Preprocess Alignment ─────
    # Verify preprocessing preserved narrative meaning. If not, feed the
    # fix directive back and re-preprocess (targeted fix, not full regen).
    if narrative_text and narrative_angle != "passthrough":
        integrity_1 = await verify_narrative_to_preprocess(
            narrative_text=narrative_text,
            narrative_angle=narrative_angle,
            preprocessing_result=preprocessing_result,
            slide_index=slide_index,
        )
        if integrity_1["status"] == "fail":
            fix_directive = integrity_1["fix_directive"]
            logger.warning(
                "Slide %d: INTEGRITY FAIL (narrative→preprocess) — attempting targeted fix: %s",
                slide_index + 1, fix_directive,
            )
            # One targeted re-preprocess with the fix directive
            fix_prompt = (
                base_prompt +
                f"\n\nINTEGRITY ENFORCEMENT — YOUR PREVIOUS OUTPUT FAILED ALIGNMENT CHECK.\n"
                f"FIX DIRECTIVE: {fix_directive}\n"
                f"ORIGINAL NARRATIVE TEXT (source of truth):\n{narrative_text}\n"
                f"You MUST use this narrative text to derive primary_element and supporting_elements."
            )
            try:
                fixed_result = await call_llm_json(PREPROCESS_PROMPT, fix_prompt)
                # Re-validate basics
                ftitle = fixed_result.get("title", "").strip()
                fprimary = fixed_result.get("primary_element", "").strip()
                if ftitle and fprimary and len(fprimary.split()) > 1:
                    preprocessing_result = fixed_result
                    logger.info("Slide %d: INTEGRITY fix applied successfully", slide_index + 1)
                else:
                    logger.warning("Slide %d: INTEGRITY fix produced weak output — keeping original", slide_index + 1)
            except Exception as fix_err:
                logger.warning("Slide %d: INTEGRITY fix LLM call failed: %s", slide_index + 1, fix_err)

    # ── Phase 1.5: Visual + Narrative Control Layer ──────────────────
    visual_plan = compute_visual_plan(
        slide_index=slide_index,
        total_slides=total_slides,
        preprocessing_result=preprocessing_result,
        layout_history=layout_history,
    )
    visual_plan_block = format_visual_plan_for_renderer(visual_plan)
    logger.info("Slide %d: Visual plan → role=%s layout=%s density=%s",
                slide_index + 1, visual_plan['narrative_role'],
                visual_plan['layout'], visual_plan['density'])

    # Phase 2 & 3: Generation & Validation Loop
    html_content = ""
    css_content = ""
    max_retries = 3
    
    render_input = f"Slide {slide_index + 1}:\nDistilled Content:\n{preprocessing_result}\nTheme: {theme_dict}\nEmotional Tone: {emotional_tone}{visual_plan_block}"
    validation_feedback = ""
    
    for attempt in range(max_retries):
        current_render_prompt = render_input
        if validation_feedback:
            current_render_prompt += f"\n\nPREVIOUS ATTEMPT FAILED. FEEDBACK TO FIX:\n{validation_feedback}"
            
        try:
            render_result = await call_llm_json(RENDER_PROMPT, current_render_prompt)
            if not isinstance(render_result, dict):
                raise ValueError("Render output not JSON dict.")
            html_content = render_result.get("html", "")
            css_content = render_result.get("css", "")
        except Exception as e:
            logger.error(f"Slide {slide_index + 1}: RENDER attempt {attempt + 1} failed: {e}")
            continue
            
        # Validate
        validation_input = f"Generated HTML:\n{html_content}\n\nGenerated CSS:\n{css_content}\nTheme Context: {theme_dict}\nStructured Content:\n{preprocessing_result}{visual_plan_block}"
        try:
            validation_result = await call_llm_json(VALIDATE_PROMPT, validation_input)
            if not isinstance(validation_result, dict):
                continue
            
            # Check constraints
            dom = validation_result.get("dominant_element_present", False)
            all_sups = validation_result.get("all_supporting_elements_present", False)
            layout_ok = validation_result.get("layout_follows_plan", False)
            ws = validation_result.get("whitespace_present", False)
            thesis_pres = validation_result.get("thesis_preserved", False)
            theme_consistent = validation_result.get("theme_consistent", False)
            
            if dom and all_sups and layout_ok and ws and thesis_pres and theme_consistent:
                logger.info(f"Slide {slide_index + 1}: Layout passed validation on attempt {attempt + 1}")
                break
            else:
                validation_feedback = validation_result.get("critique", "Layout failed structural checks.")
                logger.info(f"Slide {slide_index + 1}: Validation failed on attempt {attempt + 1}. Feedback: {validation_feedback}")
        except Exception as e:
            logger.warning(f"Slide {slide_index + 1}: Validation call failed: {e}.")
            if "HARD FAILURE" in str(e):
                raise e # Propagate hard failures
            continue
    else:
        # Loop exhausted without breaking
        logger.error(f"Slide {slide_index + 1}: HARD FAILURE validation retries exhausted. Rejecting slide generation.")
        raise RuntimeError("HARD FAILURE: Slide failed validation after retries")

    # ── INTEGRITY CHECKPOINT 2: Preprocess → Render Alignment ────────
    # Verify ALL structured content appears in rendered HTML.
    # Replaces the old hard substring check with layered enforcement.
    integrity_2 = await verify_preprocess_to_render(
        preprocessing_result=preprocessing_result,
        html_content=html_content,
        slide_index=slide_index,
    )
    if integrity_2["status"] == "fail":
        missing = integrity_2.get("missing_elements", [])
        fix_dir = integrity_2.get("fix_directive", "")
        logger.warning(
            "Slide %d: INTEGRITY FAIL (preprocess→render) — missing=%s fix=%s",
            slide_index + 1, missing, fix_dir,
        )
        # Attempt ONE targeted re-render with enforcement directive
        enforcement_prompt = (
            render_input +
            f"\n\nCONTENT INTEGRITY ENFORCEMENT — YOUR PREVIOUS RENDER IS MISSING CONTENT.\n"
            f"MISSING ELEMENTS THAT MUST APPEAR VERBATIM IN HTML:\n"
        )
        for elem in missing:
            enforcement_prompt += f"  - \"{elem}\"\n"
        enforcement_prompt += (
            f"\nFIX DIRECTIVE: {fix_dir}\n"
            f"You MUST include ALL the above text EXACTLY in your HTML output. "
            f"Do NOT summarize, rewrite, or omit any of them."
        )
        try:
            fix_render = await call_llm_json(RENDER_PROMPT, enforcement_prompt)
            if isinstance(fix_render, dict):
                fixed_html = fix_render.get("html", "")
                fixed_css = fix_render.get("css", "")
                # Verify the fix actually worked
                still_missing = []
                for elem in missing:
                    if isinstance(elem, str) and elem.strip() not in fixed_html:
                        still_missing.append(elem)
                if not still_missing:
                    html_content = fixed_html
                    css_content = fixed_css
                    logger.info("Slide %d: INTEGRITY render fix applied — all elements now present", slide_index + 1)
                else:
                    logger.warning(
                        "Slide %d: INTEGRITY render fix incomplete — still missing: %s. Using original render.",
                        slide_index + 1, still_missing,
                    )
        except Exception as fix_err:
            logger.warning("Slide %d: INTEGRITY render fix failed: %s", slide_index + 1, fix_err)

    custom_style = f"<style>{css_content}</style>" if css_content else ""

    final_html = _HTML_WRAPPER.format(
        slides_css=_load_slides_css(),
        theme=_esc(theme_dict.get('background', 'dark')),
        custom_style=custom_style,
        inner_html=html_content
    )
    
    design_spec = {
        "slide_index": slide_index,
        "theme": theme_dict.get('background', 'dark'),
        "layout": visual_plan.get("layout", "center_focus"),
        "components": {
            "type": preprocessing_result.get("intent", "content"),
            "title": preprocessing_result.get("title", ""),
            "primary": preprocessing_result.get("primary_element", ""),
            "supporting": preprocessing_result.get("supporting_elements", [])
        },
        "visual_plan": visual_plan,
    }
    
    return design_spec, final_html, continuity_context

async def run_dynamic_composition_engine(slides: list, state_theme: str, topic: str = "") -> tuple[list, list]:
    """
    Takes all slides and dynamically composes them using LLM design thinking.
    Returns: (designs, html_slides)
    """
    if not slides:
        return [], []
        
    logger.info(f"[dynamic_composition] Generating strict theme consistency data for {state_theme}...")
    try:
        theme_dict = await call_llm_json(THEME_GENERATION_PROMPT, f"Desired theme name or tone: {state_theme}")
    except Exception as e:
        logger.error(f"[dynamic_composition] Theme generation failed: {e}")
        theme_dict = {
            "background": "dark",
            "primary_color": "white",
            "font_scale": "massive headers, tiny constraints",
            "spacing_scale": "cozy"
        }
    
    logger.info(f"[dynamic_composition] Generating custom designs for {len(slides)} slides with theme={theme_dict.get('primary_color')}...")
    
    designs = []
    html_slides = []
    continuity_context = {"global_keywords": [], "entities": []}
    layout_history: list[str] = []  # tracks layouts for diversity enforcement
    total_slides = len(slides)
    
    # Use explicit topic if provided, else derive from first slide content
    inferred_topic = topic
    if not inferred_topic:
        first_content = slides[0].get("content", {}) if slides else {}
        if isinstance(first_content, dict):
            inferred_topic = first_content.get("title", "") or first_content.get("punchline", "")
    
    for idx, slide_data in enumerate(slides):
        design, slide_html, continuity_context = await generate_slide_html(
            slide_data, idx, total_slides, theme_dict, continuity_context, layout_history,
            topic=inferred_topic,
        )
        designs.append(design)
        html_slides.append(slide_html)
    
    # Log layout diversity summary
    layout_seq = [d.get("layout", "?") for d in designs]
    logger.info("[dynamic_composition] Layout sequence: %s", " → ".join(layout_seq))
    
    return designs, html_slides
