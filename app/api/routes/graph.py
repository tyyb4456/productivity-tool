# api/routes/graph.py
#
# Trigger graph runs from the API.
# Each endpoint loads state, runs the appropriate graph, persists the result,
# and returns the updated state summary.
#
# For long-running runs the frontend should use the WebSocket endpoint
# (/ws/{user_id}) to stream live progress rather than waiting on these.

from __future__ import annotations

from typing import Any, Dict, Optional

import structlog
from fastapi import APIRouter, BackgroundTasks, HTTPException, status
from pydantic import BaseModel

from api.dependencies import CurrentState, CurrentUser
from graph_builder import evening_graph, morning_graph, workday_graph
from models import Task
from services.state_store import state_store
from state import AgentState

log    = structlog.get_logger(__name__)
router = APIRouter(prefix="/run", tags=["graph"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _invoke_graph(graph, state: AgentState) -> AgentState:
    """Invoke a compiled LangGraph subgraph and merge the result into state."""
    raw_out: Dict[str, Any] = graph.invoke(state.model_dump())
    merged = state.model_dump()
    merged.update(raw_out)
    return AgentState.model_validate(merged)


async def _run_and_persist(graph, state: AgentState) -> AgentState:
    updated = _invoke_graph(graph, state)
    await state_store.save(updated)
    await state_store.snapshot(updated)
    return updated


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/morning", summary="Run morning routine (data ingest → context → calendar blocking)")
async def run_morning(state: CurrentState) -> Dict[str, Any]:
    log.info("api.run_morning", user_id=state.user_id)
    try:
        updated = await _run_and_persist(morning_graph, state)
    except Exception as exc:
        log.error("api.run_morning.failed", user_id=state.user_id, error=str(exc))
        raise HTTPException(status_code=500, detail=str(exc))
    return {
        "status": "ok",
        "cognitive_load": updated.cognitive_state.cognitive_load,
        "burnout_risk":   updated.cognitive_state.burnout_risk,
        "calendar_blocks": len(updated.last_calendar_blocks),
        "last_updated":   updated.last_updated,
    }


@router.post("/workday", summary="Run workday loop (reprioritize → filter → remind → intervene)")
async def run_workday(state: CurrentState) -> Dict[str, Any]:
    log.info("api.run_workday", user_id=state.user_id)
    try:
        updated = await _run_and_persist(workday_graph, state)
    except Exception as exc:
        log.error("api.run_workday.failed", user_id=state.user_id, error=str(exc))
        raise HTTPException(status_code=500, detail=str(exc))
    return {
        "status":          "ok",
        "reminders":       len(updated.generated_reminders),
        "interventions":   len(updated.micro_interventions),
        "pending_decisions": len(updated.pending_user_decisions),
        "last_updated":    updated.last_updated,
    }


@router.post("/evening", summary="Run evening routine (feedback → preferences → meta-refinement)")
async def run_evening(state: CurrentState) -> Dict[str, Any]:
    log.info("api.run_evening", user_id=state.user_id)
    try:
        updated = await _run_and_persist(evening_graph, state)
    except Exception as exc:
        log.error("api.run_evening.failed", user_id=state.user_id, error=str(exc))
        raise HTTPException(status_code=500, detail=str(exc))
    return {
        "status":        "ok",
        "feedback_summary": updated.last_feedback_summary,
        "last_updated":  updated.last_updated,
    }


# ---------------------------------------------------------------------------
# Task injection  (add task + immediately run workday loop)
# ---------------------------------------------------------------------------

class NewTaskRequest(BaseModel):
    id:          str
    title:       str
    description: str = ""
    due_date:    Optional[str] = None
    priority:    str = "normal"
    source:      str = "api"


@router.post("/task", summary="Add a new task and trigger workday reprioritization")
async def add_task_and_run(
    body:  NewTaskRequest,
    state: CurrentState,
) -> Dict[str, Any]:
    log.info("api.add_task", user_id=state.user_id, task_id=body.id)
    try:
        new_task = Task.model_validate(body.model_dump())
        updated  = state.model_copy(update={"tasks": state.tasks + [new_task]})
        updated  = await _run_and_persist(workday_graph, updated)
    except Exception as exc:
        log.error("api.add_task.failed", user_id=state.user_id, error=str(exc))
        raise HTTPException(status_code=500, detail=str(exc))
    return {
        "status":     "ok",
        "task_id":    body.id,
        "tasks_total": len(updated.tasks),
        "last_updated": updated.last_updated,
    }