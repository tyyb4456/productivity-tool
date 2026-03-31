# nodes/micro_intervention_suggestor_node.py

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union

import structlog
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import PromptTemplate
from pydantic import BaseModel, Field

from services.llm_service import llm_service
from state import AgentState

log = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# LLM output schema
# ---------------------------------------------------------------------------

class _InterventionSuggestion(BaseModel):
    suggestion_id: str
    message: str
    type: str = Field(
        ..., pattern="^(physical|mental|hydration|mindset|calendar_block)$"
    )
    urgency: str = Field(..., pattern="^(low|medium|high)$")
    reason: str
    params: Optional[Dict[str, Union[str, int]]] = None
    user_feedback_prompt: str


class _InterventionResponse(BaseModel):
    interventions: List[_InterventionSuggestion]


_parser = PydanticOutputParser(pydantic_object=_InterventionResponse)

_PROMPT = PromptTemplate(
    template="""
You are a proactive wellbeing assistant. Suggest empathetic micro-interventions.

📊 User Context & Trends:
- Cognitive Load (current/trend): {cognitive_load} ({cognitive_load_trend})
- Energy Level (current/trend): {energy_level} ({energy_level_trend})
- Sleep Quality: {sleep_trends}
- Physical Activity: {activity_trends}
- Mood Trend: {mood_trend}
- Sentiment Trend: {sentiment_trend}
- Detected Stress Factors: {stress_factors}
- Burnout Risk Level: {burnout_risk_level}

📍 Current Situation:
- Current Task: {current_task}
- Location: {location}
- Time of Day: {time_of_day}
- Sedentary Minutes: {sedentary_minutes}

Suggest 1–3 micro-interventions. Types:
- physical: stretch, walk, posture correction
- mental: mindfulness, breathing, calming music
- hydration: reminder based on activity/status
- mindset: cognitive reframing
- calendar_block: recovery block (suggest only, do not auto-create)

For each provide: suggestion_id, message, type, urgency, reason, params (optional), user_feedback_prompt.

{format_instructions}
""",
    input_variables=[
        "cognitive_load", "cognitive_load_trend", "energy_level", "energy_level_trend",
        "sleep_trends", "activity_trends", "mood_trend", "sentiment_trend",
        "stress_factors", "burnout_risk_level", "current_task", "location",
        "time_of_day", "sedentary_minutes",
    ],
    partial_variables={"format_instructions": _parser.get_format_instructions()},
)


# ---------------------------------------------------------------------------
# Node
# ---------------------------------------------------------------------------

def micro_intervention_suggestor(state: AgentState) -> Dict[str, Any]:
    log.info("micro_intervention_suggestor.start", user_id=state.user_id)

    t       = state.trend_data
    burnout = state.burnout_status
    cog     = state.cognitive_state

    prompt_str = _PROMPT.format(
        cognitive_load=cog.cognitive_load,
        cognitive_load_trend=t.cognitive_load[-3:] or "none",
        energy_level=cog.energy_level,
        energy_level_trend=t.energy_level[-3:] or "none",
        sleep_trends=(
            f"Deep: {t.deep_sleep_hours[-3:]}, "
            f"REM: {t.rem_sleep_hours[-3:]}, "
            f"Wake-ups: {t.wake_up_counts[-3:]}"
        ),
        activity_trends=(
            f"Steps: {t.steps[-3:]}, "
            f"Active Minutes: {t.active_minutes[-3:]}"
        ),
        mood_trend=t.mood_entries[-3:] or "none",
        sentiment_trend=t.sentiment_scores[-3:] or "none",
        stress_factors=burnout.get("detected_stress_factors", []) or "none",
        burnout_risk_level=burnout.get("severity", "low"),
        current_task=state.current_activity or "none",
        location=state.user_location or "unknown",
        time_of_day=datetime.now(timezone.utc).strftime("%H:%M"),
        sedentary_minutes=state.health_data.sedentary_period or 0,
    )

    try:
        response = llm_service.invoke(
            prompt=prompt_str,
            node_name="MicroInterventionSuggestor",
            user_id=state.user_id,
        )
        parsed: _InterventionResponse = _parser.parse(response.content)
    except Exception as exc:
        log.error("micro_intervention_suggestor.parse_failed", error=str(exc))
        return {}

    intervention_log: List[Dict] = []
    activities = list(state.recent_activities)

    for iv in parsed.interventions:
        intervention_log.append(iv.model_dump())
        ts = datetime.now(timezone.utc).isoformat()
        activities.append(
            f"[{ts}] Micro Intervention: {iv.message} "
            f"(Type: {iv.type}, Urgency: {iv.urgency})"
        )

    first = parsed.interventions[0] if parsed.interventions else None

    log.info("micro_intervention_suggestor.done", user_id=state.user_id,
             interventions=len(intervention_log))

    return {
        "micro_interventions": intervention_log,
        "next_action_suggestion": first.message if first else "",
        "next_action_params": first.params if first else {},
        "user_feedback_prompt": first.user_feedback_prompt if first else "",
        "recent_activities": activities,
        "last_updated": datetime.now(timezone.utc).isoformat(),
    }