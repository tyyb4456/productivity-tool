from typing import List, Optional

def analyze_sentiment(text: str) -> float:
    """Dummy sentiment scoring (-1 negative, +1 positive). Replace with actual model."""
    from textblob import TextBlob
    return TextBlob(text).sentiment.polarity


def detect_sentiment_trend(sentiments: List[float]) -> str:
    if len(sentiments) < 2:
        return "stable"
    delta = sentiments[-1] - sentiments[0]
    if delta > 0.1:
        return "rising"
    elif delta < -0.1:
        return "dropping"
    return "stable"

def analyze_stress_marker(health_data: dict) -> bool:
    """
    Simple heuristic for stress marker.
    """
    if health_data.get("hrv", 50) < 30 or health_data.get("resting_hr", 60) > 75:
        return True
    return False


def update_trend(trend_list, new_value, max_len=7):
    """
    Append a new value to a trend list, keeping the list length ≤ max_len.
    Skips appending if new_value is None.
    """
    if new_value is None:
        return
    trend_list.append(new_value)
    if len(trend_list) > max_len:
        trend_list.pop(0)


def get_trend(data: List[float], label: str) -> str:
    return ", ".join([f"{label} Day-{i}: {v}" for i, v in enumerate(reversed(data), 1)]) or "No data"


from statistics import mean
from datetime import datetime, timedelta
from state import AgentStateDict

def detect_stress_signatures(state: AgentStateDict) -> list[str]:
    """
    Detects stress-related patterns in the user's trend data.
    Returns a list of detected stress signatures.
    """
    trend = state['trend_data']
    detected = []

    # 🔥 Sustained high cognitive load
    if len(trend["cognitive_load"]) >= 3:
        if mean(trend["cognitive_load"][-3:]) > 0.7:
            detected.append("high_cognitive_load_trend")

    # 💤 Declining sleep quality
    if len(trend["deep_sleep_hours"]) >= 3 and mean(trend["deep_sleep_hours"][-3:]) < 1.0:
        detected.append("low_deep_sleep_trend")
    if len(trend["rem_sleep_hours"]) >= 3 and mean(trend["rem_sleep_hours"][-3:]) < 1.0:
        detected.append("low_rem_sleep_trend")

    # 🚶‍♂️ Reduced physical activity
    if len(trend["steps"]) >= 3:
        avg_steps = mean(trend["steps"][-3:])
        overall_baseline = mean(trend["steps"]) if trend["steps"] else 8000
        if avg_steps < overall_baseline * 0.5:
            detected.append("reduced_physical_activity")

    # 💬 Late-night activity (last 3 days)
    if len(trend["late_night_activity_count"]) >= 3:
        if mean(trend["late_night_activity_count"][-3:]) > 2:  # more than 2 late night events avg
            detected.append("frequent_late_night_activity")

    # 🩺 Elevated Resting HR
    if len(trend["resting_heart_rate"]) >= 3:
        if mean(trend["resting_heart_rate"][-3:]) > 75:  # threshold can be tuned
            detected.append("elevated_resting_heart_rate")

    # 🫀 Low HRV (Heart Rate Variability)
    if len(trend["hrv"]) >= 3 and mean(trend["hrv"][-3:]) < 40:  # threshold can be tuned
        detected.append("low_hrv_trend")

    return detected

from datetime import datetime, timedelta

def calculate_productive_hours_ratio(state: AgentStateDict) -> float:
    """
    Estimate ratio of productive hours to total working hours today.
    Returns a float between 0.0 (no productive time) and 1.0 (fully productive).
    """
    now = datetime.utcnow()
    start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_day = now.replace(hour=23, minute=59, second=59, microsecond=999999)

    # Get preferred work hours (defaults to 9–17)
    work_start = datetime.strptime(state['user_preferences']["preferred_work_hours"]["start"], "%H:%M").time()
    work_end = datetime.strptime(state['user_preferences']["preferred_work_hours"]["end"], "%H:%M").time()
    total_work_seconds = ((datetime.combine(now.date(), work_end) -
                          datetime.combine(now.date(), work_start)).total_seconds())

    # Estimate productive time from calendar + tasks
    productive_seconds = 0

    # Calendar events marked as meetings
    for event in state['calendar_events']:
        if event["is_meeting"] and event["start_time"] and event["end_time"]:
            start = datetime.fromisoformat(event["start_time"])
            end = datetime.fromisoformat(event["end_time"])
            if start.date() == now.date():  # only today
                productive_seconds += (end - start).total_seconds()

    # Tasks with estimated_duration_minutes
    for task in state['tasks']:
        if task["status"] == "completed" and task.get("estimated_duration_minutes"):
            productive_seconds += task["estimated_duration_minutes"] * 60

    # Avoid division by zero
    if total_work_seconds == 0:
        return 0.0

    ratio = productive_seconds / total_work_seconds
    return round(min(ratio, 1.0), 2)  # Cap at 1.0

