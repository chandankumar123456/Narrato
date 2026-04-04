"""
Pipeline event system for real-time streaming.

Defines structured event types emitted by the orchestrator and stored
in the job store so the SSE endpoint can stream them to the frontend.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Optional


class EventType(str, Enum):
    STAGE_UPDATE = "STAGE_UPDATE"
    SLIDE_GENERATED = "SLIDE_GENERATED"
    SLIDE_DESIGNED = "SLIDE_DESIGNED"
    SLIDE_RENDERED = "SLIDE_RENDERED"
    JOB_COMPLETED = "JOB_COMPLETED"
    JOB_FAILED = "JOB_FAILED"


@dataclass
class PipelineEvent:
    job_id: str
    type: str
    stage: str
    progress: int
    label: str = ""
    slide_id: Optional[int] = None
    total_slides: Optional[int] = None
    data: Optional[dict] = None
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        # Strip None values for compact JSON
        return {k: v for k, v in d.items() if v is not None}
