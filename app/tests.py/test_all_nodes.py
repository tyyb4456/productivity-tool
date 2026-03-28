# test_all_nodes.py

from datetime import datetime, timedelta
from app.state import AgentStateDict

# Import all nodes
from app.nodes.dynamic_schedule_adjustor_node import dynamic_schedule_adjustor
from app.nodes.micro_intervention_suggestor_node import micro_intervention_suggestor
from app.nodes.intelligent_reminder_generator_node import intelligent_reminder_generator
from app.nodes.information_flow_filter_node import information_flow_filter
from app.nodes.feedback_loop_node import feedback_loop_node
from app.nodes.adaptive_model_refiner_node import adaptive_model_refiner

# -------------------
# MOCK STATE BUILDER
# -------------------
def create_mock_state() -> AgentStateDict:
    return {
        "tasks": [
            {
                "id": "task_1",
                "title": "Finish report",
                "description": "Q2 financial report",
                "due_date": (datetime.utcnow() + timedelta(hours=4)).isoformat(),
                "priority": "normal",
                "status": "pending"
            }
        ],
        "calendar_events": [
            {
                "id": "event_1",
                "title": "Team Sync",
                "start_time": (datetime.utcnow() + timedelta(hours=2)).isoformat(),
                "end_time": (datetime.utcnow() + timedelta(hours=3)).isoformat(),
                "location": "Zoom"
            }
        ],
        "cognitive_state": {
            "cognitive_load": "high",
            "focus_level": "low",
            "stress_level": "medium",
            "burnout_risk": "medium",
            "detected_stress_signatures": ["fatigue", "irritability"],
            "in_focus_mode": True,
            "muted_channels": []
        },
        "burnout_status": {
            "severity": "medium",
            "detected_stress_factors": ["long work hours"]
        },
        "trend_data": {
            "cognitive_load": ["medium", "high", "high"],
            "energy_level": ["low", "medium", "low"],
            "deep_sleep_hours": [6, 5, 4],
            "rem_sleep_hours": [2, 1.5, 1],
            "wake_up_counts": [2, 3, 4],
            "steps": [2000, 1500, 1000],
            "active_minutes": [30, 20, 15],
            "mood_entries": ["neutral", "low", "low"],
            "sentiment_scores": ["neutral", "negative", "negative"]
        },
        "health_data": {
            "sleep_hours": 5,
            "steps_today": 1200,
            "mood": "tired",
            "hydration_level": "low",
            "sedentary_period": 180
        },
        "user_preferences": {
            "reminder_style": "gentle",
            "break_frequency": "every 60 mins",
            "preferred_work_hours": {"start": "09:00", "end": "17:00"},
            "preferred_deep_work_duration": 90,
            "preferred_break_interval": 60,
            "stress_patterns": {"afternoon": "high stress"},
            "notification_filtering_level": "balanced"
        },
        "free_busy": ["09:00-10:00 busy", "14:00-15:30 busy"],
        "pending_notifications": [
            "Slack: Urgent message from Manager",
            "Email: Newsletter from Product Team",
            "Teams: Standup meeting reminder"
        ],
        "recent_feedback": [
            "Too many notifications during focus mode",
            "Break reminders are too frequent"
        ],
        "micro_interventions": [],
        "last_reprioritization": [],
        "last_feedback_summary": "",
        "model_refinement_profile": {
            "intervention_aggressiveness": "medium",
            "schedule_rigidity": "semi-flexible"
        },
        "recent_activities": [],
        "last_model_refinement_summary": None,
        "last_model_refinement_updates": [],
        "last_updated": datetime.utcnow()
    }

# -------------------
# TEST RUNNER
# -------------------
def run_node_test(node_func, state, node_name):
    print(f"\n===== Running {node_name} =====")
    print("Before:")
    print(f"Recent Activities: {state['recent_activities']}")
    updated_state = node_func(state)
    print("\nAfter:")
    print(f"Recent Activities: {updated_state['recent_activities']}")
    print(f"Last Updated: {updated_state['last_updated']}")
    print("=" * 50)
    return updated_state


def test_all_nodes():
    state = create_mock_state()

    # 🔥 Sequentially run all nodes
    state = run_node_test(dynamic_schedule_adjustor, state, "Dynamic Schedule Adjustor")
    state = run_node_test(micro_intervention_suggestor, state, "Micro Intervention Suggestor")
    state = run_node_test(intelligent_reminder_generator, state, "Intelligent Reminder Generator")
    state = run_node_test(information_flow_filter, state, "Information Flow Filter")
    state = run_node_test(feedback_loop_node, state, "Feedback Loop Node")
    state = run_node_test(adaptive_model_refiner, state, "Adaptive Model Refiner")


if __name__ == "__main__":
    test_all_nodes()
