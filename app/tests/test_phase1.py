# tests/test_phase1.py
#
# Run with:  pytest tests/test_phase1.py -v
#
# These tests are pure-Python — no LLM calls, no Redis, no Postgres needed.

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'app'))

import pytest
from datetime import datetime, timezone

from models import (
    CalendarEvent, CognitiveState, CommunicationInsight,
    HealthData, Note, Task, TrendData, UserPreferences,
)
from state import AgentState
from utils.help_func import (
    calculate_productive_hours_ratio,
    detect_sentiment_trend,
    detect_stress_signatures,
    get_trend,
    update_trend,
)


# ---------------------------------------------------------------------------
# AgentState
# ---------------------------------------------------------------------------

class TestAgentState:

    def test_fresh_state_defaults(self):
        s = AgentState(user_id="u1")
        assert s.cognitive_state.cognitive_load == "normal"
        assert s.trend_data.cognitive_load == []
        assert s.user_preferences.preferred_work_hours == {"start": "09:00", "end": "17:00"}
        assert s.tasks == []
        assert s.alerts == []

    def test_log_activity_immutability(self):
        s = AgentState(user_id="u1")
        s2 = s.log_activity("something happened")
        # original is untouched
        assert len(s.recent_activities) == 0
        assert len(s2.recent_activities) == 1
        assert "something happened" in s2.recent_activities[0]

    def test_touch_updates_timestamp(self):
        s = AgentState(user_id="u1")
        original_ts = s.last_updated
        import time; time.sleep(0.01)
        s2 = s.touch()
        assert s2.last_updated >= original_ts

    def test_json_round_trip(self):
        s = AgentState(user_id="round-trip")
        s = s.model_copy(update={
            "tasks": [Task(id="t1", title="Report", priority="high")],
            "health_data": HealthData(sleep_hours=6.5, mood="tired"),
        })
        s2 = AgentState.model_validate_json(s.model_dump_json())
        assert s2.user_id == "round-trip"
        assert s2.tasks[0].title == "Report"
        assert s2.health_data.sleep_hours == 6.5

    def test_extra_fields_ignored(self):
        """Old JSON with unknown keys should not crash (extra='ignore')."""
        raw = AgentState(user_id="u1").model_dump()
        raw["unknown_future_field"] = "some_value"
        s = AgentState.model_validate(raw)
        assert s.user_id == "u1"


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class TestTask:

    def test_valid_task(self):
        t = Task(id="t1", title="Fix bug", priority="high", status="pending")
        assert t.priority == "high"

    def test_invalid_priority_raises(self):
        with pytest.raises(Exception):
            Task(id="t2", title="x", priority="critical")   # not in enum

    def test_invalid_status_raises(self):
        with pytest.raises(Exception):
            Task(id="t3", title="x", status="done")         # not in enum

    def test_defaults(self):
        t = Task(id="t4", title="y")
        assert t.priority == "normal"
        assert t.status == "pending"
        assert t.tags == []


class TestCognitiveState:

    def test_score_bounds(self):
        with pytest.raises(Exception):
            CognitiveState(cognitive_load="high", cognitive_load_score=11.0)

    def test_defaults(self):
        c = CognitiveState()
        assert c.burnout_risk is False
        assert c.in_focus_mode is False
        assert c.muted_channels == []


class TestHealthData:

    def test_sleep_hours_bounds(self):
        with pytest.raises(Exception):
            HealthData(sleep_hours=25.0)   # > 24

    def test_hydration_enum(self):
        with pytest.raises(Exception):
            HealthData(hydration_level="medium")   # not in pattern


class TestCalendarEvent:

    def test_invalid_status(self):
        with pytest.raises(Exception):
            CalendarEvent(id="e1", title="Meeting", start_time="", end_time="",
                          status="maybe")


class TestUserPreferences:

    def test_deep_work_bounds(self):
        with pytest.raises(Exception):
            UserPreferences(preferred_deep_work_duration=5)   # < 15 min


# ---------------------------------------------------------------------------
# Utils — update_trend
# ---------------------------------------------------------------------------

class TestUpdateTrend:

    def test_max_len_enforced(self):
        lst = []
        for v in range(10):
            update_trend(lst, v, max_len=7)
        assert len(lst) == 7
        assert lst[-1] == 9

    def test_none_skipped(self):
        lst = [1, 2, 3]
        update_trend(lst, None)
        assert lst == [1, 2, 3]

    def test_single_append(self):
        lst = []
        update_trend(lst, 42)
        assert lst == [42]


# ---------------------------------------------------------------------------
# Utils — sentiment + trend
# ---------------------------------------------------------------------------

class TestSentimentTrend:

    def test_rising(self):
        assert detect_sentiment_trend([0.1, 0.5]) == "rising"

    def test_dropping(self):
        assert detect_sentiment_trend([0.5, 0.1]) == "dropping"

    def test_stable(self):
        assert detect_sentiment_trend([0.1, 0.15]) == "stable"

    def test_single_value(self):
        assert detect_sentiment_trend([0.5]) == "stable"


# ---------------------------------------------------------------------------
# Utils — detect_stress_signatures
# ---------------------------------------------------------------------------

class TestStressSignatures:

    def _state_with_trend(self, **kwargs) -> AgentState:
        t = TrendData(**kwargs)
        return AgentState(user_id="test").model_copy(update={"trend_data": t})

    def test_high_cognitive_load(self):
        s = self._state_with_trend(cognitive_load=[0.8, 0.85, 0.9])
        assert "high_cognitive_load_trend" in detect_stress_signatures(s)

    def test_no_flag_normal_load(self):
        s = self._state_with_trend(cognitive_load=[0.4, 0.5, 0.45])
        assert "high_cognitive_load_trend" not in detect_stress_signatures(s)

    def test_low_deep_sleep(self):
        s = self._state_with_trend(deep_sleep_hours=[0.8, 0.7, 0.6])
        assert "low_deep_sleep_trend" in detect_stress_signatures(s)

    def test_low_hrv(self):
        s = self._state_with_trend(hrv=[38.0, 36.0, 32.0])
        assert "low_hrv_trend" in detect_stress_signatures(s)

    def test_elevated_rhr(self):
        s = self._state_with_trend(resting_heart_rate=[78, 80, 82])
        assert "elevated_resting_heart_rate" in detect_stress_signatures(s)

    def test_late_night_activity(self):
        s = self._state_with_trend(late_night_activity_count=[3, 4, 3])
        assert "frequent_late_night_activity" in detect_stress_signatures(s)

    def test_reduced_physical_activity(self):
        # Needs 4+ data points; recent 3 << earlier baseline
        s = self._state_with_trend(steps=[9500, 9200, 4000, 3500, 2800])
        assert "reduced_physical_activity" in detect_stress_signatures(s)

    def test_no_signatures_on_empty(self):
        s = AgentState(user_id="empty")
        assert detect_stress_signatures(s) == []


# ---------------------------------------------------------------------------
# Utils — productive hours ratio
# ---------------------------------------------------------------------------

class TestProductiveHoursRatio:

    def test_empty_state_is_zero(self):
        s = AgentState(user_id="u1")
        assert calculate_productive_hours_ratio(s) == 0.0

    def test_bounds(self):
        s = AgentState(user_id="u1")
        r = calculate_productive_hours_ratio(s)
        assert 0.0 <= r <= 1.0