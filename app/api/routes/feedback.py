# api/routes/feedback.py

from __future__ import annotations

from typing import Any, Dict, List

import structlog
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from api.dependencies import CurrentState, CurrentUser
from graph_builder import evening_graph, workday_graph
from services.state_store import state_store
from state import AgentState

log    = structlog.get_logger(__name__)
router = APIRouter(prefix="/feedback", tags=["feedback"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _run_and_persist(graph, state: AgentState) -> AgentState:
    raw_out: Dict[str, Any] = graph.invoke(state.model_dump())
    merged  = state.model_dump()
    merged.update(raw_out)
    updated = AgentState.model_validate(merged)
    await state_store.save(updated)
    await state_store.snapshot(updated)
    return updated


# ---------------------------------------------------------------------------
# Free-text feedback
# ---------------------------------------------------------------------------

class FeedbackRequest(BaseModel):
    text: str


@router.post("", summary="Submit free-text feedback — triggers preference learning")
async def submit_feedback(
    body:  FeedbackRequest,
    state: CurrentState,
) -> Dict[str, Any]:
    """
    Appends feedback to recent_feedback then runs the evening graph so
    FeedbackLoop and UserPreferencesLearner process it immediately.
    """
    log.info("api.submit_feedback", user_id=state.user_id)
    updated = state.model_copy(
        update={"recent_feedback": state.recent_feedback + [body.text]}
    )
    try:
        updated = await _run_and_persist(evening_graph, updated)
    except Exception as exc:
        log.error("api.submit_feedback.failed", user_id=state.user_id, error=str(exc))
        raise HTTPException(status_code=500, detail=str(exc))
    return {
        "status":  "ok",
        "summary": updated.last_feedback_summary,
        "updates": len(updated.last_feedback_updates),
    }


# ---------------------------------------------------------------------------
# Reprioritization decisions  (accept / reject)
# ---------------------------------------------------------------------------

class ReprioritizationDecision(BaseModel):
    task_id:  str
    accepted: bool


class ReprioritizationDecisionsRequest(BaseModel):
    decisions: List[ReprioritizationDecision]


@router.post("/reprioritization", summary="Accept or reject pending reprioritization suggestions")
async def submit_reprioritization_decisions(
    body:  ReprioritizationDecisionsRequest,
    state: CurrentState,
) -> Dict[str, Any]:
    """
    Applies user accept/reject decisions to the last reprioritization run.
    Calls DynamicReprioritizer in feedback mode (no new LLM call needed).
    """
    log.info("api.reprioritization_decisions", user_id=state.user_id,
             count=len(body.decisions))

    feedback_map = {d.task_id: d.accepted for d in body.decisions}

    from nodes.dynamic_reprioritizer_node import dynamic_reprioritizer
    patch = dynamic_reprioritizer(state, user_feedback=feedback_map)

    merged = state.model_dump()
    merged.update(patch)
    updated = AgentState.model_validate(merged)

    await state_store.save(updated)
    return {
        "status":   "ok",
        "applied":  len([d for d in body.decisions if d.accepted]),
        "rejected": len([d for d in body.decisions if not d.accepted]),
    }


# ---------------------------------------------------------------------------
# Notification injection
# ---------------------------------------------------------------------------

class NotificationsRequest(BaseModel):
    notifications: List[str]


@router.post("/notifications", summary="Inject incoming notifications for filtering")
async def inject_notifications(
    body:  NotificationsRequest,
    state: CurrentState,
) -> Dict[str, Any]:
    """
    Appends new notifications to pending_notifications then runs the
    workday graph so InformationFlowFilter processes them immediately.
    """
    log.info("api.inject_notifications", user_id=state.user_id,
             count=len(body.notifications))

    merged_notifications = state.pending_notifications + body.notifications
    updated = state.model_copy(update={"pending_notifications": merged_notifications})

    try:
        updated = await _run_and_persist(workday_graph, updated)
    except Exception as exc:
        log.error("api.inject_notifications.failed", user_id=state.user_id, error=str(exc))
        raise HTTPException(status_code=500, detail=str(exc))

    return {
        "status":  "ok",
        "allowed": len(updated.pending_notifications),
        "total_received": len(body.notifications),
    }