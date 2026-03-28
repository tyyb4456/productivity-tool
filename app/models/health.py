# models/health.py

from typing import TypedDict, List



class HealthDataDict(TypedDict):
    sleep_hours: float  # Total sleep hours
    deep_sleep_hours: int  # Deep sleep hours
    rem_sleep_hours: int  # REM sleep hours
    wake_up_count: int  # Number of wake-ups during sleep
    steps_today: int  # Steps taken today
    active_minutes: int  # Active minutes today
    sedentary_period: str  # Longest sedentary period
    hrv: float  # Heart Rate Variability
    resting_heart_rate: int  # Resting heart rate
    mood: str  # e.g., happy, stressed, tired
    mood_score: int  # Mood score (0–100)
    stress_marker: bool  # True if stress marker detected
    hydration_level: str  # e.g., low, normal, high
    hydration_score: int  # Hydration score (0–100)
    last_health_check: str  # ISO datetime string of last health check
    health_suggestions: str  # Suggestions based on health data
    health_alerts: List[str]  # Alerts based on health data
    last_health_update: str  # ISO datetime string of last health update
    health_trends: List[str]  # Recent health trends
    last_health_assessment: str  # ISO datetime string of last health assessment
    health_assessment_score: int  # Score from health assessment (0–100)

def create_default_health_data() -> HealthDataDict:
    return HealthDataDict(
        sleep_hours=0.0,
        deep_sleep_hours=0,
        rem_sleep_hours=0,
        wake_up_count=0,
        steps_today=0,
        active_minutes=0,
        sedentary_period="unknown",
        hrv=0.0,
        resting_heart_rate=0,
        mood="neutral",
        mood_score=50,
        stress_marker=False,
        hydration_level="normal",
        hydration_score=50,
        last_health_check="",
        health_suggestions="",
        health_alerts=[],
        last_health_update="",
        health_trends=[],
        last_health_assessment="",
        health_assessment_score=50
    )
