from pptx import Presentation # type: ignore
from pptx.util import Inches, Pt, Emu # type: ignore
from pptx.dml.color import RGBColor # type: ignore
from pptx.enum.text import PP_ALIGN # type: ignore
import uuid, os
from config import settings
from ppt.themes.modern import THEMES, ThemeConfig

SLIDE_W = Inches(13.33)  # Widescreen 16:9
SLIDE_H = Inches(7.5)

def hex_to_rgb(hex_str: str) -> RGBColor:
    h = hex_str.lstrip("#")
    return RGBColor(int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))

def add_text_box(slide, text, left, top, width, height, font_name, font_size, bold=False, color="000000", align=PP_ALIGN.LEFT, wrap=True):
    txBox = slide.shapes.add_textbox(left, top, width, height)
    tf = txBox.text_frame
    tf.word_wrap = wrap
    p = tf.paragraphs[0]
    p.alignment = align
    run = p.add_run()
    run.text = text
    run.font.name = font_name
    run.font.size = Pt(font_size)
    run.font.bold = bold
    run.font.color.rgb = hex_to_rgb(color)
    return txBox

def set_background(slide, color_hex: str):
    from pptx.oxml.ns import qn
    from lxml import etree
    fill = slide.background.fill
    fill.solid()
    fill.fore_color.rgb = hex_to_rgb(color_hex)

def generate_ppt(state) -> str:
    theme: ThemeConfig = THEMES.get(state.theme, THEMES["modern"])
    prs = Presentation()
    prs.slide_width = SLIDE_W
    prs.slide_height = SLIDE_H

    blank_layout = prs.slide_layouts[6]  # completely blank

    for slide_data in state.structured_slides:
        slide = prs.slides.add_slide(blank_layout)
        set_background(slide, theme.background)
        _render_slide(slide, slide_data, theme)

    os.makedirs(settings.output_dir, exist_ok=True)
    path = f"{settings.output_dir}/{uuid.uuid4().hex}.pptx"
    prs.save(path)
    return path

def _render_slide(slide, slide_data: dict, theme: ThemeConfig):
    from ppt.layouts import title_slide, feature_slide, section_header, \
                             stats_slide, conclusion_slide, problem_slide, cta_slide

    dispatch = {
        "title_slide": title_slide.render,
        "section_header": section_header.render,
        "feature_slide": feature_slide.render,
        "stats_slide": stats_slide.render,
        "conclusion_slide": conclusion_slide.render,
        "problem_slide": problem_slide.render,
        "cta_slide": cta_slide.render,
    }

    renderer = dispatch.get(slide_data["type"])
    if renderer:
        renderer(slide, slide_data["content"], theme, slide_data.get("image_path"))
    else:
        # Generic fallback layout
        add_text_box(slide, slide_data["content"].get("title", ""), Inches(0.5), Inches(0.3), Inches(12), Inches(1), theme.font_heading, theme.heading_size, bold=True, color=theme.primary)