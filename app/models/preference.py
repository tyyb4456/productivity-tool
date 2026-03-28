# models/preference.py

from typing import TypedDict, Dict


class UserPreferencesDict(TypedDict):
    preferred_work_hours: Dict[str, str]  # {"start": "09:00", "end": "17:00"}
    preferred_deep_work_duration: int  # minutes
    preferred_break_interval: int  # minutes
    stress_patterns: Dict[str, str]  # e.g., {"meetings": "high_stress", "emails": "low_stress"}
    focus_mode_enabled: bool  # True if focus mode is enabled
    focus_mode_start_time: str  # ISO datetime string   
    focus_mode_end_time: str  # ISO datetime string
    preferred_notification_times: Dict[str, str]  # e.g., {"morning": "08:00", "evening": "18:00"}
    preferred_hydration_reminders: bool  # True if hydration reminders are enabled
    preferred_sleep_schedule: Dict[str, str]  # e.g., {"bedtime": "22:00", "wake_time": "06:00"}
    preferred_mood_tracking: bool  # True if mood tracking is enabled
    preferred_health_data_sync: bool  # True if health data sync is enabled
    preferred_assessment_frequency: str  # e.g., "daily", "weekly"
    preferred_assessment_time: str  # ISO datetime string for preferred assessment time
    preferred_alerts: Dict[str, bool]  # e.g., {"stress": True, "health": False}

def create_default_user_preferences() -> UserPreferencesDict:
    return UserPreferencesDict(
        preferred_work_hours={"start": "09:00", "end": "17:00"},
        preferred_deep_work_duration=90,
        preferred_break_interval=60,
        stress_patterns={},
        focus_mode_enabled=False,
        focus_mode_start_time="",
        focus_mode_end_time="",
        preferred_notification_times={"morning": "08:00", "evening": "18:00"},
        preferred_hydration_reminders=True,
        preferred_sleep_schedule={"bedtime": "22:00", "wake_time": "06:00"},
        preferred_mood_tracking=True,
        preferred_health_data_sync=True,
        preferred_assessment_frequency="weekly",
        preferred_assessment_time="",
        preferred_alerts={"stress": True, "health": True}
    )