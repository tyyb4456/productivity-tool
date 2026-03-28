# app/test_dynamic_reprioritizer.py

from nodes.dynamic_reprioritizer_node import dynamic_reprioritizer
from datetime import datetime, timezone
from pprint import pprint

# 🧪 Mock AgentStateDict
mock_state = {
    "cognitive_state": {
        "cognitive_load": "high",
        "cognitive_load_score": 8.0,
        "energy_level": "low",
        "energy_level_score": 3.0,
        "stress_level": "high",
        "stress_level_score": 7.5,
        "burnout_risk": True,
        "wellbeing_suggestion": "Take a 10-min break and drink water.",
        "productivity_suggestion": "Defer non-urgent tasks for today.",
        "reasoning": "Sustained high cognitive load and low energy detected.",
        "detected_stress_signatures": ["high_cognitive_load", "low_sleep_quality"]
    },
    "trend_data": {
        "cognitive_load": [6, 7, 8],
        "energy_level": [4, 3, 2],
        "sleep_hours": [6.5, 5.0, 5.5],
        "deep_sleep_hours": [1.2, 0.8, 1.0],
        "rem_sleep_hours": [1.1, 0.9, 1.0],
        "wake_up_counts": [2, 3, 4],
        "steps": [6000, 5000, 4000],
        "active_minutes": [40, 30, 25],
        "mood_entries": ["tired", "stressed", "overwhelmed"],
        "sentiment_scores": ["negative", "neutral", "negative"],
        "detected_stress_signatures": ["low_sleep_quality", "high_cognitive_load"],
        "burnout_risk": [True, True, True],
        "detected_stress_factors": ["low_sleep_quality", "late_night_activity"]
    },
    "burnout_status": {
        "burnout_risk": True,
        "severity": "high",
        "reason": "Sustained high cognitive load, low sleep quality, and reduced activity.",
        "detected_stress_factors": ["low_sleep_quality", "high_cognitive_load", "late_night_activity"],
        "recommended_action": "defer tasks"
    },
    "tasks": [
        {
            "id": "task-001",
            "title": "Prepare project report",
            "description": "Complete the draft for the Q2 report.",
            "due_date": "2025-07-15",
            "priority": "high",
            "status": "in_progress"
        },
        {
            "id": "task-002",
            "title": "Plan team meeting",
            "description": "Schedule next week's team sync.",
            "due_date": "2025-07-20",
            "priority": "medium",
            "status": "pending"
        },
        {
            "id": "task-003",
            "title": "Review codebase",
            "description": "Go through PR #42 and #43.",
            "due_date": "2025-07-18",
            "priority": "high",
            "status": "pending"
        }
    ],
    "recent_activities": [],
    "pending_user_decisions": [],
    "last_reprioritization": [],
    "last_updated": datetime.now(timezone.utc).isoformat()
}


# 🔥 Run Dynamic Reprioritizer
print("\n=== Initial Reprioritization Run ===")
updated_state = dynamic_reprioritizer(mock_state)
pprint(updated_state["last_reprioritization"])

# 📝 Simulate user feedback on suggested changes
# Accept task-001 change, reject task-003 change
mock_user_feedback = {
    "task-001": True,
    "task-003": False
}

print("\n=== Applying User Feedback ===")
updated_state = dynamic_reprioritizer(updated_state, user_feedback=mock_user_feedback)

# ✅ Print final state
print("\n=== Final State After User Feedback ===")
pprint(updated_state["tasks"])
pprint(updated_state["recent_activities"])
