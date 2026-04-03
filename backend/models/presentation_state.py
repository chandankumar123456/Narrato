from pydantic import BaseModel, field_validator
from typing import Optional

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
    image_preference: bool = True
    visual_style: str = "modern"
    theme: str = "modern"

    # Runtime (filled during pipeline)
    story: Optional[dict] = None
    slide_plan: Optional[list[dict]] = None
    structured_slides: Optional[list[dict]] = None
    speaker_notes: Optional[list[dict]] = None
    image_queries: Optional[list[str]] = None
    output_path: Optional[str] = None
    design_theme: Optional[str] = None
    metadata: Optional[dict] = None

    # Strict mode fields
    user_schema: Optional[dict] = None
    generation_mode: Optional[str] = None  # "strict" | "default" | None

    @field_validator("slide_count")
    @classmethod
    def clamp_slide_count(cls, v):
        return max(5, min(v, 30))