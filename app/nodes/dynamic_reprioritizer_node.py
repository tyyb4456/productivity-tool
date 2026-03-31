# nodes/dynamic_reprioritizer_node.py

from __future__ import annotations

from datetime import datetime, timezone
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

class _TaskPriorityUpdate(BaseModel):
    task_id: str
    new_priority: str = Field(..., pattern="^(low|normal|medium|high|urgent)$")
    reason: Optional[str] = None
    detected_pressure_factors: Optional[List[str]] = None
    requires_user_confirmation: bool = False


class _ReprioritizationResponse(BaseModel):
    updates: List[_TaskPriorityUpdate]


_parser = PydanticOutputParser(pydantic_object=_ReprioritizationResponse)

_PROMPT = PromptTemplate(
    template="""
You are a task reprioritization expert helping balance productivity and wellbeing.

📊 User State & Trends
- Cognitive Load (current/trend): {cognitive_load} ({cognitive_load_trend})
- Energy Level (current/trend): {energy_level} ({energy_level_trend})
- Sleep Trends: {sleep_trends}
- Activity Trends: {activity_trends}
- Burnout Risk: {burnout_risk} ({burnout_trend})
- Stress Factors: {stress_factors}

📋 Pending Tasks
{task_list}

Rules:
- High burnout risk or sustained high cognitive load → consider downgrading non-urgent tasks.
- Keep high-urgency tasks unless health indicators show critical strain.
- List detected_pressure_factors (e.g. low_sleep_quality, high_cognitive_load).
- Set requires_user_confirmation=true for major downgrades (high → low).

For each task provide: task_id, new_priority, reason, detected_pressure_factors, requires_user_confirmation.

{format_instructions}
""",
    input_variables=[
        "cognitive_load", "cognitive_load_trend", "energy_level", "energy_level_trend",
        "sleep_trends", "activity_trends", "burnout_risk", "burnout_trend",
        "stress_factors", "task_list",
    ],
    partial_variables={"format_instructions": _parser.get_format_instructions()},
)


# ---------------------------------------------------------------------------
# Node
# ---------------------------------------------------------------------------

def dynamic_reprioritizer(
    state: AgentState,
    user_feedback: Optional[Dict[str, bool]] = None,
) -> Dict[str, Any]:
    """
    Two modes:
      1. Normal run  → LLM scores every pending task, applies changes.
      2. Feedback run → user_feedback={task_id: accepted} applies/rejects pending updates.
    """
    log.info("dynamic_reprioritizer.start", user_id=state.user_id)

    # --- Mode 2: Apply user feedback on a previous reprioritization run ---
    if user_feedback:
        return _apply_user_feedback(state, user_feedback)

    # --- Mode 1: LLM reprioritization ---
    t      = state.trend_data
    burnout = state.burnout_status

    pending_tasks = [tk for tk in state.tasks if tk.status != "completed"]
    if not pending_tasks:
        log.info("dynamic_reprioritizer.skip", reason="no pending tasks")
        return {}

    task_list_str = "\n".join(
        f"- {tk.id}: {tk.title} | due: {tk.due_date} | "
        f"priority: {tk.priority} | status: {tk.status}"
        for tk in pending_tasks
    )

    prompt_str = _PROMPT.format(
        cognitive_load=state.cognitive_state.cognitive_load,
        cognitive_load_trend=get_trend(t.cognitive_load, "CL")[-3:],
        energy_level=state.cognitive_state.energy_level,
        energy_level_trend=get_trend(t.energy_level, "EL")[-3:],
        sleep_trends=(
            f"Deep: {t.deep_sleep_hours[-3:]}, "
            f"REM: {t.rem_sleep_hours[-3:]}, "
            f"Wake-ups: {t.wake_up_counts[-3:]}"
        ),
        activity_trends=f"Steps: {t.steps[-3:]}, Active: {t.active_minutes[-3:]}",
        burnout_risk=burnout.get("severity", "low"),
        burnout_trend=t.burnout_risk[-3:],
        stress_factors=burnout.get("detected_stress_factors", []),
        task_list=task_list_str,
    )

    try:
        response = llm_service.invoke(
            prompt=prompt_str,
            node_name="DynamicReprioritizer",
            user_id=state.user_id,
        )
        parsed: _ReprioritizationResponse = _parser.parse(response.content)
    except Exception as exc:
        log.error("dynamic_reprioritizer.parse_failed", error=str(exc))
        return {}

    # --- Apply changes ---
    tasks      = [tk.model_copy() for tk in state.tasks]
    task_map   = {tk.id: tk for tk in tasks}
    activities = list(state.recent_activities)
    pending_decisions = list(state.pending_user_decisions)
    reprio_log: List[Dict] = []

    for update in parsed.updates:
        task = task_map.get(update.task_id)
        if not task:
            continue

        reprio_log.append(update.model_dump())

        if not update.requires_user_confirmation:
            old_priority     = task.priority
            task.priority    = update.new_priority
            ts = datetime.now(timezone.utc).isoformat()
            activities.append(
                f"[{ts}] Task '{task.title}' reprioritized "
                f"{old_priority} → {update.new_priority} "
                f"(Factors: {update.detected_pressure_factors}, "
                f"Reason: {update.reason})"
            )
        else:
            pending_decisions.append({
                "type": "reprioritization",
                "task_id": update.task_id,
                "suggestion": update.model_dump(),
            })
            ts = datetime.now(timezone.utc).isoformat()
            activities.append(
                f"[{ts}] Suggested reprioritization for "
                f"'{update.task_id}': {update.new_priority} (confirmation needed)"
            )

    log.info("dynamic_reprioritizer.done", user_id=state.user_id,
             updates=len(reprio_log))

    return {
        "tasks": tasks,
        "last_reprioritization": reprio_log,
        "pending_user_decisions": pending_decisions,
        "recent_activities": activities,
        "last_updated": datetime.now(timezone.utc).isoformat(),
    }


def _apply_user_feedback(
    state: AgentState,
    user_feedback: Dict[str, bool],
) -> Dict[str, Any]:
    tasks      = [tk.model_copy() for tk in state.tasks]
    task_map   = {tk.id: tk for tk in tasks}
    activities = list(state.recent_activities)

    for update in state.last_reprioritization:
        task = task_map.get(update["task_id"])
        if not task:
            continue
        ts = datetime.now(timezone.utc).isoformat()
        if user_feedback.get(update["task_id"], False):
            old = task.priority
            task.priority = update["new_priority"]
            activities.append(
                f"[{ts}] User confirmed reprioritization of "
                f"'{task.title}' from {old} → {task.priority}"
            )
        else:
            activities.append(
                f"[{ts}] User rejected reprioritization of '{task.title}'."
            )

    return {
        "tasks": tasks,
        "recent_activities": activities,
        "last_updated": datetime.now(timezone.utc).isoformat(),
    }