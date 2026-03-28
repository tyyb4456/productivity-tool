# models/cognitive.py

from typing import TypedDict, Optional


class CognitiveStateDict(TypedDict):
    cognitive_load: str  # low | normal | high | overloaded
    cognitive_load_score: float  # Always present, default 0.0
    focus_level: str  # low | normal | high
    stress_level: str  # low | normal | high | burnout_risk
    stress_level_score: float  # Always present, default 0.0
    burnout_risk: bool
    energy_level: str  # low | normal | high
    energy_level_score: float  # Always present, default 0.0
    wellbeing_suggestion: str
    productivity_suggestion: str
    reasoning: str  # Explanation of state
    detected_stress_signatures: str  # Comma-separated list
    in_focus_mode: bool
    focus_mode_start_time: Optional[str]  # ISO datetime string
    focus_mode_end_time: Optional[str]  # ISO datetime string


def create_default_cognitive_state() -> CognitiveStateDict:
    return CognitiveStateDict(
        cognitive_load="normal",
        cognitive_load_score=0.0,
        focus_level="normal",
        stress_level="normal",
        stress_level_score=0.0,
        burnout_risk=False,
        energy_level="normal",
        energy_level_score=0.0,
        wellbeing_suggestion="Take a deep breath.",
        productivity_suggestion="Review your top 3 tasks.",
        reasoning="Initial state",
        detected_stress_signatures="",
        in_focus_mode=False,
    
        focus_mode_start_time=None,
        focus_mode_end_time=None
    )