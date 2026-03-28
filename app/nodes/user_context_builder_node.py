# nodes/user_context_builder_node.py

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List

import structlog
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import PromptTemplate
from pydantic import BaseModel, Field

from models import CognitiveState
from services.llm_service import llm_service
from state import AgentState

log = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# LLM output schema
# ---------------------------------------------------------------------------

class _CognitiveAssessment(BaseModel):
    cognitive_load: str = Field(..., pattern="^(low|normal|high|overloaded)$")
    cognitive_load_score: float = Field(..., ge=0.0, le=10.0)
    focus_level: str = Field(..., pattern="^(low|normal|high)$")
    stress_level: str = Field(..., pattern="^(low|normal|high|burnout_risk)$")
    stress_level_score: float = Field(..., ge=0.0, le=10.0)
    burnout_risk: bool
    energy_level: str = Field(..., pattern="^(low|normal|moderate|high)$")
    energy_level_score: float = Field(..., ge=0.0, le=10.0)
    wellbeing_suggestion: str
    productivity_suggestion: str
    reasoning: str
    detected_stress_signatures: List[str] = Field(default_factory=list)


_parser = PydanticOutputParser(pydantic_object=_CognitiveAssessment)

_PROMPT = PromptTemplate(
    template="""
You are ZenMaster, a hyper-intelligent wellbeing and productivity coach.

Synthesize multi-source user data to assess the user's real-time cognitive and physical state.

---

📅 Calendar Summary:
{calendar_summary}

✅ Task Summary:
{task_summary}

💬 Communication Summary:
{comm_summary}

🛌 Health Summary:
{health_summary}

😌 Mood: {mood}
⏰ Time of Day: {time_of_day}

---

Assess:
- cognitive_load (low | normal | high | overloaded) + score 1–10
- focus_level (low | normal | high)
- stress_level (low | normal | high | burnout_risk) + score 1–10
- burnout_risk (true | false)
- energy_level (low | moderate | high) + score 1–10
- wellbeing_suggestion (short, supportive)
- productivity_suggestion (short, actionable)
- reasoning (explain scores referencing input data)
- detected_stress_signatures (list of tags, e.g. low_energy, high_stress_workload)

If time_of_day == morning: energizing wellbeing tone, planning productivity tone.
If time_of_day == evening: wind-down wellbeing tone, reflection productivity tone.

{format_instructions}
""",
    input_variables=[
        "calendar_summary", "task_summary", "comm_summary",
        "health_summary", "mood", "time_of_day",
    ],
    partial_variables={"format_instructions": _parser.get_format_instructions()},
)


# ---------------------------------------------------------------------------
# Node
# ---------------------------------------------------------------------------

def user_context_builder(state: AgentState) -> Dict[str, Any]:
    log.info("user_context_builder.start", user_id=state.user_id)

    now     = datetime.now(timezone.utc)
    today   = now.date().isoformat()

    # --- Build prompt inputs ---
    calendar_summary = "\n".join(
        f"- {ev.title} ({ev.start_time[11:16]}–{ev.end_time[11:16]})"
        for ev in state.calendar_events
        if ev.start_time.startswith(today)
    ) or "No meetings today."

    task_summary = "\n".join(
        f"- {t.title} | Due: {t.due_date or 'N/A'} | Priority: {t.priority}"
        for t in state.tasks
        if t.status != "completed"
    ) or "No pending tasks."

    ci = state.communication_insight
    comm_summary = (
        f"Volume: {ci.message_volume}, "
        f"Avg Length: {ci.avg_message_length}, "
        f"Late Night: {ci.late_night_activity}, "
        f"Trend: {ci.sentiment_trend}"
    )

    hd = state.health_data
    health_summary = (
        f"Sleep: {hd.sleep_hours}h, Steps: {hd.steps_today}, "
        f"HRV: {hd.hrv or 'N/A'}, RHR: {hd.resting_heart_rate or 'N/A'}"
    )

    time_of_day = "morning" if now.hour < 12 else "evening"

    prompt_str = _PROMPT.format(
        calendar_summary=calendar_summary,
        task_summary=task_summary,
        comm_summary=comm_summary,
        health_summary=health_summary,
        mood=hd.mood,
        time_of_day=time_of_day,
    )

    # --- Invoke LLM ---
    try:
        response = llm_service.invoke(
            prompt=prompt_str,
            node_name="UserContextBuilder",
            user_id=state.user_id,
        )
        parsed: _CognitiveAssessment = _parser.parse(response.content)
    except Exception as exc:
        log.error("user_context_builder.parse_failed", error=str(exc))
        parsed = _CognitiveAssessment(
            cognitive_load="normal", cognitive_load_score=5.0,
            focus_level="normal",
            stress_level="normal", stress_level_score=4.0,
            burnout_risk=False,
            energy_level="moderate", energy_level_score=5.0,
            wellbeing_suggestion="Take a short walk.",
            productivity_suggestion="Review your top 3 tasks.",
            reasoning="LLM parse failed — using safe defaults.",
        )

    new_cog = CognitiveState(**parsed.model_dump())

    # --- Build alerts ---
    alerts = list(state.alerts)
    if new_cog.burnout_risk and new_cog.detected_stress_signatures:
        alerts.append("⚠️ Burnout risk detected: Sustained high stress and low recovery.")
    if new_cog.energy_level_score <= 3.0 and new_cog.detected_stress_signatures:
        alerts.append("⚠️ Low energy detected: Recommend rest and recovery actions.")

    activity = (
        f"Updated cognitive state: Load={new_cog.cognitive_load}, "
        f"Focus={new_cog.focus_level}, Stress={new_cog.stress_level}, "
        f"Burnout={new_cog.burnout_risk}, Energy={new_cog.energy_level}"
    )

    updated = state.log_activity(activity)

    log.info(
        "user_context_builder.done",
        user_id=state.user_id,
        cognitive_load=new_cog.cognitive_load,
        stress_level=new_cog.stress_level,
        burnout_risk=new_cog.burnout_risk,
    )

    return {
        "cognitive_state": new_cog,
        "last_cognitive_assessment": new_cog.model_dump(),
        "alerts": alerts,
        "recent_activities": updated.recent_activities,
        "last_updated": updated.last_updated,
    }