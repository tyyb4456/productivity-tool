from datetime import datetime, timedelta
from nodes.micro_intervention_suggestor_node import micro_intervention_suggestor
from state import AgentStateDict

# 📝 Mock AgentStateDict
mock_state: AgentStateDict = {
    "cognitive_state": {
        "cognitive_load": "high",
        "energy_level": "low",
        "focus_level": "distracted",
        "stress_level": "moderate",
        "detected_stress_signatures": ["tight deadlines", "poor sleep"],
        "burnout_risk": True
    },
    "trend_data": {
        "cognitive_load": [0.7, 0.8, 0.9],
        "energy_level": [0.4, 0.3, 0.2],
        "sleep_hours": [6, 5.5, 4],
        "deep_sleep_hours": [1.2, 1.0, 0.8],
        "rem_sleep_hours": [1.5, 1.3, 1.1],
        "wake_up_counts": [3, 4, 5],
        "steps": [5000, 3000, 2000],
        "active_minutes": [30, 20, 10],
        "mood_entries": ["stressed", "tired", "anxious"],
        "sentiment_scores": ["negative", "negative", "negative"],
        "detected_stress_signatures": ["back-to-back meetings", "sleep deprivation"],
        "burnout_risk": [True, True, True],
        "detected_stress_factors": ["workload", "lack of breaks"]
    },
    "burnout_status": {
        "burnout_risk": True,
        "severity": "high",
        "reason": "Sustained high cognitive load and poor sleep",
        "detected_stress_factors": ["tight deadlines", "poor recovery"],
        "recommended_action": "schedule recovery block"
    },
    "health_data": {
        "sedentary_period": 180,  # minutes sitting
        "steps_today": 1500,
        "active_minutes": 10,
        "mood": "tired"
    },
    "current_activity": "Reviewing a complex report",
    "user_location": "Office Desk",
    "recent_activities": [],
    "micro_interventions": [],
    "next_action_suggestion": None,
    "next_action_params": None,
    "user_feedback_prompt": None,
    "last_updated": datetime.utcnow(),
    "tasks": [],
    "calendar_events": [],
    "assessment_history": [],
    "pending_user_decisions": [],
    "last_reprioritization": [],
    "free_busy": [],
    "user_preferences": {
        "preferred_work_hours": {"start": "09:00", "end": "17:00"},
        "preferred_break_interval": 60,
        "preferred_deep_work_duration": 90,
        "stress_patterns": {"afternoon": "high"}
    }
}

# 🏃 Run the Node
if __name__ == "__main__":
    print("🔄 Testing Micro Intervention Suggestor Node...")
    updated_state = micro_intervention_suggestor(mock_state)
    
    print("\n✅ Updated Agent State:")
    print("Micro Interventions Suggested:")
    for intervention in updated_state["micro_interventions"]:
        print(f"- {intervention['message']} (Type: {intervention['type']}, Urgency: {intervention['urgency']})")
    
    print("\nNext Action Suggestion:")
    print(updated_state["next_action_suggestion"])
    
    print("\nUser Feedback Prompt:")
    print(updated_state["user_feedback_prompt"])
