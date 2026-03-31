# nodes/user_preferences_learner_node.py

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict

import structlog

from state import AgentState

log = structlog.get_logger(__name__)


def user_preferences_learner(state: AgentState) -> Dict[str, Any]:
    log.info("user_preferences_learner.start", user_id=state.user_id)

    prefs      = state.user_preferences.model_copy(deep=True)
    activities = list(state.recent_activities)

    # --- Adjust work hours based on late-night activity ---
    late_night_detected = any(
        snap.inputs.get("communication_summary", {}).get("late_night_activity", False)
        for snap in state.assessment_history[-14:]
    )
    if late_night_detected:
        old = prefs.preferred_work_hours.copy()
        prefs.preferred_work_hours = {"start": "11:00", "end": "19:00"}
        log.info("user_preferences_learner.work_hours_adjusted",
                 old=old, new=prefs.preferred_work_hours)

    # --- Reduce deep work duration if average energy is low ---
    last_week = state.assessment_history[-7:]
    if last_week:
        avg_energy = sum(
            (snap.assessment.energy_level_score or 0.0) for snap in last_week
        ) / len(last_week)
        if avg_energy < 5.0:                                  # 0–10 scale
            old_dur = prefs.preferred_deep_work_duration
            prefs.preferred_deep_work_duration = max(45, old_dur - 15)
            log.info("user_preferences_learner.deep_work_reduced",
                     old=old_dur, new=prefs.preferred_deep_work_duration)

    # --- Shorten break interval if high stress appeared ≥3 days ---
    high_stress_days = sum(
        1 for snap in last_week
        if snap.assessment.stress_level in ("high", "burnout_risk")
    )
    if high_stress_days >= 3:
        old_brk = prefs.preferred_break_interval
        prefs.preferred_break_interval = max(30, old_brk - 10)
        log.info("user_preferences_learner.break_interval_shortened",
                 old=old_brk, new=prefs.preferred_break_interval)

    # --- Learn stress hot zones ---
    stress_patterns: Dict[str, str] = {}
    for snap in state.assessment_history:
        ts = snap.timestamp
        try:
            dt = datetime.fromisoformat(ts)
            label = dt.strftime("%A %H:00")   # e.g. "Tuesday 18:00"
        except ValueError:
            continue
        if snap.assessment.stress_level in ("high", "burnout_risk"):
            stress_patterns[label] = snap.assessment.stress_level

    prefs.stress_patterns = stress_patterns

    ts_now = datetime.now(timezone.utc).isoformat()
    activities.append(
        f"[{ts_now}] Updated user preferences from historical behaviour."
    )

    log.info("user_preferences_learner.done", user_id=state.user_id,
             stress_hot_zones=len(stress_patterns))

    return {
        "user_preferences": prefs,
        "recent_activities": activities,
        "last_updated": ts_now,
    }