# test_user_context_builder.py

from datetime import datetime, timedelta
from nodes.user_context_builder_node import user_context_builder
from state import AgentStateDict


def create_mock_state() -> AgentStateDict:
    # Mock calendar events (some today, some not)
    today = datetime.utcnow().date().isoformat()
    calendar_events = [
        {"title": "Team Standup", "start_time": f"{today}T09:00:00", "end_time": f"{today}T09:30:00"},
        {"title": "1:1 with Manager", "start_time": f"{today}T14:00:00", "end_time": f"{today}T14:30:00"},
        {"title": "Old Event", "start_time": "2024-01-01T10:00:00", "end_time": "2024-01-01T10:30:00"},
    ]

    # Mock tasks
    tasks = [
        {"title": "Finish report", "due_date": today, "priority": "high", "status": "in_progress"},
        {"title": "Reply to client", "due_date": today, "priority": "medium", "status": "pending"},
        {"title": "Completed Task", "due_date": today, "priority": "low", "status": "completed"},
    ]

    # Mock communication insights
    communication_insight = {
        "message_volume": 42,
        "avg_message_length": 87,
        "late_night_activity": True,
        "sentiment_trend": "slightly_negative"
    }

    # Mock health data
    health_data = {
        "sleep_hours": 6,
        "steps_today": 3500,
        "hrv": 45,
        "resting_heart_rate": 72,
        "mood": "tired"
    }

    # Initial agent state
    return {
        "calendar_events": calendar_events,
        "tasks": tasks,
        "communication_insight": communication_insight,
        "health_data": health_data,
        "alerts": [],
        "recent_activities": []
    }


def test_user_context_builder():
    print("=== Running test_user_context_builder ===")
    mock_state = create_mock_state()

    # Run the node
    updated_state = user_context_builder(mock_state)

    # Print cognitive state
    print("\n=== Cognitive State ===")
    print(updated_state["cognitive_state"])

    # Print alerts (if any)
    print("\n=== Alerts ===")
    for alert in updated_state.get("alerts", []):
        print(alert)

    # Print recent activities log
    print("\n=== Recent Activities ===")
    for activity in updated_state["recent_activities"]:
        print(activity)


if __name__ == "__main__":
    test_user_context_builder()
