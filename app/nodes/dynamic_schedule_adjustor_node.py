# nodes/dynamic_schedule_adjustor_node.py

from __future__ import annotations

from datetime import datetime, timedelta, timezone
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

class _Adjustment(BaseModel):
    item_id: str
    item_type: str = Field(..., pattern="^(task|event)$")
    suggested_status: str = Field(
        ..., pattern="^(prioritize|reschedule|defer|cancel)$"
    )
    new_start_time: Optional[str] = None
    new_end_time: Optional[str] = None
    reason: Optional[str] = None


class _ScheduleAdjustmentResponse(BaseModel):
    adjustments: List[_Adjustment]
    active_focus_block: Optional[bool] = None
    muted_channels: Optional[List[str]] = None


_parser = PydanticOutputParser(pydantic_object=_ScheduleAdjustmentResponse)

_PROMPT = PromptTemplate(
    template="""
You are ZenMaster, a hyper-adaptive personal productivity agent.
Optimise the user's day for both productivity and wellbeing.

🧠 Context:
- Cognitive load: {cognitive_load}
- Focus level: {focus_level}
- Stress level: {stress_level}
- Burnout risk: {burnout_risk}
- Energy level: {energy_level}
- Detected stress signatures: {stress_signatures}

💡 User Preferences:
- Work Hours: {work_hours}
- Deep Work Block: {deep_work_duration} mins
- Break Interval: {break_interval} mins
- Stress Hot Zones: {stress_hot_zones}

📆 Current Schedule:
Tasks:
{task_list}

Events:
{event_list}

Free/Busy slots:
{busy_slots}

For each task or event suggest: prioritize | reschedule | defer | cancel.
If rescheduling provide new_start_time and new_end_time (ISO 8601).
Also indicate if an active focus block should be set, and which channels to mute.
Provide a clear reason for each decision.

{format_instructions}
""",
    input_variables=[
        "cognitive_load", "focus_level", "stress_level", "burnout_risk",
        "energy_level", "stress_signatures", "work_hours", "deep_work_duration",
        "break_interval", "stress_hot_zones", "task_list", "event_list", "busy_slots",
    ],
    partial_variables={"format_instructions": _parser.get_format_instructions()},
)


# ---------------------------------------------------------------------------
# Node
# ---------------------------------------------------------------------------

def dynamic_schedule_adjustor(state: AgentState) -> Dict[str, Any]:
    log.info("dynamic_schedule_adjustor.start", user_id=state.user_id)

    if not state.tasks and not state.calendar_events:
        log.info("dynamic_schedule_adjustor.skip", reason="no tasks or events")
        return {}

    cog   = state.cognitive_state
    prefs = state.user_preferences

    task_list_str = "\n".join(
        f"- {tk.id}: {tk.title} | due: {tk.due_date} | priority: {tk.priority}"
        for tk in state.tasks
    ) or "None"

    event_list_str = "\n".join(
        f"- {ev.id}: {ev.title} | start: {ev.start_time} | end: {ev.end_time}"
        for ev in state.calendar_events
    ) or "None"

    stress_hot_zones = ", ".join(
        f"{k} ({v})" for k, v in prefs.stress_patterns.items()
    ) or "None"

    prompt_str = _PROMPT.format(
        cognitive_load=cog.cognitive_load,
        focus_level=cog.focus_level,
        stress_level=cog.stress_level,
        burnout_risk=str(cog.burnout_risk),
        energy_level=cog.energy_level,
        stress_signatures=", ".join(cog.detected_stress_signatures) or "None",
        work_hours=(
            f"{prefs.preferred_work_hours.get('start', '09:00')} - "
            f"{prefs.preferred_work_hours.get('end', '17:00')}"
        ),
        deep_work_duration=prefs.preferred_deep_work_duration,
        break_interval=prefs.preferred_break_interval,
        stress_hot_zones=stress_hot_zones,
        task_list=task_list_str,
        event_list=event_list_str,
        busy_slots=str(state.free_busy or state.busy_slots or "None"),
    )

    try:
        response = llm_service.invoke(
            prompt=prompt_str,
            node_name="DynamicScheduleAdjustor",
            user_id=state.user_id,
        )
        parsed: _ScheduleAdjustmentResponse = _parser.parse(response.content)
    except Exception as exc:
        log.error("dynamic_schedule_adjustor.parse_failed", error=str(exc))
        return {}

    # --- Apply adjustments ---
    tasks        = [tk.model_copy() for tk in state.tasks]
    events       = [ev.model_copy() for ev in state.calendar_events]
    task_map     = {tk.id: tk for tk in tasks}
    event_map    = {ev.id: ev for ev in events}
    activities   = list(state.recent_activities)
    adj_log: List[Dict] = []

    for adj in parsed.adjustments:
        item = task_map.get(adj.item_id) if adj.item_type == "task" \
               else event_map.get(adj.item_id)
        if not item:
            continue

        ts = datetime.now(timezone.utc).isoformat()

        if adj.suggested_status == "prioritize" and adj.item_type == "task":
            item.priority = "high"
        elif adj.suggested_status == "reschedule":
            if adj.new_start_time:
                item.start_time = adj.new_start_time
            if adj.new_end_time:
                item.end_time = adj.new_end_time
        elif adj.suggested_status == "defer" and adj.item_type == "task":
            if item.due_date:
                try:
                    new_due = datetime.fromisoformat(item.due_date) + timedelta(days=1)
                    item.due_date = new_due.isoformat()
                except ValueError:
                    pass
        elif adj.suggested_status == "cancel":
            item.status = "cancelled"

        reason_str = f" — {adj.reason}" if adj.reason else ""
        activities.append(
            f"[{ts}] {adj.item_type.title()} '{item.title}': "
            f"{adj.suggested_status}{reason_str}"
        )
        adj_log.append(adj.model_dump())

    log.info("dynamic_schedule_adjustor.done", user_id=state.user_id,
             adjustments=len(adj_log))

    return {
        "tasks": tasks,
        "calendar_events": events,
        "last_schedule_adjustments": adj_log,
        "active_focus_block": parsed.active_focus_block
                              if parsed.active_focus_block is not None
                              else state.active_focus_block,
        "muted_channels": parsed.muted_channels or state.muted_channels,
        "recent_activities": activities,
        "last_updated": datetime.now(timezone.utc).isoformat(),
    }