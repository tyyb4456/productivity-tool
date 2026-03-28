# test_adaptive_model_refiner_node.py

from datetime import datetime
from nodes.adaptive_model_refiner_node import adaptive_model_refiner
from state import AgentStateDict

def test_adaptive_model_refiner_node():
    # 📝 Mock AgentStateDict
    mock_state: AgentStateDict = {
        "cognitive_state": {
            "cognitive_load": "medium",
            "focus_level": "low",
            "stress_level": "high",
            "burnout_risk": "medium",
            "detected_stress_signatures": ["fatigue", "irritability"],
            "in_focus_mode": False,
            "muted_channels": []
        },
        "burnout_status": {
            "severity": "medium",
            "detected_stress_factors": ["long work hours", "poor sleep"]
        },
        "micro_interventions": [
            {"suggestion_id": "m1", "message": "Take a 5-min walk", "type": "physical", "urgency": "medium",
             "reason": "Sedentary for 2 hours", "params": {"duration": "5m"}, "user_feedback_prompt": "Want me to set a timer for your walk?"}
        ],
        "last_reprioritization": [
            {"item_id": "task_123", "action": "reschedule", "reason": "Energy dip post-lunch"}
        ],
        "user_preferences": {
            "reminder_style": "gentle",
            "break_frequency": "every 60 mins",
            "notification_filtering_level": "balanced"
        },
        "last_feedback_summary": "User prefers fewer notifications during focus periods.",
        "model_refinement_profile": {
            "intervention_aggressiveness": "medium",
            "schedule_rigidity": "semi-flexible"
        },
        "recent_activities": [],
        "last_model_refinement_summary": None,
        "last_model_refinement_updates": [],
        "last_updated": datetime.utcnow()
    }

    print("\n=== Before Adaptive Model Refiner ===")
    print(f"Model Refinement Profile: {mock_state['model_refinement_profile']}\n")

    # 🔥 Run the node
    updated_state = adaptive_model_refiner(mock_state)

    print("\n=== After Adaptive Model Refiner ===")
    print(f"Model Refinement Profile: {updated_state['model_refinement_profile']}")
    print(f"Refinement Summary: {updated_state['last_model_refinement_summary']}")
    print(f"Refinement Updates: {updated_state['last_model_refinement_updates']}")
    print(f"Recent Activities: {updated_state['recent_activities']}")
    print(f"Last Updated: {updated_state['last_updated']}")


if __name__ == "__main__":
    test_adaptive_model_refiner_node()
