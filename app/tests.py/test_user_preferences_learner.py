# test_user_preferences_learner.py

from datetime import datetime, timedelta
from nodes.user_preferences_learner_node import user_preferences_learner
from state import AgentStateDict


def create_mock_state() -> AgentStateDict:
    # Generate mock assessment history (last 14 days)
    assessment_history = []
    for i in range(14):
        day_offset = timedelta(days=-i)
        snapshot = {
            "timestamp": datetime.utcnow() + day_offset,
            "inputs": {
                "communication_summary": {
                    "late_night_activity": i % 5 == 0  # simulate some late night activity
                }
            },
            "assessment": {
                "energy_level_score": 0.3 if i % 3 == 0 else 0.8,  # low energy every 3rd day
                "stress_level": "high" if i % 4 == 0 else "normal"
            }
        }
        assessment_history.append(snapshot)

    # Initial user preferences
    user_preferences = {
        "preferred_work_hours": {"start": "09:00", "end": "17:00"},
        "preferred_deep_work_duration": 90,
        "preferred_break_interval": 60,
        "stress_patterns": {}
    }

    return {
        "assessment_history": assessment_history,
        "user_preferences": user_preferences,
        "recent_activities": []
    }


def test_user_preferences_learner():
    print("=== Running test_user_preferences_learner ===")
    mock_state = create_mock_state()

    # Run the node
    updated_state = user_preferences_learner(mock_state)

    # Print the results
    print("\n=== Updated User Preferences ===")
    print(updated_state["user_preferences"])

    print("\n=== Recent Activities Log ===")
    for activity in updated_state["recent_activities"]:
        print(activity)


if __name__ == "__main__":
    test_user_preferences_learner()
