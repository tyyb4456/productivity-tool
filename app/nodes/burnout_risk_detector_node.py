# nodes/burnout_risk_detector_node.py

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import structlog
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import PromptTemplate
from pydantic import BaseModel, Field

from services.llm_service import llm_service
from state import AgentState
from utils.help_func import get_trend

log = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# LLM output schema
# ---------------------------------------------------------------------------

class _BurnoutAssessment(BaseModel):
    burnout_risk: bool
    severity: str = Field(..., pattern="^(low|moderate|high|critical)$")
    reason: str
    detected_stress_factors: List[str]
    recommended_action: Optional[str] = None


_parser = PydanticOutputParser(pydantic_object=_BurnoutAssessment)

_PROMPT = PromptTemplate(
    template="""
You are a wellbeing analyst AI. Assess the user's burnout risk from multi-day trends.

📊 Trends (last 3–7 days):
- Cognitive Load: {cognitive_load_trend}
- Energy Level: {energy_level_trend}
- Sleep Quality: {sleep_trend}
- Physical Activity: {activity_trend}
- Late-night activity: {late_night_activity}
- Sentiment trend: {sentiment_trend}
- Mood entries: {mood_trend}
- Detected stress signatures: {stress_signatures}

Rules:
1. Sustained high cognitive load without recovery → flag.
2. Consistent late-night work → flag.
3. Declining sleep quality (less deep/REM, more wake-ups) → flag.
4. Reduced physical activity vs baseline → flag.
5. Multiple moderate factors weigh heavier than one severe factor.

Output:
- burnout_risk (true/false)
- severity (low | moderate | high | critical)
- reason (explain)
- detected_stress_factors (list)
- recommended_action: one of: take a break | block calendar | defer tasks | mindfulness | sleep early

{format_instructions}
""",
    input_variables=[
        "cognitive_load_trend", "energy_level_trend", "sleep_trend",
        "activity_trend", "late_night_activity", "sentiment_trend",
        "mood_trend", "stress_signatures",
    ],
    partial_variables={"format_instructions": _parser.get_format_instructions()},
)


# ---------------------------------------------------------------------------
# Node
# ---------------------------------------------------------------------------

def burnout_risk_detector(state: AgentState) -> Dict[str, Any]:
    log.info("burnout_risk_detector.start", user_id=state.user_id)

    t = state.trend_data

    # Late-night activity count
    cutoff = datetime.now(timezone.utc) - timedelta(days=5)
    late_msgs = [
        m for m in state.recent_communication_messages
        if (ts := m.get("timestamp")) and (
            datetime.fromisoformat(ts).hour >= 22
            or datetime.fromisoformat(ts).hour < 7
        )
    ]
    late_night_str = f"{len(late_msgs)} late-night messages in last 5 days"

    sleep_trend = (
        f"Total: {t.sleep_hours}, Deep: {t.deep_sleep_hours}, "
        f"REM: {t.rem_sleep_hours}, Wake-ups: {t.wake_up_counts}"
    )
    activity_trend = f"Steps: {t.steps}, Active Minutes: {t.active_minutes}"

    prompt_str = _PROMPT.format(
        cognitive_load_trend=get_trend(t.cognitive_load, "CL"),
        energy_level_trend=get_trend(t.energy_level, "EL"),
        sleep_trend=sleep_trend,
        activity_trend=activity_trend,
        late_night_activity=late_night_str,
        sentiment_trend=", ".join(t.sentiment_scores) or "No data",
        mood_trend=", ".join(t.mood_entries) or "No data",
        stress_signatures=", ".join(t.detected_stress_signatures) or "None",
    )

    try:
        response = llm_service.invoke(
            prompt=prompt_str,
            node_name="BurnoutRiskDetector",
            user_id=state.user_id,
        )
        parsed: _BurnoutAssessment = _parser.parse(response.content)
    except Exception as exc:
        log.error("burnout_risk_detector.parse_failed", error=str(exc))
        return {}

    burnout_status = {
        "burnout_risk": parsed.burnout_risk,
        "severity": parsed.severity,
        "reason": parsed.reason,
        "detected_stress_factors": parsed.detected_stress_factors,
        "recommended_action": parsed.recommended_action,
    }

    schedule_adjustment = state.schedule_adjustment_required
    wellbeing_reminder  = state.wellbeing_reminder_required

    if parsed.burnout_risk:
        if parsed.recommended_action in ("block calendar", "defer tasks"):
            schedule_adjustment = True
        if parsed.recommended_action in ("take a break", "mindfulness", "sleep early"):
            wellbeing_reminder = True

    activity = (
        f"Burnout Risk Assessment: Risk={parsed.burnout_risk}, "
        f"Severity={parsed.severity}, Factors={parsed.detected_stress_factors}, "
        f"Action='{parsed.recommended_action}'"
    )
    updated = state.log_activity(activity)

    log.info(
        "burnout_risk_detector.done",
        user_id=state.user_id,
        burnout_risk=parsed.burnout_risk,
        severity=parsed.severity,
    )

    return {
        "burnout_status": burnout_status,
        "schedule_adjustment_required": schedule_adjustment,
        "wellbeing_reminder_required": wellbeing_reminder,
        "recent_activities": updated.recent_activities,
        "last_updated": updated.last_updated,
    }