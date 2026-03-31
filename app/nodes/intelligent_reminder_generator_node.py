# nodes/intelligent_reminder_generator_node.py

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

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

class _Reminder(BaseModel):
    reminder_id: str
    type: str = Field(
        ..., pattern="^(task|wellbeing|focus|hydration|sleep|break)$"
    )
    message: str
    urgency: str = Field(..., pattern="^(low|medium|high)$")
    reason: Optional[str] = None


class _ReminderResponse(BaseModel):
    reminders: List[_Reminder]


_parser = PydanticOutputParser(pydantic_object=_ReminderResponse)

_PROMPT = PromptTemplate(
    template="""
You are ZenMaster's Intelligent Reminder Generator.

🧠 User Cognitive State:
- Cognitive load: {cognitive_load}
- Focus level: {focus_level}
- Stress level: {stress_level}
- Burnout risk: {burnout_risk}
- Active Focus Block: {active_focus_block}
- Muted Channels: {muted_channels}

💖 Health Data:
- Sleep hours last night: {sleep_hours}
- Steps today: {steps_today}
- Mood: {mood}
- Hydration Status: {hydration_status}

📅 Upcoming Tasks/Events:
{task_list}

Generate intelligent reminders that:
- Respect active Focus Blocks (delay non-critical reminders).
- Encourage micro-breaks if user has been in Deep Work 90+ minutes.
- Prompt hydration if status is low.
- Warn if burnout risk is high.
- Remind about sleep preparation if it is evening.

For each reminder specify: reminder_id, type, message, urgency, reason.

{format_instructions}
""",
    input_variables=[
        "cognitive_load", "focus_level", "stress_level", "burnout_risk",
        "active_focus_block", "muted_channels", "sleep_hours", "steps_today",
        "mood", "hydration_status", "task_list",
    ],
    partial_variables={"format_instructions": _parser.get_format_instructions()},
)


# ---------------------------------------------------------------------------
# Node
# ---------------------------------------------------------------------------

def intelligent_reminder_generator(state: AgentState) -> Dict[str, Any]:
    log.info("intelligent_reminder_generator.start", user_id=state.user_id)

    cog  = state.cognitive_state
    hd   = state.health_data

    task_list_str = "\n".join(
        f"- {tk.id}: {tk.title} | due: {tk.due_date} | "
        f"priority: {tk.priority} | status: {tk.status}"
        for tk in state.tasks if tk.status != "completed"
    ) or "None"

    active_focus_block = "Yes" if state.active_focus_block else "No"
    muted_channels_str = ", ".join(state.muted_channels) or "None"

    prompt_str = _PROMPT.format(
        cognitive_load=cog.cognitive_load,
        focus_level=cog.focus_level,
        stress_level=cog.stress_level,
        burnout_risk=str(cog.burnout_risk),
        active_focus_block=active_focus_block,
        muted_channels=muted_channels_str,
        sleep_hours=hd.sleep_hours,
        steps_today=hd.steps_today,
        mood=hd.mood,
        hydration_status=hd.hydration_level,
        task_list=task_list_str,
    )

    try:
        response = llm_service.invoke(
            prompt=prompt_str,
            node_name="IntelligentReminderGenerator",
            user_id=state.user_id,
        )
        parsed: _ReminderResponse = _parser.parse(response.content)
    except Exception as exc:
        log.error("intelligent_reminder_generator.parse_failed", error=str(exc))
        return {}

    # Apply — delay low-urgency reminders during active focus block
    reminder_log: List[Dict] = []
    activities = list(state.recent_activities)

    for reminder in parsed.reminders:
        ts = datetime.now(timezone.utc).isoformat()
        if state.active_focus_block and reminder.urgency == "low":
            activities.append(
                f"[{ts}] Delayed reminder (Focus Block active): "
                f"{reminder.message} (Reason: {reminder.reason})"
            )
            continue

        reminder_log.append(reminder.model_dump())
        activities.append(
            f"[{ts}] Reminder: {reminder.message} "
            f"(Type: {reminder.type}, Urgency: {reminder.urgency}, "
            f"Reason: {reminder.reason})"
        )

    log.info("intelligent_reminder_generator.done", user_id=state.user_id,
             reminders=len(reminder_log))

    return {
        "generated_reminders": reminder_log,
        "recent_activities": activities,
        "last_updated": datetime.now(timezone.utc).isoformat(),
    }