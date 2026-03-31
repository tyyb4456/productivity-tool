# graph_builder.py
#
# Three independently-invocable compiled subgraphs:
#
#   morning_graph   — data ingestion, context, schedule blocking
#   workday_graph   — reprioritize, filter, remind, intervene
#   evening_graph   — feedback, preferences, weekly meta-refinement
#
# Each graph is compiled once at import time and reused across runs.
# The Celery tasks (main.py) call graph.invoke(state.model_dump()) and
# receive back a dict that is merged back into a new AgentState.
#
# LangGraph note on state:
#   LangGraph needs a TypedDict or dict as its state container.
#   We use AgentState.model_dump() going in and AgentState.model_validate()
#   coming out, so the rest of the codebase always works with typed objects.

from __future__ import annotations

from langgraph.graph import END, StateGraph

from core.router import (
    route_after_burnout,
    route_after_feedback,
    route_after_filter,
    route_after_interventions,
    route_after_preferences,
    route_after_reminders,
    route_after_reprioritizer,
    route_workday_entry,
)
from nodes.adaptive_model_refiner_node import adaptive_model_refiner
from nodes.burnout_risk_detector_node import burnout_risk_detector
from nodes.calendar_blocking_node import calendar_blocking_node
from nodes.dynamic_reprioritizer_node import dynamic_reprioritizer
from nodes.dynamic_schedule_adjustor_node import dynamic_schedule_adjustor
from nodes.feedback_loop_node import feedback_loop_node
from nodes.information_flow_filter_node import information_flow_filter
from nodes.intelligent_reminder_generator_node import intelligent_reminder_generator
from nodes.micro_intervention_suggestor_node import micro_intervention_suggestor
# from nodes.tool_node import tool_node
from nodes.update_trend_node import update_trend_node
from nodes.user_context_builder_node import user_context_builder
from nodes.user_preferences_learner_node import user_preferences_learner
from state import AgentState


def get_tool_node():
    from nodes.tool_node import tool_node
    return tool_node

# ---------------------------------------------------------------------------
# Helper: wrap a Pydantic-aware node so LangGraph receives/returns plain dicts
# ---------------------------------------------------------------------------

def _pydantic_node(node_fn):

    def wrapper(state):
        actual = node_fn() if callable(node_fn) and node_fn.__name__ == "get_tool_node" else node_fn
        return actual(state)

    return wrapper


def _pydantic_router(fn):
    """Same but for router functions — returns a string, not a dict."""
    def wrapper(raw_state: dict) -> str:
        state = AgentState.model_validate(raw_state)
        return fn(state)
    wrapper.__name__ = fn.__name__
    return wrapper


# ---------------------------------------------------------------------------
# Morning Graph
#
# ToolNode → UpdateTrend → UserContextBuilder → BurnoutRiskDetector
#     ↓ (conditional)
#   DynamicScheduleAdjustor  ──→  CalendarBlockingNode
#   CalendarBlockingNode (direct path when no adjustment needed)
# ---------------------------------------------------------------------------

def build_morning_graph() -> StateGraph:
    g = StateGraph(dict)

    g.add_node("ToolNode",              _pydantic_node(get_tool_node))
    g.add_node("UpdateTrend",           _pydantic_node(update_trend_node))
    g.add_node("UserContextBuilder",    _pydantic_node(user_context_builder))
    g.add_node("BurnoutRiskDetector",   _pydantic_node(burnout_risk_detector))
    g.add_node("DynamicScheduleAdjustor", _pydantic_node(dynamic_schedule_adjustor))
    g.add_node("CalendarBlockingNode",  _pydantic_node(calendar_blocking_node))

    g.set_entry_point("ToolNode")
    g.add_edge("ToolNode",           "UpdateTrend")
    g.add_edge("UpdateTrend",        "UserContextBuilder")
    g.add_edge("UserContextBuilder", "BurnoutRiskDetector")

    g.add_conditional_edges(
        "BurnoutRiskDetector",
        _pydantic_router(route_after_burnout),
        {
            "DynamicScheduleAdjustor": "DynamicScheduleAdjustor",
            "CalendarBlockingNode":    "CalendarBlockingNode",
        },
    )

    g.add_edge("DynamicScheduleAdjustor", "CalendarBlockingNode")
    g.add_edge("CalendarBlockingNode",    END)

    return g.compile()


