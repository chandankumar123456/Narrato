"""Phase 5: Intelligence Report Generator.

Produces a structured evaluation README documenting the agent's behavior
during content generation.  This is NOT for end-users — it is for
evaluating the quality and reasoning of the multi-stage pipeline.
"""

from __future__ import annotations

import json
import logging

from models.presentation_state import PresentationState
from services.llm_client import call_llm

logger = logging.getLogger(__name__)


async def generate_intelligence_report(
    state: PresentationState,
) -> PresentationState:
    """Generate a Phase 1 Intelligence Report evaluating pipeline behavior.

    Attaches the Markdown report to ``state.intelligence_report``.
    """
    if not state.structured_slides:
        logger.warning("[intelligence-report] No structured slides — skipping report")
        return state

    slides_summary = json.dumps(
        [
            {
                "slide_id": s["slide_id"],
                "type": s["type"],
                "content": s.get("content", {}),
            }
            for s in state.structured_slides
        ],
        indent=2,
    )

    slide_plan_summary = ""
    if state.slide_plan:
        slide_plan_summary = json.dumps(
            [
                {
                    "slide_id": s["slide_id"],
                    "section": s["section"],
                    "purpose": s["purpose"],
                    "type": s["type"],
                }
                for s in state.slide_plan
            ],
            indent=2,
        )

    system_prompt = """You are an AI evaluation analyst. Your task is to produce a structured
intelligence report evaluating how an AI content generation system performed.

This report is for INTERNAL EVALUATION — not for end-users.

Write the report in Markdown format following the EXACT structure provided.
Be specific, cite actual slide content, and provide honest assessment."""

    user_prompt = f"""Generate an intelligence report for the following AI-generated presentation.

TOPIC: {state.topic}
PRESENTATION TYPE: {state.presentation_type}
AUDIENCE: {state.audience or "general"}
TONE: {state.tone}

SLIDE PLAN:
{slide_plan_summary}

GENERATED SLIDES:
{slides_summary}

Write the report using this EXACT structure:

# Narrato Phase 1 Intelligence Report

## 1. Input Understanding
- What was the task?
- What type of slide was generated?

## 2. Slide Intent Handling
- What was the intent for each slide?
- How was intent strictly followed?

## 3. Content Strategy
- How did the system ensure:
  - specificity (topic-specific content)
  - mechanisms (how things work)
  - non-generic content (not reusable across industries)

## 4. Repetition Avoidance
- How was overlap between slides prevented?
- Cite specific examples of unique content per slide.

## 5. Validation Decisions
- What checks were applied?
- What would have caused rejection?

## 6. Critic Evaluation
- Why would an investor accept each slide?
- What makes the content convincing?

## 7. Improvements Made
- What weaknesses were corrected internally?
- How did iterative refinement improve quality?

## 8. Final Quality Justification
- Why this output is:
  - non-generic
  - non-repetitive
  - structured

## 9. Limitations
- Where could the slides still be improved?
- What information gaps remain?

Be specific and reference actual slide content in your analysis."""

    try:
        report = await call_llm(system_prompt, user_prompt)
    except Exception as exc:
        logger.exception("[intelligence-report] Failed to generate report: %s", exc)
        report = _fallback_report(state)

    return state.model_copy(update={"intelligence_report": report})


def _fallback_report(state: PresentationState) -> str:
    """Minimal fallback report when LLM generation fails."""
    slide_count = len(state.structured_slides or [])
    return f"""# Narrato Phase 1 Intelligence Report

## 1. Input Understanding
- Task: Generate a {state.presentation_type} presentation on "{state.topic}"
- Slides generated: {slide_count}

## 2. Slide Intent Handling
- Slide intents were mapped from the slide plan sections and purposes.

## 3. Content Strategy
- Content was generated using mechanism-driven prompts.

## 4. Repetition Avoidance
- Previous slide content was provided as context to avoid duplication.

## 5. Validation Decisions
- Repetition, generic, and depth checks were applied per slide.

## 6. Critic Evaluation
- Investor-mode evaluation was applied to each slide.

## 7. Improvements Made
- Content was regenerated when validation or critic checks failed.

## 8. Final Quality Justification
- Multi-stage pipeline enforced specificity and non-repetition.

## 9. Limitations
- Report generated using fallback due to LLM failure.
"""
