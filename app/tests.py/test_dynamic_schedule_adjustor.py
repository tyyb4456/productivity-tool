from datetime import datetime, timedelta, timezone
from nodes.dynamic_schedule_adjustor_node import dynamic_schedule_adjustor
from state import AgentStateDict

# 📝 Create a mock state
state: AgentStateDict = {
    "cognitive_state": {
        "cognitive_load": 0.82,
        "focus_level": 0.6,
        "stress_level": 0.7,
        "burnout_risk": True,
        "energy_level": 0.4,
        "detected_stress_signatures": ["high_cognitive_load", "low_sleep_quality"]
    },
    "tasks": [
        {
            "id": "task1",
            "title": "Write project report",
            "due_date": (datetime.now(timezone.utc) + timedelta(hours=4)).isoformat(),
            "priority": "medium",
            "status": "pending"
        },
        {
            "id": "task2",
            "title": "Prepare slides for meeting",
            "due_date": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
            "priority": "high",
            "status": "pending"
        },
        {
            "id": "task3",
            "title": "Update team on Slack",
            "due_date": (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat(),
            "priority": "low",
            "status": "pending"
        }
    ],
    "calendar_events": [
        {
            "id": "event1",
            "title": "Daily Standup",
            "start_time": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
            "end_time": (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
        },
        {
            "id": "event2",
            "title": "Client Presentation",
            "start_time": (datetime.now(timezone.utc) + timedelta(hours=5)).isoformat(),
            "end_time": (datetime.now(timezone.utc) + timedelta(hours=6)).isoformat()
        }
    ],
    "user_preferences": {
        "preferred_work_hours": {"start": "09:00", "end": "18:00"},
        "preferred_deep_work_duration": 90,
        "preferred_break_interval": 60,
        "stress_patterns": {"afternoon": "higher stress"}
    },
    "free_busy": "9:00-10:00 Busy, 10:00-11:00 Free, 11:00-13:00 Busy",
    "recent_activities": [],
    "last_schedule_adjustments": [],
    "active_focus_block": False,
    "muted_channels": [],
    "last_updated": None
}

# 🏃 Run the node
updated_state = dynamic_schedule_adjustor(state)

# 📦 Print results
print("\n✅ Adjustments Applied:")
for adj in updated_state["last_schedule_adjustments"]:
    print(f"- {adj['item_type']} ({adj['item_id']}): {adj['suggested_status']} | Reason: {adj.get('reason', 'N/A')}")

print("\n📋 Recent Activities:")
for act in updated_state["recent_activities"]:
    print(f"- {act}")

print("\n🔒 Active Focus Block:", updated_state.get("active_focus_block", False))
print("🔕 Muted Channels:", updated_state.get("muted_channels", []))
