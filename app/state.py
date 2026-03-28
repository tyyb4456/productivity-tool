# app/state.py
#
# AgentState is the single source of truth flowing through every LangGraph node.
#
# Design decisions:
#   - Pydantic BaseModel instead of TypedDict.  Gives us validation, defaults,
#     .model_dump() for serialisation, and schema evolution via field aliases.
#   - All timestamps are timezone-aware ISO-8601 strings produced by
#     datetime.now(timezone.utc).isoformat() — never datetime.utcnow().
#   - State is IMMUTABLE inside nodes: nodes return a NEW dict produced by
#     state.model_copy(update={...}) so LangGraph's reducer works correctly.
#   - user_id is mandatory; everything else has a safe default so a fresh
#     state can be created with AgentState(user_id="...").

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, ConfigDict

from models import (
    CalendarEvent,
    CognitiveAssessmentSnapshot,
    CognitiveState,
    CommunicationInsight,
    HealthData,
    Note,
    Task,
    TrendData,
    UserPreferences,
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class AgentState(BaseModel):
    """Full agent state.  Passed between every LangGraph node."""

    # ------------------------------------------------------------------
    # Identity
    # ------------------------------------------------------------------
    user_id: str

    # ------------------------------------------------------------------
    # Data ingested by ToolNode
    # ------------------------------------------------------------------
    calendar_events: List[CalendarEvent] = Field(default_factory=list)
    free_busy: Dict[str, Any] = Field(default_factory=dict)
    tasks: List[Task] = Field(default_factory=list)
    notes: List[Note] = Field(default_factory=list)
    communication_insight: CommunicationInsight = Field(
        default_factory=CommunicationInsight
    )
    health_data: HealthData = Field(default_factory=HealthData)
    recent_communication_messages: List[Dict[str, Any]] = Field(default_factory=list)

    # ------------------------------------------------------------------
    # Core assessments (set by UserContextBuilder + BurnoutRiskDetector)
    # ------------------------------------------------------------------
    cognitive_state: CognitiveState = Field(default_factory=CognitiveState)
    burnout_status: Dict[str, Any] = Field(default_factory=dict)
    last_cognitive_assessment: Dict[str, Any] = Field(default_factory=dict)

    # ------------------------------------------------------------------
    # Trend history (rolling 7-day window, updated by TrendUpdater)
    # ------------------------------------------------------------------
    trend_data: TrendData = Field(default_factory=TrendData)
    assessment_history: List[CognitiveAssessmentSnapshot] = Field(
        default_factory=list
    )

    # ------------------------------------------------------------------
    # User configuration (set by UserPreferencesLearner + FeedbackLoop)
    # ------------------------------------------------------------------
    user_preferences: UserPreferences = Field(default_factory=UserPreferences)
    model_refinement_profile: Dict[str, Any] = Field(default_factory=dict)

    # ------------------------------------------------------------------
    # Schedule & focus state
    # ------------------------------------------------------------------
    active_focus_block: bool = False
    active_focus_session: Dict[str, Any] = Field(default_factory=dict)
    muted_channels: List[str] = Field(default_factory=list)
    last_calendar_blocks: List[Dict[str, Any]] = Field(default_factory=list)
    busy_slots: List[Dict[str, Any]] = Field(default_factory=list)

    # ------------------------------------------------------------------
    # Node outputs  (used downstream, cleared each cycle)
    # ------------------------------------------------------------------
    last_reprioritization: List[Dict[str, Any]] = Field(default_factory=list)
    last_schedule_adjustments: List[Dict[str, Any]] = Field(default_factory=list)
    generated_reminders: List[Dict[str, Any]] = Field(default_factory=list)
    micro_interventions: List[Dict[str, Any]] = Field(default_factory=list)
    pending_notifications: List[str] = Field(default_factory=list)
    last_information_filter_decisions: List[Dict[str, Any]] = Field(
        default_factory=list
    )

    # ------------------------------------------------------------------
    # User interaction
    # ------------------------------------------------------------------
    next_action_suggestion: str = ""
    next_action_params: Dict[str, Any] = Field(default_factory=dict)
    user_feedback_prompt: str = ""
    recent_feedback: List[str] = Field(default_factory=list)   # ← was str; now list
    last_feedback_summary: str = ""
    last_feedback_updates: List[Dict[str, Any]] = Field(default_factory=list)
    pending_user_decisions: List[Dict[str, Any]] = Field(default_factory=list)

    # ------------------------------------------------------------------
    # Adaptive model refinement
    # ------------------------------------------------------------------
    last_model_refinement_summary: str = ""
    last_model_refinement_updates: List[Dict[str, Any]] = Field(default_factory=list)

    # ------------------------------------------------------------------
    # Control flags  (set by BurnoutRiskDetector to gate downstream nodes)
    # ------------------------------------------------------------------
    schedule_adjustment_required: bool = False
    wellbeing_reminder_required: bool = False

    # ------------------------------------------------------------------
    # Observability
    # ------------------------------------------------------------------
    alerts: List[str] = Field(default_factory=list)
    recent_activities: List[str] = Field(default_factory=list)
    current_activity: str = ""
    user_location: str = ""
    last_updated: str = Field(default_factory=_now_iso)

    # ------------------------------------------------------------------
    # Active reminders (persisted across short cycles)
    # ------------------------------------------------------------------
    active_reminders: List[Dict[str, Any]] = Field(default_factory=list)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def log_activity(self, message: str) -> "AgentState":
        """Return a copy of self with a new activity appended."""
        ts = datetime.now(timezone.utc).isoformat()
        updated = self.recent_activities + [f"[{ts}] {message}"]
        return self.model_copy(update={"recent_activities": updated, "last_updated": ts})

    def touch(self) -> "AgentState":
        """Return a copy with last_updated refreshed."""
        return self.model_copy(update={"last_updated": _now_iso()})

    model_config = ConfigDict(extra="ignore")