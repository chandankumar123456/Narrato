from pydantic import BaseModel, field_validator, model_validator
from typing import Optional

# Slide count boundaries (default mode only; strict mode uses exact counts)
MIN_SLIDE_COUNT = 5
MAX_SLIDE_COUNT = 30

# Shared word-limit constant used by structurer, validator, and renderer
MAX_WORDS_PER_FIELD = 12
MAX_WORDS_NAME = 6

class PresentationState(BaseModel):
    # Identity
    topic: str
    presentation_type: str = "general"
    language: str = "en"

    # Structure
    slide_count: int = 10
    min_slides: int = 5
    max_slides: int = 30
    sections: Optional[list[str]] = None

    # Tone
    tone: str = "professional"
    audience: Optional[str] = None

    # Content
    examples_count: int = 2
    include_stats: bool = True

    # Visuals
    visual_style: str = "modern"
    theme: str = "modern"

    # Runtime (filled during pipeline)
    story: Optional[dict] = None
    slide_plan: Optional[list[dict]] = None
    structured_slides: Optional[list[dict]] = None
    speaker_notes: Optional[list[dict]] = None
    output_path: Optional[str] = None
    design_theme: Optional[str] = None
    metadata: Optional[dict] = None
    narrative_arc: Optional[list[dict]] = None

    # Strict mode fields
    user_schema: Optional[dict] = None
    generation_mode: Optional[str] = None  # "strict" | "default" | None

    # Intelligence report (Phase 5 evaluation output)
    intelligence_report: Optional[str] = None

    # Visual rendering engine output
    visual_render_output: Optional[dict] = None

    @field_validator("slide_count", mode="before")
    @classmethod
    def clamp_slide_count(cls, v, info):
        return max(MIN_SLIDE_COUNT, min(v, MAX_SLIDE_COUNT))

    @model_validator(mode="after")
    def enforce_strict_slide_count(self):
        """In strict mode, override the clamped slide_count with the exact
        schema-derived value.  Strict mode requires EXACT counts — no guards."""
        if self.generation_mode == "strict" and self.user_schema:
            n = self.user_schema.get("examples_required", 0)
            exact = 2 + n + 1  # title + definition + N examples + summary
            if self.slide_count != exact:
                object.__setattr__(self, "slide_count", exact)
        return self