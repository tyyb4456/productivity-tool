# api/routes/state.py

from __future__ import annotations

from typing import Any, Dict, List

import structlog
from fastapi import APIRouter

from api.dependencies import CurrentState, CurrentUser
from state import AgentState

log    = structlog.get_logger(__name__)
router = APIRouter(prefix="/state", tags=["state"])


# ---------------------------------------------------------------------------
# Response schemas (plain dicts — no extra Pydantic models needed,
# AgentState.model_dump() is already the serialisable form)
# ---------------------------------------------------------------------------

@router.get("", summary="Full agent state for the current user")
async def get_state(state: CurrentState) -> Dict[str, Any]:
    """
    Returns the complete AgentState as JSON.
    Used by the frontend for full hydration on page load.
    """
    log.info("api.get_state", user_id=state.user_id)
    return state.model_dump()


@router.get("/summary", summary="Lightweight state summary for dashboard polling")
async def get_summary(state: CurrentState) -> Dict[str, Any]:
    """
    Returns only the fields the dashboard header needs.
    Keeps the payload small for frequent polling (~30 s intervals).
    """
    cog = state.cognitive_state
    return {
        "user_id":           state.user_id,
        "last_updated":      state.last_updated,
        "cognitive_load":    cog.cognitive_load,
        "stress_level":      cog.stress_level,
        "energy_level":      cog.energy_level,
        "burnout_risk":      cog.burnout_risk,
        "active_focus_block": state.active_focus_block,
        "alerts":            state.alerts,
        "next_action_suggestion": state.next_action_suggestion,
        "pending_decisions": len(state.pending_user_decisions),
    }


@router.get("/activities", summary="Recent activity log")
async def get_activities(
    state: CurrentState,
    limit: int = 50,
) -> Dict[str, Any]:
    """Returns the last N activity log entries."""
    entries = state.recent_activities[-limit:]
    return {"user_id": state.user_id, "activities": entries}


@router.get("/trends", summary="7-day trend data")
async def get_trends(state: CurrentState) -> Dict[str, Any]:
    return {
        "user_id":    state.user_id,
        "trend_data": state.trend_data.model_dump(),
    }