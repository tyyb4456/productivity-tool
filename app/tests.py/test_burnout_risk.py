# app/test_burnout_risk.py

from datetime import datetime, timezone, timedelta
from nodes.burnout_risk_detector_node import burnout_risk_detector
from state import AgentStateDict

# 🧪 Mock AgentStateDict with sample data
state: AgentStateDict = {
    "trend_data": {
        "cognitive_load": [0.8, 0.9, 0.85, 0.88, 0.9],
        "energy_level": [0.4, 0.5, 0.3, 0.35, 0.4],
        "sleep_hours": [5.0, 4.5, 5.2, 4.8, 5.0],
        "deep_sleep_hours": [0.8, 0.7, 0.6, 0.5, 0.8],
        "rem_sleep_hours": [0.9, 0.8, 1.0, 0.7, 0.8],
        "wake_up_counts": [3, 4, 5, 4, 3],
        "steps": [4000, 3500, 3000, 2800, 3200],
        "active_minutes": [20, 15, 10, 12, 18],
        "mood_entries": ["stressed", "overwhelmed", "neutral", "stressed", "sad"],
        "sentiment_scores": ["negative", "negative", "neutral", "negative", "neutral"],
        "detected_stress_signatures": ["high_cognitive_load_trend", "low_deep_sleep_trend"],
        "burnout_risk": [False, False, True, True, True],
        "detected_stress_factors": ["late_night_activity", "negative_mood_trend"]
    },
    "recent_communication_messages": [
        {
            "text": "Working late again...",
            "sentiment": "negative",
            "timestamp": (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
        },
        {
            "text": "Feeling exhausted.",
            "sentiment": "negative",
            "timestamp": (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        }
    ],
    "calendar_events": [],
    "tasks": [],
    "health_data": {
        "sleep_hours": 5.0,
        "deep_sleep_hours": 0.8,
        "rem_sleep_hours": 0.9,
        "wake_up_count": 4,
        "steps_today": 3500,
        "active_minutes": 15,
        "mood": "stressed",
        "mood_score": 2.0,
        "stress_marker": "high",
    },
    "cognitive_state": {
        "cognitive_load": "high",
        "cognitive_load_score": 8.5,
        "focus_level": "low",
        "stress_level": "high",
        "stress_level_score": 7.5,
        "burnout_risk": True,
        "energy_level": "low",
        "energy_level_score": 3.0,
        "wellbeing_suggestion": "Take a short walk",
        "productivity_suggestion": "Prioritize critical tasks only",
        "reasoning": "Sustained high cognitive load and poor sleep detected.",
        "detected_stress_signatures": ["high_cognitive_load_trend"]
    },
    "burnout_status": {},
    "assessment_history": [],
    "recent_activities": [],
    "schedule_adjustment_required": False,
    "wellbeing_reminder_required": False,
    "last_updated": None
}

# 🚀 Run the burnout risk detector
updated_state = burnout_risk_detector(state)

# 📦 Print the results
print("\n=== Burnout Risk Detector Result ===")
print("Burnout Risk:", updated_state["burnout_status"]["burnout_risk"])
print("Severity:", updated_state["burnout_status"]["severity"])
print("Reason:", updated_state["burnout_status"]["reason"])
print("Detected Stress Factors:", updated_state["burnout_status"]["detected_stress_factors"])
print("Recommended Action:", updated_state["burnout_status"]["recommended_action"])
print("\nRecent Activities:")
for activity in updated_state["recent_activities"]:
    print("•", activity)
print("\n====================================\n")
