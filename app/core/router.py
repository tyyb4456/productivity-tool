# core/router.py
#
# All routing decisions live here — not in graph_builder.py.
# Each function receives the current AgentState and returns a string
# that LangGraph uses to pick the next node (or END).
#
# Keeping routing logic here makes it:
#   - easy to unit-test without a compiled graph
#   - easy to change routing rules without touching graph wiring

from __future__ import annotations

from typing import Literal

from langgraph.graph import END

from state import AgentState


# ---------------------------------------------------------------------------
# Morning phase router
# Decides what to do after BurnoutRiskDetector.
# ---------------------------------------------------------------------------

MorningRoute = Literal[
    "DynamicScheduleAdjustor",
    "CalendarBlockingNode",
]


def route_after_burnout(state: AgentState) -> MorningRoute:
    """
    If the burnout detector flagged schedule_adjustment_required,
    run the full DynamicScheduleAdjustor first.
    Otherwise go straight to CalendarBlockingNode.
    """
    if state.schedule_adjustment_required:
        return "DynamicScheduleAdjustor"
    return "CalendarBlockingNode"


# ---------------------------------------------------------------------------
# Workday phase routers
# ---------------------------------------------------------------------------

WorkdayRoute = Literal[
    "DynamicReprioritizer",
    "InformationFlowFilter",
    "IntelligentReminderGenerator",
    "MicroInterventionSuggestor",
    "FeedbackLoop",
    "skip_to_evening",
]


def route_workday_entry(state: AgentState) -> WorkdayRoute:
    """
    Gate the workday loop.
    If neither tasks nor notifications nor wellbeing reminders are needed,
    skip straight to the evening phase.
    """
    has_tasks         = any(t.status not in ("completed", "cancelled") for t in state.tasks)
    has_notifications = bool(state.pending_notifications)
    needs_wellbeing   = state.wellbeing_reminder_required

    if not has_tasks and not has_notifications and not needs_wellbeing:
        return "skip_to_evening"

    if has_tasks:
        return "DynamicReprioritizer"
    if has_notifications:
        return "InformationFlowFilter"
    return "IntelligentReminderGenerator"


def route_after_reprioritizer(state: AgentState) -> WorkdayRoute:
    """After reprioritization, filter notifications if any exist."""
    if state.pending_notifications:
        return "InformationFlowFilter"
    return "IntelligentReminderGenerator"


def route_after_filter(state: AgentState) -> WorkdayRoute:
    return "IntelligentReminderGenerator"


def route_after_reminders(state: AgentState) -> WorkdayRoute:
    """
    Only run MicroInterventionSuggestor when burnout or high stress warrants it.
    Otherwise proceed to the evening phase.
    """
    burnout_active = state.burnout_status.get("burnout_risk", False)
    high_stress    = state.cognitive_state.stress_level in ("high", "burnout_risk")

    if burnout_active or high_stress or state.wellbeing_reminder_required:
        return "MicroInterventionSuggestor"
    return "FeedbackLoop"


def route_after_interventions(state: AgentState) -> WorkdayRoute:
    return "FeedbackLoop"


# ---------------------------------------------------------------------------
# Evening / weekly phase routers
# ---------------------------------------------------------------------------

EveningRoute = Literal[
    "UserPreferencesLearner",
    END,
]

WeeklyRoute = Literal[
    "AdaptiveModelRefiner",
    END,
]


def route_after_feedback(state: AgentState):
    """Always run preferences learner after feedback."""
    return "UserPreferencesLearner"


def route_after_preferences(state: AgentState):
    """
    Only run AdaptiveModelRefiner when we have ≥7 assessment history snapshots
    (i.e. one full week of data) — prevents noisy meta-refinement on day 1.
    """
    if len(state.assessment_history) >= 7:
        return "AdaptiveModelRefiner"
    return END