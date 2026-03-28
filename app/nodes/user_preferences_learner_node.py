# app/nodes/user_preferences_learner_node.py

from datetime import datetime
from typing import Dict
from state import AgentStateDict


def user_preferences_learner(state: AgentStateDict) -> AgentStateDict:
    print("📖 [UserPreferencesLearner] Learning user preferences from historical data...")

    # 🕒 Adjust preferred work hours based on late-night activity
    late_night_activity = any(
        snapshot["inputs"].get("communication_summary", {}).get("late_night_activity", False)
        for snapshot in state.get("assessment_history", [])[-14:]  # Last 2 weeks
    )
    if late_night_activity:
        old_hours = state["user_preferences"]["preferred_work_hours"].copy()
        state["user_preferences"]["preferred_work_hours"] = {"start": "11:00", "end": "19:00"}
        print(f"🕒 Adjusted preferred work hours from {old_hours} to {state['user_preferences']['preferred_work_hours']}")

    # ⚡ Adjust deep work block duration if user shows low energy after long sessions
    last_week = state.get("assessment_history", [])[-7:]
    avg_energy = sum(
        (s["assessment"].get("energy_level_score") or 0) for s in last_week
    ) / max(len(last_week), 1)
    if avg_energy < 0.5:
        old_duration = state["user_preferences"]["preferred_deep_work_duration"]
        new_duration = max(45, old_duration - 15)
        state["user_preferences"]["preferred_deep_work_duration"] = new_duration
        print(f"⚡ Reduced deep work duration from {old_duration} mins to {new_duration} mins due to low energy.")

    # 🧘 Shorten break interval if high stress detected frequently
    high_stress_days = sum(
        1 for s in last_week
        if s["assessment"].get("stress_level") in ["high", "burnout_risk"]
    )
    if high_stress_days >= 3:
        old_break = state["user_preferences"]["preferred_break_interval"]
        new_break = max(30, old_break - 10)
        state["user_preferences"]["preferred_break_interval"] = new_break
        print(f"⏸️ Shortened break interval from {old_break} mins to {new_break} mins due to repeated stress.")

    # 🔥 Detect recurring stress patterns (stress hot zones)
    stress_patterns: Dict[str, str] = {}
    for snapshot in state.get("assessment_history", []):
        ts = snapshot["timestamp"]
        if isinstance(ts, datetime):
            ts = ts.strftime("%A %H:00")  # Example: "Tuesday 18:00"
        level = snapshot["assessment"].get("stress_level")
        if level in ["high", "burnout_risk"]:
            stress_patterns[ts] = level

    state["user_preferences"]["stress_patterns"] = stress_patterns
    if stress_patterns:
        print(f"🔥 Learned stress patterns: {stress_patterns}")

    print("\n\n-----------------------------------\n\n")
    print("📖 User preferences learning complete.")
    print(f"📝 Updated user preferences: {state['user_preferences']}")
    print("\n\n-----------------------------------\n\n")

    # 📝 Log update activity
    state["recent_activities"].append(
        f"[{datetime.utcnow().isoformat()}] Updated user preferences based on historical behavior."
    )

    return state
