# nodes/update_trend_node.py
#
# Must run BEFORE UserContextBuilder and BurnoutRiskDetector so every
# assessment is made on fresh trend data.
# Node order in graph_builder: ToolNode → UpdateTrend → UserContextBuilder → ...

from __future__ import annotations

from datetime import datetime, timezone
from statistics import mean
from typing import Any, Dict, List

import structlog

from state import AgentState
from utils.help_func import (
    calculate_productive_hours_ratio,
    detect_stress_signatures,
    update_trend,
)

log = structlog.get_logger(__name__)


def update_trend_node(state: AgentState) -> Dict[str, Any]:
    """
    LangGraph node.
    Appends latest observations to every trend list (max 7 entries each).
    Returns a dict of updated trend_data fields only.
    """
    log.info("update_trend_node.start", user_id=state.user_id)

    # Work on a mutable copy of trend_data fields
    t = state.trend_data.model_copy(deep=True)
    cog  = state.cognitive_state
    hlth = state.health_data

    # --- Cognitive ---
    if cog.cognitive_load_score is not None:
        update_trend(t.cognitive_load, cog.cognitive_load_score)
    if cog.energy_level_score is not None:
        update_trend(t.energy_level, cog.energy_level_score)
    if cog.focus_level:
        update_trend(t.focus_level, cog.focus_level)

    # --- Sleep ---
    update_trend(t.sleep_hours,      hlth.sleep_hours)
    update_trend(t.deep_sleep_hours, hlth.deep_sleep_hours)
    update_trend(t.rem_sleep_hours,  hlth.rem_sleep_hours)
    update_trend(t.wake_up_counts,   hlth.wake_up_count)

    # --- Activity ---
    update_trend(t.steps,          hlth.steps_today)
    update_trend(t.active_minutes, hlth.active_minutes)

    # --- Mood ---
    if hlth.mood:
        update_trend(t.mood_entries, hlth.mood)

    # --- Sentiment (dominant value from last 20 messages) ---
    recent_msgs = state.recent_communication_messages
    if recent_msgs:
        sentiments: List[str] = [
            m.get("sentiment")
            for m in recent_msgs[-20:]
            if m.get("sentiment")
        ]
        if sentiments:
            dominant = max(set(sentiments), key=sentiments.count)
            update_trend(t.sentiment_scores, dominant)

    # --- Vitals ---
    if hlth.resting_heart_rate is not None:
        update_trend(t.resting_heart_rate, hlth.resting_heart_rate)
    if hlth.hrv is not None:
        update_trend(t.hrv, hlth.hrv)
    if hlth.hydration_level:
        update_trend(t.hydration_level, hlth.hydration_level)

    # --- Productive hours ratio ---
    ratio = calculate_productive_hours_ratio(state)
    update_trend(t.productive_hours_ratio, ratio)

    # --- Burnout risk flag ---
    t.burnout_risk.append(cog.burnout_risk)
    if len(t.burnout_risk) > 7:
        t.burnout_risk = t.burnout_risk[-7:]

    # --- Stress signatures (computed from the trend itself) ---
    # Pass a temporary state with the updated trend so detection sees fresh data
    temp_state = state.model_copy(update={"trend_data": t})
    t.detected_stress_signatures = detect_stress_signatures(temp_state)

    log.info(
        "update_trend_node.done",
        user_id=state.user_id,
        stress_signatures=t.detected_stress_signatures,
        productive_ratio=ratio,
    )

    return {"trend_data": t}