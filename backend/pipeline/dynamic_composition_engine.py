import logging
import asyncio
from pathlib import Path
import html
from services.llm_client import call_llm_json

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

PREPROCESS_PROMPT = """You are a Content Reduction and Hierarchy Engine. Your goal is to map messy, dense slide content into highly controlled, minimal textual elements.
MANDATORY RULES:
1. CONTENT REDUCTION: Compress long sentences. Convert paragraphs to short 2-5 word phrases. Remove duplicate phrases. Extract stats/numbers.
2. DETERMINE VISUAL HIERARCHY: You MUST define ONE primary element. It should be the most important point or a key statistic.
3. LIMIT SECONDARY ELEMENTS: Keep secondary/tertiary points brief.

Output a JSON object with:
- "intent": the overall goal or layout hint (e.g., 'hero', 'stat', 'split', 'blocks').
- "primary_element": a short string representation of the dominant focal point.
- "secondary_elements": an array of short strings supporting the primary point.
- "tertiary_elements": an array of short strings for extra context (can be empty).

IMPORTANT: Only return JSON. No markdown backticks or preamble.
"""

RENDER_PROMPT = """You are a master presentation designer. Your task is to output the perfect, custom HTML and CSS for a single presentation slide, using the highly controlled content provided.
Do NOT use rigid templates or structured gridding unless mathematically necessary.

DESIGN RULES (MANDATORY):
1. ONE DOMINANT ELEMENT: Use the provided `primary_element`. You MUST style it to be 2x-4x larger or more prominent than secondary elements.
2. WHITESPACE ENFORCEMENT: Maintain 40-60% empty space across the layout. Do not make the slide dense.
3. TYPOGRAPHY DOMINANCE: Primary element font size must be massive. Secondary text small. Never allow all text to be similar sizes.
4. SYMMETRY BREAKING: Avoid equal-width cards or identical layouts. Use uneven spacing, offset alignments, or asymmetrical flow. 1 dominant + 2 supporting elements is best.
5. DESIGN CONSISTENCY: Enforce spacing and font families consistently through your CSS. Use relative sizing (rem, em) or percentages (%), not random fixed pixel sets.

Context constraints: No images. Only vanilla CSS/HTML. 

Return a JSON object with:
- "html": The body content of the layout. (Do not wrap in <html> or <body>).
- "css": Any custom CSS you want placed in a <style> block specific to this layout. Use classes.

IMPORTANT: Only return JSON. No markdown backticks or preamble.
"""

VALIDATE_PROMPT = """You are a Visual Design Validator. Analyze the generated HTML and CSS. You are verifying 4 strict visual design goals.

CRITERIA:
1. dominant_element: Does the HTML/CSS clearly contain ONE element styled 2x-4x larger than the rest?
2. text_reduced: Are all text elements brief? (No long blocks of text allowed).
3. asymmetrical_layout: Does the layout avoid perfect symmetry (e.g. no 3 equal cards, no perfectly centered text blocks if it feels standard)?
4. whitespace_present: Does the layout logically contain 40-60% breathing space given the CSS constraints?

Output a JSON object with:
- "dominant_element": boolean
- "text_reduced": boolean
- "asymmetrical_layout": boolean
- "whitespace_present": boolean
- "critique": If any boolean is false, write a strictly brief 1-2 sentence direction to fix it. If all true, return empty string.

IMPORTANT: Only return JSON. No markdown backticks or preamble.
"""

async def generate_slide_html(slide_data: dict, slide_index: int, theme: str) -> tuple[dict, str]:
    """Generates custom HTML and CSS for a single slide using a multi-step control layer."""
    content = slide_data.get("content", {})
    intent_str = slide_data.get("intent", "")
    base_prompt = f"Intent: {intent_str}\nContent:\n{content}"
    
    # Phase 1: Preprocessing & Content Reduction
    try:
        preprocessing_result = await call_llm_json(PREPROCESS_PROMPT, base_prompt)
    except Exception as e:
        logger.error(f"Slide {slide_index + 1}: Preprocessing failed: {e}")
        preprocessing_result = {"primary_element": str(content)[:50], "secondary_elements": []}

    # Phase 2 & 3: Generation & Validation Loop
    html_content = ""
    css_content = ""
    max_retries = 3
    
    render_input = f"Slide {slide_index + 1}:\nDistilled Content:\n{preprocessing_result}\nTheme: {theme}"
    validation_feedback = ""
    
    for attempt in range(max_retries):
        current_render_prompt = render_input
        if validation_feedback:
            current_render_prompt += f"\n\nPREVIOUS ATTEMPT FAILED. FEEDBACK TO FIX:\n{validation_feedback}"
            
        try:
            render_result = await call_llm_json(RENDER_PROMPT, current_render_prompt)
            if not isinstance(render_result, dict):
                logger.error(f"Slide {slide_index + 1}: Render output not JSON dict. Using fallback.")
                html_content = "<div class='error'>Failed rendering layout constraints.</div>"
                break
            html_content = render_result.get("html", "")
            css_content = render_result.get("css", "")
        except Exception as e:
            logger.error(f"Slide {slide_index + 1}: RENDER attempt {attempt + 1} failed: {e}")
            html_content = f"<div class='error'>Failed to generate visual slide layout.</div>"
            css_content = ""
            break # LLM JSON decode failure, do not retry blindly
            
        # Validate
        validation_input = f"Generated HTML:\n{html_content}\n\nGenerated CSS:\n{css_content}"
        try:
            validation_result = await call_llm_json(VALIDATE_PROMPT, validation_input)
            if not isinstance(validation_result, dict):
                break # Default to assuming we at least tried, move forward
            
            # Check constraints
            dom = validation_result.get("dominant_element", False)
            txt = validation_result.get("text_reduced", False)
            asym = validation_result.get("asymmetrical_layout", False)
            ws = validation_result.get("whitespace_present", False)
            
            if dom and txt and asym and ws:
                logger.info(f"Slide {slide_index + 1}: Layout passed validation on attempt {attempt + 1}")
                break
            else:
                validation_feedback = validation_result.get("critique", "Layout failed structural checks. Make the primary element massive, ensure asymmetry, and reduce text length.")
                logger.info(f"Slide {slide_index + 1}: Validation failed on attempt {attempt + 1}. Feedback: {validation_feedback}")
        except Exception as e:
            logger.warning(f"Slide {slide_index + 1}: Validation call failed: {e}. Accepting current render.")
            break

    custom_style = f"<style>{css_content}</style>" if css_content else ""

    final_html = _HTML_WRAPPER.format(
        slides_css=_load_slides_css(),
        theme=_esc(theme),
        custom_style=custom_style,
        inner_html=html_content
    )
    
    design_spec = {
        "slide_index": slide_index,
        "theme": theme,
        "presentation": {"slide_number": slide_index + 1}
    }
    
    return design_spec, final_html

async def run_dynamic_composition_engine(slides: list, state_theme: str) -> tuple[list, list]:
    """
    Takes all slides and dynamically composes them using LLM design thinking.
    Returns: (designs, html_slides)
    """
    if not slides:
        return [], []
    
    logger.info(f"[dynamic_composition] Generating custom designs for {len(slides)} slides...")
    
    tasks = []
    for idx, slide_data in enumerate(slides):
        tasks.append(generate_slide_html(slide_data, idx, state_theme))
        
    results = await asyncio.gather(*tasks)
    
    designs = [res[0] for res in results]
    html_slides = [res[1] for res in results]
    
    return designs, html_slides
