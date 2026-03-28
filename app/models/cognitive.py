# models/cognitive.py

from __future__ import annotations
from typing import List, Optional
from pydantic import BaseModel, Field


class CognitiveState(BaseModel):
    """Real-time assessment of user's mental and physical state."""

    cognitive_load: str = Field(
        default="normal",
        pattern="^(low|normal|high|overloaded)$",
        description="Overall mental workload.",
    )
    cognitive_load_score: float = Field(default=0.0, ge=0.0, le=10.0)

    focus_level: str = Field(
        default="normal",
        pattern="^(low|normal|high)$",
    )

    stress_level: str = Field(
        default="normal",
        pattern="^(low|normal|high|burnout_risk)$",
    )
    stress_level_score: float = Field(default=0.0, ge=0.0, le=10.0)

    burnout_risk: bool = False

    # In models.py — CognitiveState
    energy_level: str = Field(
        default="moderate",      
        pattern=r"^(low|moderate|high)$"
    )
    energy_level_score: float = Field(default=0.0, ge=0.0, le=10.0)

    wellbeing_suggestion: str = "Take a deep breath."
    productivity_suggestion: str = "Review your top 3 tasks."
    reasoning: str = "Initial state — no assessment run yet."
    detected_stress_signatures: List[str] = Field(default_factory=list)

    # Focus mode tracking
    in_focus_mode: bool = False
    focus_mode_start_time: Optional[str] = None
    focus_mode_end_time: Optional[str] = None

    # Muted channels set by InformationFlowFilter
    muted_channels: List[str] = Field(default_factory=list)