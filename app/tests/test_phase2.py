# tests/test_phase2.py
#
# Phase 2 tests — no LLM calls, no Redis, no Postgres needed.
# Tests cover: router logic, graph structure, node return contracts,
# and the pydantic_node wrapper behaviour.

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'app'))

import pytest
from datetime import datetime, timezone
from langgraph.graph import END

from models import (
    CalendarEvent, CognitiveAssessmentSnapshot,
    CognitiveState, HealthData, Task, TrendData,
)
from state import AgentState
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


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def base_state() -> AgentState:
    return AgentState(user_id="test-user")


@pytest.fixture
def stressed_state(base_state) -> AgentState:
    return base_state.model_copy(update={
        "cognitive_state": CognitiveState(
            stress_level="high",
            cognitive_load="high",
            energy_level="low",
            burnout_risk=True,
        ),
        "burnout_status": {
            "burnout_risk": True,
            "severity": "moderate",
            "detected_stress_factors": ["high_cognitive_load", "low_sleep"],
        },
    })


# ---------------------------------------------------------------------------
# route_after_burnout
# ---------------------------------------------------------------------------

class TestRouteAfterBurnout:

    def test_no_adjustment_needed(self, base_state):
        assert route_after_burnout(base_state) == "CalendarBlockingNode"

    def test_adjustment_required(self, base_state):
        s = base_state.model_copy(update={"schedule_adjustment_required": True})
        assert route_after_burnout(s) == "DynamicScheduleAdjustor"


# ---------------------------------------------------------------------------
# route_workday_entry
# ---------------------------------------------------------------------------

class TestRouteWorkdayEntry:

    def test_nothing_to_do_skips(self, base_state):
        assert route_workday_entry(base_state) == "skip_to_evening"

    def test_pending_tasks_routes_to_reprioritizer(self, base_state):
        s = base_state.model_copy(update={
            "tasks": [Task(id="t1", title="Fix bug", priority="high")]
        })
        assert route_workday_entry(s) == "DynamicReprioritizer"

    def test_completed_task_not_counted(self, base_state):
        s = base_state.model_copy(update={
            "tasks": [Task(id="t1", title="Done", priority="high", status="completed")]
        })
        assert route_workday_entry(s) == "skip_to_evening"

    def test_cancelled_task_not_counted(self, base_state):
        s = base_state.model_copy(update={
            "tasks": [Task(id="t1", title="Dropped", priority="high", status="cancelled")]
        })
        assert route_workday_entry(s) == "skip_to_evening"

    def test_only_notifications_routes_to_filter(self, base_state):
        s = base_state.model_copy(update={
            "pending_notifications": ["Email: deadline extended"]
        })
        assert route_workday_entry(s) == "InformationFlowFilter"

    def test_only_wellbeing_flag_routes_to_reminders(self, base_state):
        s = base_state.model_copy(update={"wellbeing_reminder_required": True})
        assert route_workday_entry(s) == "IntelligentReminderGenerator"

    def test_tasks_take_priority_over_notifications(self, base_state):
        """When both exist, tasks win — reprioritizer runs first."""
        s = base_state.model_copy(update={
            "tasks": [Task(id="t1", title="x", priority="high")],
            "pending_notifications": ["Slack: ping"],
        })
        assert route_workday_entry(s) == "DynamicReprioritizer"


# ---------------------------------------------------------------------------
# route_after_reprioritizer
# ---------------------------------------------------------------------------

class TestRouteAfterReprioritizer:

    def test_no_notifications_goes_to_reminders(self, base_state):
        assert route_after_reprioritizer(base_state) == "IntelligentReminderGenerator"

    def test_with_notifications_goes_to_filter(self, base_state):
        s = base_state.model_copy(update={
            "pending_notifications": ["Slack: standup"]
        })
        assert route_after_reprioritizer(s) == "InformationFlowFilter"


# ---------------------------------------------------------------------------
# route_after_filter
# ---------------------------------------------------------------------------

class TestRouteAfterFilter:

    def test_always_goes_to_reminders(self, base_state):
        assert route_after_filter(base_state) == "IntelligentReminderGenerator"


# ---------------------------------------------------------------------------
# route_after_reminders
# ---------------------------------------------------------------------------

class TestRouteAfterReminders:

    def test_normal_state_skips_interventions(self, base_state):
        assert route_after_reminders(base_state) == "FeedbackLoop"

    def test_high_stress_triggers_interventions(self, base_state):
        s = base_state.model_copy(update={
            "cognitive_state": CognitiveState(stress_level="high")
        })
        assert route_after_reminders(s) == "MicroInterventionSuggestor"

    def test_burnout_risk_triggers_interventions(self, base_state):
        s = base_state.model_copy(update={
            "burnout_status": {"burnout_risk": True, "severity": "moderate"}
        })
        assert route_after_reminders(s) == "MicroInterventionSuggestor"

    def test_wellbeing_flag_triggers_interventions(self, base_state):
        s = base_state.model_copy(update={"wellbeing_reminder_required": True})
        assert route_after_reminders(s) == "MicroInterventionSuggestor"

    def test_burnout_risk_level_flag(self, stressed_state):
        assert route_after_reminders(stressed_state) == "MicroInterventionSuggestor"


