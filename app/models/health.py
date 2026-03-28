# models/health.py

from __future__ import annotations
from typing import List, Optional
from pydantic import BaseModel, Field


class HealthData(BaseModel):
    """Health metrics fetched from Apple HealthKit or similar sources."""

    sleep_hours: float = Field(default=0.0, ge=0.0, le=24.0)
    deep_sleep_hours: float = Field(default=0.0, ge=0.0, le=24.0)
    rem_sleep_hours: float = Field(default=0.0, ge=0.0, le=24.0)
    wake_up_count: int = Field(default=0, ge=0)

    steps_today: int = Field(default=0, ge=0)
    active_minutes: int = Field(default=0, ge=0)
    sedentary_period: int = Field(default=0, ge=0, description="Longest sedentary period in minutes.")

    hrv: Optional[float] = Field(default=None, description="Heart rate variability (ms).")
    resting_heart_rate: Optional[int] = Field(default=None, description="Resting heart rate (bpm).")

    mood: str = Field(default="neutral")
    mood_score: int = Field(default=50, ge=0, le=100)

    stress_marker: bool = False
    hydration_level: str = Field(default="normal", pattern="^(low|normal|high)$")

    # Derived / enriched fields — set during ingestion
    health_alerts: List[str] = Field(default_factory=list)