# tests/test_feedback_loop_node.py

from datetime import datetime
from nodes.feedback_loop_node import feedback_loop_node
from state import AgentStateDict


def get_mock_state() -> AgentStateDict:
    return {
        "user_id": "user-123",
        "tasks": [],
        "calendar_events": [],
        "pending_notifications": [],
        "recent_feedback": [
            "The reminders feel too frequent and a bit distracting.",
            "I prefer more motivational tone in the morning."
        ],
        "user_preferences": {
            "reminder_frequency": "every 30 mins",
            "reminder_style": "neutral",
            "break_frequency": "every 2 hours"
        },
        "cognitive_state": {
            "cognitive_load": "high",
            "focus_level": "low",
            "stress_level": "medium",
            "burnout_risk": 0.4,
            "energy_level": "low",
            "detected_stress_signatures": [],
            "in_focus_mode": False,
            "muted_channels": []
        },
        "health_data": {
            "sleep_hours": 6,
            "steps_today": 1500,
            "hydration_level": "low",
            "mood": "neutral",
            "sedentary_period": 90
        },
        "trend_data": {
            "cognitive_load": [],
            "energy_level": [],
            "deep_sleep_hours": [],
            "rem_sleep_hours": [],
            "wake_up_counts": [],
            "steps": [],
            "active_minutes": [],
            "mood_entries": [],
            "sentiment_scores": []
        },
        "burnout_status": {
            "severity": "moderate",
            "detected_stress_factors": []
        },
        "active_focus_block": False,
        "muted_channels": [],
        "recent_activities": [],
        "micro_interventions": [],
        "generated_reminders": [],
        "last_schedule_adjustments": [],
        "last_feedback_summary": None,
        "last_feedback_updates": [],
        "next_action_suggestion": None,
        "next_action_params": None,
        "user_feedback_prompt": None,
        "free_busy": [],
        "current_activity": None,
        "user_location": "office",
        "last_updated": datetime.utcnow()
    }


def mock_llm_invoke(_):
    """
    Mocked LLM response for feedback_loop_node
    """
    class MockResponse:
        content = '''
        {
            "updates": [
                {
                    "preference": "reminder_frequency",
                    "new_value": "every 60 mins",
                    "reason": "User found reminders too frequent and distracting."
                },
                {
                    "preference": "reminder_style",
                    "new_value": "motivational",
                    "reason": "User prefers motivational tone in mornings."
                }
            ],
            "summary": "Adjusted reminder frequency and style based on user feedback."
        }
        '''
    return MockResponse()


def test_feedback_loop_node():
    """
    Simple test for feedback_loop_node without pytest
    """
    print("\n🔄 Running test_feedback_loop_node...")

    # Setup
    state = get_mock_state()

    # Patch llm.invoke
    from nodes import feedback_loop_node as node_module
    node_module.llm.invoke('moked content') == mock_llm_invoke

    # Run
    updated_state = feedback_loop_node(state)


    print("✅ Preferences updated correctly.")
    print("✅ Feedback summary:", updated_state["last_feedback_summary"])
    print("✅ Activity Log:")
    for activity in updated_state["recent_activities"]:
        print("   -", activity)

    print("\n🎉 Test Passed!\n")


if __name__ == "__main__":
    test_feedback_loop_node()