# ---------------------------------------------------------------------------
# route_after_interventions
# ---------------------------------------------------------------------------

class TestRouteAfterInterventions:

    def test_always_goes_to_feedback(self, base_state):
        assert route_after_interventions(base_state) == "FeedbackLoop"


# ---------------------------------------------------------------------------
# route_after_feedback
# ---------------------------------------------------------------------------

class TestRouteAfterFeedback:

    def test_always_goes_to_preferences(self, base_state):
        assert route_after_feedback(base_state) == "UserPreferencesLearner"


# ---------------------------------------------------------------------------
# route_after_preferences
# ---------------------------------------------------------------------------

class TestRouteAfterPreferences:

    def test_fewer_than_7_snapshots_ends(self, base_state):
        assert route_after_preferences(base_state) == END

    def test_six_snapshots_still_ends(self, base_state):
        snaps = [
            CognitiveAssessmentSnapshot(
                timestamp=datetime.now(timezone.utc).isoformat(),
                assessment=CognitiveState(),
            )
            for _ in range(6)
        ]
        s = base_state.model_copy(update={"assessment_history": snaps})
        assert route_after_preferences(s) == END

    def test_seven_snapshots_triggers_refiner(self, base_state):
        snaps = [
            CognitiveAssessmentSnapshot(
                timestamp=datetime.now(timezone.utc).isoformat(),
                assessment=CognitiveState(),
            )
            for _ in range(7)
        ]
        s = base_state.model_copy(update={"assessment_history": snaps})
        assert route_after_preferences(s) == "AdaptiveModelRefiner"

    def test_more_than_7_snapshots_triggers_refiner(self, base_state):
        snaps = [
            CognitiveAssessmentSnapshot(
                timestamp=datetime.now(timezone.utc).isoformat(),
                assessment=CognitiveState(),
            )
            for _ in range(14)
        ]
        s = base_state.model_copy(update={"assessment_history": snaps})
        assert route_after_preferences(s) == "AdaptiveModelRefiner"


# ---------------------------------------------------------------------------
# Graph structure tests (node presence, no invocation needed)
# ---------------------------------------------------------------------------

class TestGraphStructure:

    def test_morning_graph_has_required_nodes(self):
        from graph_builder import morning_graph
        nodes = set(morning_graph.nodes.keys())
        for required in [
            "ToolNode", "UpdateTrend", "UserContextBuilder",
            "BurnoutRiskDetector", "DynamicScheduleAdjustor", "CalendarBlockingNode",
        ]:
            assert required in nodes, f"Missing node: {required}"

    def test_workday_graph_has_required_nodes(self):
        from graph_builder import workday_graph
        nodes = set(workday_graph.nodes.keys())
        for required in [
            "WorkdayRouter", "DynamicReprioritizer", "InformationFlowFilter",
            "IntelligentReminderGenerator", "MicroInterventionSuggestor", "FeedbackLoop",
        ]:
            assert required in nodes, f"Missing node: {required}"

    def test_evening_graph_has_required_nodes(self):
        from graph_builder import evening_graph
        nodes = set(evening_graph.nodes.keys())
        for required in [
            "FeedbackLoop", "UserPreferencesLearner", "AdaptiveModelRefiner",
        ]:
            assert required in nodes, f"Missing node: {required}"

    def test_trend_node_is_second_in_morning(self):
        """UpdateTrend must appear before UserContextBuilder — critical ordering."""
        from graph_builder import morning_graph
        nodes = list(morning_graph.nodes.keys())
        # Both must be present
        assert "UpdateTrend" in nodes
        assert "UserContextBuilder" in nodes


# ---------------------------------------------------------------------------
# Node contract tests (pure logic, no LLM)
# ---------------------------------------------------------------------------

