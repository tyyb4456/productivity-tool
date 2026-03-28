# app/nodes/update_trend_node.py

from state import AgentStateDict
from utils.help_func import update_trend, calculate_productive_hours_ratio, detect_stress_signatures
from statistics import mean
from datetime import datetime, timedelta, timezone


def updateTrend(state: AgentStateDict) -> AgentStateDict:
    """
    Update trend data in the agent state based on recent observations.
    """
    print("🔄 Running UpdateTrend Node...")

    # --- 🧠 Cognitive Trends ---
    if state["cognitive_state"]["cognitive_load_score"] is not None:
        update_trend(state["trend_data"]["cognitive_load"], state["cognitive_state"]["cognitive_load_score"])
    if state["cognitive_state"]["energy_level_score"] is not None:
        update_trend(state["trend_data"]["energy_level"], state["cognitive_state"]["energy_level_score"])
    if state["cognitive_state"]["focus_level"] is not None:
        update_trend(state["trend_data"]["focus_level"], state["cognitive_state"]["focus_level"])

    # --- 🛌 Sleep Trends ---
    health = state["health_data"]
    if health["sleep_hours"] is not None:
        update_trend(state["trend_data"]["sleep_hours"], health["sleep_hours"])
    if health["deep_sleep_hours"] is not None:
        update_trend(state["trend_data"]["deep_sleep_hours"], health["deep_sleep_hours"])
    if health["rem_sleep_hours"] is not None:
        update_trend(state["trend_data"]["rem_sleep_hours"], health["rem_sleep_hours"])
    if health["wake_up_count"] is not None:
        update_trend(state["trend_data"]["wake_up_counts"], health["wake_up_count"])

    # --- 🏃‍♂️ Physical Activity Trends ---
    if health["steps_today"] is not None:
        update_trend(state["trend_data"]["steps"], health["steps_today"])
    if health["active_minutes"] is not None:
        update_trend(state["trend_data"]["active_minutes"], health["active_minutes"])

    # --- 😌 Mood Trends ---
    if health["mood"]:
        update_trend(state["trend_data"]["mood_entries"], health["mood"])

    # --- 💬 Sentiment Trends ---
    recent_msgs = state.get("recent_communication_messages", [])
    if recent_msgs:
        sentiments = [msg.get("sentiment") for msg in recent_msgs[-20:] if msg.get("sentiment")]
        if sentiments:
            avg_sentiment = max(set(sentiments), key=sentiments.count)
            update_trend(state["trend_data"]["sentiment_scores"], avg_sentiment)

    # --- ⏱ Productive Hours Ratio ---
    productive_ratio = calculate_productive_hours_ratio(state)
    update_trend(state["trend_data"]["productive_hours_ratio"], productive_ratio)

    # --- 🛑 Detect Stress Signatures ---
    stress_signatures = detect_stress_signatures(state)
    state["trend_data"]["detected_stress_signatures"] = stress_signatures

    # --- 🔥 Burnout Risk Trend ---
    state["trend_data"]["burnout_risk"].append(state["cognitive_state"]["burnout_risk"])

    # Trim lists to keep last 7 entries
    for key, value in state["trend_data"].items():
        if isinstance(value, list) and len(value) > 7:
            state["trend_data"][key] = value[-7:]

    print("\n📊 Updated Trend Data:\n", state["trend_data"], "\n")

    return state
