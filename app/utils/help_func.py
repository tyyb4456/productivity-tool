# utils/help_func.py

from __future__ import annotations

from datetime import datetime, timezone
from statistics import mean
from typing import TYPE_CHECKING, List, Optional

if TYPE_CHECKING:
    from state import AgentState


# ---------------------------------------------------------------------------
# Sentiment helpers
# ---------------------------------------------------------------------------

def analyze_sentiment(text: str) -> float:
    """Return polarity score in [-1, +1].  Requires textblob."""
    try:
        from textblob import TextBlob
        return TextBlob(text).sentiment.polarity
    except ImportError:
        return 0.0


def detect_sentiment_trend(sentiments: List[float]) -> str:
    if len(sentiments) < 2:
        return "stable"
    delta = sentiments[-1] - sentiments[0]
    if delta > 0.1:
        return "rising"
    if delta < -0.1:
        return "dropping"
    return "stable"


def analyze_stress_marker(health_data: dict) -> bool:
    return (
        health_data.get("hrv", 50) < 30
        or health_data.get("resting_hr", 60) > 75
    )


# ---------------------------------------------------------------------------
# Trend helpers
# ---------------------------------------------------------------------------

def update_trend(trend_list: list, new_value, max_len: int = 7) -> None:
    """Append value in-place, capping list at max_len entries."""
    if new_value is None:
        return
    trend_list.append(new_value)
    if len(trend_list) > max_len:
        del trend_list[:-max_len]


def get_trend(data: List[float], label: str) -> str:
    return (
        ", ".join(f"{label} Day-{i}: {v}" for i, v in enumerate(reversed(data), 1))
        or "No data"
    )


# ---------------------------------------------------------------------------
# Stress signature detection
# ---------------------------------------------------------------------------

def detect_stress_signatures(state: "AgentState") -> List[str]:
    """
    Detect stress-related patterns from trend_data.
    Returns a list of string tags.
    """
    trend    = state.trend_data
    detected: List[str] = []

    if len(trend.cognitive_load) >= 3 and mean(trend.cognitive_load[-3:]) > 0.7:
        detected.append("high_cognitive_load_trend")

    if len(trend.deep_sleep_hours) >= 3 and mean(trend.deep_sleep_hours[-3:]) < 1.0:
        detected.append("low_deep_sleep_trend")

    if len(trend.rem_sleep_hours) >= 3 and mean(trend.rem_sleep_hours[-3:]) < 1.0:
        detected.append("low_rem_sleep_trend")

    if len(trend.steps) >= 4:
        # Need at least 4 points so the recent 3 and the baseline are distinct
        avg_steps = mean(trend.steps[-3:])
        baseline  = mean(trend.steps[:-3]) if len(trend.steps) > 3 else 8000
        if avg_steps < baseline * 0.6:
            detected.append("reduced_physical_activity")

    if (
        len(trend.late_night_activity_count) >= 3
        and mean(trend.late_night_activity_count[-3:]) > 2
    ):
        detected.append("frequent_late_night_activity")

    if len(trend.resting_heart_rate) >= 3 and mean(trend.resting_heart_rate[-3:]) > 75:
        detected.append("elevated_resting_heart_rate")

    if len(trend.hrv) >= 3 and mean(trend.hrv[-3:]) < 40:
        detected.append("low_hrv_trend")

    return detected


# ---------------------------------------------------------------------------
# Productive hours ratio
# ---------------------------------------------------------------------------

def calculate_productive_hours_ratio(state: "AgentState") -> float:
    """
    Ratio of productive time to total work hours today.
    Returns a float in [0.0, 1.0].
    """
    now = datetime.now(timezone.utc)                  # ← fixed: was utcnow()

    work_start_str = state.user_preferences.preferred_work_hours.get("start", "09:00")
    work_end_str   = state.user_preferences.preferred_work_hours.get("end",   "17:00")

    work_start = datetime.strptime(work_start_str, "%H:%M").replace(
        year=now.year, month=now.month, day=now.day, tzinfo=timezone.utc
    )
    work_end = datetime.strptime(work_end_str, "%H:%M").replace(
        year=now.year, month=now.month, day=now.day, tzinfo=timezone.utc
    )

    total_work_seconds = (work_end - work_start).total_seconds()
    if total_work_seconds <= 0:
        return 0.0

    productive_seconds = 0.0

    for event in state.calendar_events:
        if event.is_meeting and event.start_time and event.end_time:
            try:
                start = datetime.fromisoformat(event.start_time)
                end   = datetime.fromisoformat(event.end_time)
                if start.date() == now.date():
                    productive_seconds += (end - start).total_seconds()
            except ValueError:
                pass

    for task in state.tasks:
        if task.status == "completed" and task.estimated_duration_minutes:
            productive_seconds += task.estimated_duration_minutes * 60

    return round(min(productive_seconds / total_work_seconds, 1.0), 2)