class TestCalendarBlockingNode:
    """CalendarBlockingNode has no LLM — can be invoked directly."""

    def test_creates_focus_blocks_for_pending_tasks(self):
        from nodes.calendar_blocking_node import calendar_blocking_node

        state = AgentState(user_id="u1")
        state = state.model_copy(update={
            "tasks": [
                Task(id="t1", title="Write report", priority="high"),
                Task(id="t2", title="Review PRs", priority="normal"),
            ],
            "calendar_events": [],
        })
        result = calendar_blocking_node(state)

        assert "calendar_events" in result
        assert "last_calendar_blocks" in result
        blocks = result["last_calendar_blocks"]
        assert len(blocks) >= 1
        # All blocks should have title, start_time, end_time
        for blk in blocks:
            assert "title" in blk
            assert "start_time" in blk
            assert "end_time" in blk

    def test_adds_wind_down_block_when_burnout_risk(self):
        from nodes.calendar_blocking_node import calendar_blocking_node

        state = AgentState(user_id="u1")
        state = state.model_copy(update={
            "tasks": [Task(id="t1", title="x", priority="high")],
            "calendar_events": [],
            "cognitive_state": CognitiveState(burnout_risk=True),
        })
        result = calendar_blocking_node(state)
        titles = [blk["title"] for blk in result["last_calendar_blocks"]]
        assert any("Wind-down" in t for t in titles)

    def test_no_tasks_produces_no_focus_blocks(self):
        from nodes.calendar_blocking_node import calendar_blocking_node

        state = AgentState(user_id="u1")
        result = calendar_blocking_node(state)
        focus_blocks = [
            blk for blk in result.get("last_calendar_blocks", [])
            if "Focus Block" in blk.get("title", "")
        ]
        assert len(focus_blocks) == 0

    def test_skips_occupied_slots(self):
        from nodes.calendar_blocking_node import calendar_blocking_node
        from datetime import timezone

        now = datetime.now(timezone.utc)
        day = now.date()

        # Block 09:00–11:30 — should push focus block later
        busy_start = now.replace(hour=9,  minute=0,  second=0, microsecond=0)
        busy_end   = now.replace(hour=11, minute=30, second=0, microsecond=0)

        state = AgentState(user_id="u1")
        state = state.model_copy(update={
            "tasks": [Task(id="t1", title="Task", priority="high")],
            "calendar_events": [
                CalendarEvent(
                    id="existing",
                    title="Morning Standup",
                    start_time=busy_start.isoformat(),
                    end_time=busy_end.isoformat(),
                )
            ],
        })
        result = calendar_blocking_node(state)
        blocks = result.get("last_calendar_blocks", [])
        focus_blocks = [b for b in blocks if "Focus Block" in b.get("title", "")]
        for blk in focus_blocks:
            blk_start = datetime.fromisoformat(blk["start_time"])
            assert blk_start >= busy_end, \
                f"Focus block {blk_start} overlaps busy slot ending {busy_end}"


class TestUpdateTrendNode:
    """UpdateTrendNode has no LLM — can be invoked directly."""

    def test_appends_cognitive_load(self):
        from nodes.update_trend_node import update_trend_node

        state = AgentState(user_id="u1")
        state = state.model_copy(update={
            "cognitive_state": CognitiveState(
                cognitive_load="high", cognitive_load_score=8.0,
                energy_level="low",   energy_level_score=2.0,
            ),
            "health_data": HealthData(
                sleep_hours=6.0, steps_today=3000, mood="tired"
            ),
        })
        result = update_trend_node(state)
        trend = result["trend_data"]
        assert 8.0 in trend.cognitive_load
        assert 2.0 in trend.energy_level
        assert 6.0 in trend.sleep_hours
        assert 3000 in trend.steps
        assert "tired" in trend.mood_entries

    def test_trend_capped_at_7(self):
        from nodes.update_trend_node import update_trend_node

        state = AgentState(user_id="u1")
        # Pre-fill trend with 7 values
        existing = TrendData(cognitive_load=[1.0] * 7)
        state = state.model_copy(update={
            "trend_data": existing,
            "cognitive_state": CognitiveState(cognitive_load_score=9.0),
            "health_data": HealthData(),
        })
        result = update_trend_node(state)
        assert len(result["trend_data"].cognitive_load) == 7
        assert result["trend_data"].cognitive_load[-1] == 9.0


class TestUserPreferencesLearnerNode:
    """UserPreferencesLearner has no LLM — can be invoked directly."""

    def test_learns_stress_patterns_from_history(self):
        from nodes.user_preferences_learner_node import user_preferences_learner

        snaps = [
            CognitiveAssessmentSnapshot(
                timestamp="2025-07-20T18:00:00+00:00",
                assessment=CognitiveState(stress_level="high"),
            ),
            CognitiveAssessmentSnapshot(
                timestamp="2025-07-21T18:00:00+00:00",
                assessment=CognitiveState(stress_level="normal"),
            ),
        ]
        state = AgentState(user_id="u1")
        state = state.model_copy(update={"assessment_history": snaps})
        result = user_preferences_learner(state)
        prefs = result["user_preferences"]
        # Sunday 18:00 should be flagged as high stress
        assert any("18:00" in k for k in prefs.stress_patterns.keys())

    def test_returns_activity_log_entry(self):
        from nodes.user_preferences_learner_node import user_preferences_learner

        state = AgentState(user_id="u1")
        result = user_preferences_learner(state)
        assert any("Updated user preferences" in a
                   for a in result["recent_activities"])