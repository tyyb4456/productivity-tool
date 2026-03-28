# models/supporting.py
#
# All smaller models in one file to avoid import sprawl.
# Split into individual files later if any model grows large.

from __future__ import annotations
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from models.cognitive import CognitiveState


# ---------------------------------------------------------------------------
# Note
# ---------------------------------------------------------------------------

class Note(BaseModel):
    id: str
    title: str
    content: Optional[str] = None
    created_at: str                                   # ISO 8601
    last_modified: str                                # ISO 8601
    tags: List[str] = Field(default_factory=list)
    source: str = "unknown"
    is_archived: bool = False
    is_pinned: bool = False
    priority: str = Field(default="normal", pattern="^(low|normal|high)$")
    attachments: List[str] = Field(default_factory=list)
    related_events: List[str] = Field(default_factory=list)
    related_tasks: List[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Communication
# ---------------------------------------------------------------------------

class CommunicationInsight(BaseModel):
    message_volume: int = 0
    avg_message_length: int = 0
    late_night_activity: bool = False
    sentiment_score: float = Field(default=0.0, ge=-1.0, le=1.0)
    sentiment_trend: str = Field(
        default="stable",
        pattern="^(rising|stable|dropping)$",
    )
    source: str = "unknown"


# ---------------------------------------------------------------------------
# Trend data  (rolling 7-day window for every metric)
# ---------------------------------------------------------------------------

class TrendData(BaseModel):
    cognitive_load: List[float] = Field(default_factory=list)
    focus_level: List[str] = Field(default_factory=list)
    energy_level: List[float] = Field(default_factory=list)

    sleep_hours: List[float] = Field(default_factory=list)
    deep_sleep_hours: List[float] = Field(default_factory=list)
    rem_sleep_hours: List[float] = Field(default_factory=list)
    wake_up_counts: List[int] = Field(default_factory=list)

    steps: List[int] = Field(default_factory=list)
    active_minutes: List[int] = Field(default_factory=list)

    mood_entries: List[str] = Field(default_factory=list)
    sentiment_scores: List[str] = Field(default_factory=list)

    detected_stress_signatures: List[str] = Field(default_factory=list)
    burnout_risk: List[bool] = Field(default_factory=list)
    detected_stress_factors: List[str] = Field(default_factory=list)

    resting_heart_rate: List[int] = Field(default_factory=list)
    hrv: List[float] = Field(default_factory=list)
    hydration_level: List[str] = Field(default_factory=list)
    late_night_activity_count: List[int] = Field(default_factory=list)
    productive_hours_ratio: List[float] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# User preferences  (learned + explicit)
# ---------------------------------------------------------------------------

class UserPreferences(BaseModel):
    preferred_work_hours: Dict[str, str] = Field(
        default_factory=lambda: {"start": "09:00", "end": "17:00"}
    )
    preferred_deep_work_duration: int = Field(default=90, ge=15, le=240)   # minutes
    preferred_break_interval: int = Field(default=60, ge=10, le=120)       # minutes

    stress_patterns: Dict[str, str] = Field(default_factory=dict)
    focus_mode_enabled: bool = False
    focus_mode_start_time: str = ""
    focus_mode_end_time: str = ""

    preferred_notification_times: Dict[str, str] = Field(
        default_factory=lambda: {"morning": "08:00", "evening": "18:00"}
    )
    preferred_hydration_reminders: bool = True
    preferred_sleep_schedule: Dict[str, str] = Field(
        default_factory=lambda: {"bedtime": "22:00", "wake_time": "06:00"}
    )

    preferred_mood_tracking: bool = True
    preferred_health_data_sync: bool = True
    preferred_assessment_frequency: str = "weekly"
    preferred_assessment_time: str = ""
    preferred_alerts: Dict[str, bool] = Field(
        default_factory=lambda: {"stress": True, "health": True}
    )

    # Learned by FeedbackLoop / AdaptiveModelRefiner
    reminder_frequency: str = "every 60 mins"
    reminder_style: str = "neutral"
    task_prioritization: str = "urgency"
    notification_filtering: str = "balanced"


# ---------------------------------------------------------------------------
# Assessment snapshot  (persisted history)
# ---------------------------------------------------------------------------

class CognitiveAssessmentSnapshot(BaseModel):
    timestamp: str                                    # ISO 8601
    inputs: Dict[str, Any] = Field(default_factory=dict)
    assessment: CognitiveState = Field(default_factory=CognitiveState)