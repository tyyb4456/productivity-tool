# test_calendar_blocking_node.py

from datetime import datetime, timedelta
from nodes.calendar_blocking_node import calendar_blocking_node

# 📝 Mock AgentStateDict
mock_state = {
    "user_preferences": {
        "preferred_work_hours": {"start": "09:00", "end": "17:00"},
        "preferred_deep_work_duration": 90,  # minutes
        "preferred_break_interval": 60  # minutes
    },
    "tasks": [
        {"title": "Write quarterly report", "status": "pending", "priority": "high", "due_date": "2025-07-10"},
        {"title": "Prepare slides for meeting", "status": "pending", "priority": "medium", "due_date": "2025-07-09"},
        {"title": "Inbox cleanup", "status": "pending", "priority": "low", "due_date": "2025-07-15"},
    ],
    "calendar_events": [
        {
            "title": "Morning Standup",
            "start_time": (datetime.utcnow().replace(hour=9, minute=30, second=0, microsecond=0)).isoformat(),
            "end_time": (datetime.utcnow().replace(hour=10, minute=0, second=0, microsecond=0)).isoformat()
        },
        {
            "title": "Client Call",
            "start_time": (datetime.utcnow().replace(hour=14, minute=0, second=0, microsecond=0)).isoformat(),
            "end_time": (datetime.utcnow().replace(hour=15, minute=0, second=0, microsecond=0)).isoformat()
        }
    ],
    "cognitive_state": {
        "burnout_risk": True  # To trigger evening wind-down block
    },
    "recent_activities": []
}

# 🚀 Run the calendar blocking node
updated_state = calendar_blocking_node(mock_state)

# 📅 Print results
print("\n=== 📅 Updated Calendar Events ===")
for event in updated_state["calendar_events"]:
    print(f"{event['start_time']} - {event['end_time']} | {event['title']}")

print("\n=== 📝 Recent Activities ===")
for activity in updated_state["recent_activities"]:
    print(activity)

print("\n=== ✅ Test Complete ===")
