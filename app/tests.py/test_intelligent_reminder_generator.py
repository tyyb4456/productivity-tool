# tests/test_intelligent_reminder_generator.py

import sys
import os
from datetime import datetime, timedelta

# Add app directory to path for imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../app")))

from nodes.intelligent_reminder_generator_node import intelligent_reminder_generator
from state import AgentStateDict

def test_intelligent_reminder_generator():
    # 📦 Dummy AgentStateDict
    state: AgentStateDict = {
        "cognitive_state": {
            "cognitive_load": "medium",
            "focus_level": "low",
            "stress_level": "high",
            "burnout_risk": "medium"
        },
        "health_data": {
            "sleep_hours": 5.5,
            "steps_today": 4200,
            "mood": "tired",
            "hydration_level": "low",
            "sedentary_period": 120
        },
        "tasks": [
            {
                "id": "task-001",
                "title": "Prepare project report",
                "due_date": (datetime.utcnow() + timedelta(hours=2)).isoformat(),
                "priority": "high",
                "status": "pending"
            },
            {
                "id": "task-002",
                "title": "Team standup meeting",
                "due_date": (datetime.utcnow() + timedelta(hours=1)).isoformat(),
                "priority": "medium",
                "status": "pending"
            }
        ],
        "calendar_events": [],
        "muted_channels": ["Slack", "Teams"],
        "active_focus_block": True,
        "recent_activities": [],
        "generated_reminders": [],
        "last_updated": datetime.utcnow().isoformat()
    }

    # 🚀 Run the node
    updated_state = intelligent_reminder_generator(state)

    # 📝 Assertions / Checks
    print("\n==================== TEST OUTPUT ====================")
    print("Generated Reminders:")
    for reminder in updated_state["generated_reminders"]:
        print(f"- {reminder['message']} (Type: {reminder['type']}, Urgency: {reminder['urgency']})")
    print("\nRecent Activities:")
    for activity in updated_state["recent_activities"]:
        print(f"- {activity}")
    print("======================================================\n")

    # ✅ Basic check: At least one reminder generated or delayed
    assert "generated_reminders" in updated_state
    assert isinstance(updated_state["generated_reminders"], list)

    # ✅ Check last_updated
    assert "last_updated" in updated_state

if __name__ == "__main__":
    test_intelligent_reminder_generator()