# ---------------------------------------------------------------------------
# Workday Graph
#
# Entry router → DynamicReprioritizer (optional)
#             → InformationFlowFilter (optional)
#             → IntelligentReminderGenerator
#             → MicroInterventionSuggestor (only if high stress / burnout)
#             → FeedbackLoop
# ---------------------------------------------------------------------------

def build_workday_graph() -> StateGraph:
    g = StateGraph(dict)

    g.add_node("WorkdayRouter",              lambda s: {})   # pass-through gate
    g.add_node("DynamicReprioritizer",       _pydantic_node(dynamic_reprioritizer))
    g.add_node("InformationFlowFilter",      _pydantic_node(information_flow_filter))
    g.add_node("IntelligentReminderGenerator", _pydantic_node(intelligent_reminder_generator))
    g.add_node("MicroInterventionSuggestor", _pydantic_node(micro_intervention_suggestor))
    g.add_node("FeedbackLoop",               _pydantic_node(feedback_loop_node))
    g.add_node("skip_to_evening",            lambda s: {})   # no-op terminal

    g.set_entry_point("WorkdayRouter")

    g.add_conditional_edges(
        "WorkdayRouter",
        _pydantic_router(route_workday_entry),
        {
            "DynamicReprioritizer":        "DynamicReprioritizer",
            "InformationFlowFilter":       "InformationFlowFilter",
            "IntelligentReminderGenerator": "IntelligentReminderGenerator",
            "FeedbackLoop":                "FeedbackLoop",
            "skip_to_evening":             "skip_to_evening",
        },
    )

    g.add_conditional_edges(
        "DynamicReprioritizer",
        _pydantic_router(route_after_reprioritizer),
        {
            "InformationFlowFilter":       "InformationFlowFilter",
            "IntelligentReminderGenerator": "IntelligentReminderGenerator",
        },
    )

    g.add_conditional_edges(
        "InformationFlowFilter",
        _pydantic_router(route_after_filter),
        {"IntelligentReminderGenerator": "IntelligentReminderGenerator"},
    )

    g.add_conditional_edges(
        "IntelligentReminderGenerator",
        _pydantic_router(route_after_reminders),
        {
            "MicroInterventionSuggestor": "MicroInterventionSuggestor",
            "FeedbackLoop":               "FeedbackLoop",
        },
    )

    g.add_conditional_edges(
        "MicroInterventionSuggestor",
        _pydantic_router(route_after_interventions),
        {"FeedbackLoop": "FeedbackLoop"},
    )

    g.add_edge("FeedbackLoop",    END)
    g.add_edge("skip_to_evening", END)

    return g.compile()


# ---------------------------------------------------------------------------
# Evening Graph
#
# FeedbackLoop → UserPreferencesLearner → AdaptiveModelRefiner (weekly only)
# ---------------------------------------------------------------------------

def build_evening_graph() -> StateGraph:
    g = StateGraph(dict)

    g.add_node("FeedbackLoop",            _pydantic_node(feedback_loop_node))
    g.add_node("UserPreferencesLearner",  _pydantic_node(user_preferences_learner))
    g.add_node("AdaptiveModelRefiner",    _pydantic_node(adaptive_model_refiner))

    g.set_entry_point("FeedbackLoop")

    g.add_conditional_edges(
        "FeedbackLoop",
        _pydantic_router(route_after_feedback),
        {"UserPreferencesLearner": "UserPreferencesLearner"},
    )

    g.add_conditional_edges(
        "UserPreferencesLearner",
        _pydantic_router(route_after_preferences),
        {
            "AdaptiveModelRefiner": "AdaptiveModelRefiner",
            END: END,
        },
    )

    g.add_edge("AdaptiveModelRefiner", END)

    return g.compile()


# ---------------------------------------------------------------------------
# Module-level compiled graphs — import and invoke directly
# ---------------------------------------------------------------------------

morning_graph = build_morning_graph()
workday_graph = build_workday_graph()
evening_graph = build_evening_graph()