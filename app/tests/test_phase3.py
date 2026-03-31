# tests/test_phase3.py
#
# Phase 3 API tests.
# No real Redis, no real Postgres, no real LLM calls.
# Uses httpx.AsyncClient + FastAPI TestClient with pytest-asyncio.
#
# Run:  pytest tests/test_phase3.py -v

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'app'))

import json
from datetime import datetime, timedelta, timezone
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

import jwt
import pytest
from fastapi.testclient import TestClient

from models import CognitiveState, Task
from state import AgentState

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_SECRET    = "change-me-in-production"
_ALGORITHM = "HS256"
_USER_ID   = "test-user-001"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_token(user_id: str = _USER_ID, expired: bool = False) -> str:
    exp = datetime.now(timezone.utc) + (
        timedelta(seconds=-1) if expired else timedelta(hours=1)
    )
    return jwt.encode({"sub": user_id, "exp": exp}, _SECRET, algorithm=_ALGORITHM)


def _fresh_state(**overrides) -> AgentState:
    s = AgentState(user_id=_USER_ID)
    if overrides:
        s = s.model_copy(update=overrides)
    return s


def _make_client() -> TestClient:
    from api.app import create_app
    return TestClient(create_app(), raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def client():
    return _make_client()


@pytest.fixture
def token():
    return _make_token()


@pytest.fixture
def auth_header(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def state():
    return _fresh_state()


# ---------------------------------------------------------------------------
# Health check  (no auth)
# ---------------------------------------------------------------------------

class TestHealth:

    def test_health_returns_ok(self, client):
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

class TestAuth:

    def test_missing_token_returns_401(self, client):
        r = client.get("/state")
        assert r.status_code == 401

    def test_malformed_token_returns_401(self, client):
        r = client.get("/state", headers={"Authorization": "Bearer not.a.token"})
        assert r.status_code == 401

    def test_expired_token_returns_401(self, client):
        token = _make_token(expired=True)
        r = client.get("/state", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 401

    def test_valid_token_passes(self, client, auth_header, state):
        with patch("api.dependencies.state_store") as mock_store:
            mock_store.load = AsyncMock(return_value=state)
            r = client.get("/state", headers=auth_header)
        assert r.status_code == 200


# ---------------------------------------------------------------------------
# GET /state
# ---------------------------------------------------------------------------

class TestGetState:

    def test_returns_full_state(self, client, auth_header, state):
        with patch("api.dependencies.state_store") as mock_store:
            mock_store.load = AsyncMock(return_value=state)
            r = client.get("/state", headers=auth_header)
        assert r.status_code == 200
        body = r.json()
        assert body["user_id"] == _USER_ID
        assert "cognitive_state" in body
        assert "tasks" in body
        assert "trend_data" in body

    def test_returns_stress_level(self, client, auth_header):
        state = _fresh_state(
            cognitive_state=CognitiveState(stress_level="high")
        )
        with patch("api.dependencies.state_store") as mock_store:
            mock_store.load = AsyncMock(return_value=state)
            r = client.get("/state", headers=auth_header)
        assert r.json()["cognitive_state"]["stress_level"] == "high"


class TestGetSummary:

    def test_summary_has_required_keys(self, client, auth_header, state):
        with patch("api.dependencies.state_store") as mock_store:
            mock_store.load = AsyncMock(return_value=state)
            r = client.get("/state/summary", headers=auth_header)
        assert r.status_code == 200
        body = r.json()
        for key in [
            "user_id", "cognitive_load", "stress_level",
            "energy_level", "burnout_risk", "alerts",
        ]:
            assert key in body, f"Missing key: {key}"

    def test_summary_is_smaller_than_full_state(self, client, auth_header, state):
        with patch("api.dependencies.state_store") as mock_store:
            mock_store.load = AsyncMock(return_value=state)
            full    = client.get("/state",         headers=auth_header).json()
            summary = client.get("/state/summary", headers=auth_header).json()
        assert len(json.dumps(summary)) < len(json.dumps(full))


class TestGetActivities:

    def test_returns_activities(self, client, auth_header):
        state = _fresh_state(
            recent_activities=["[ts] event A", "[ts] event B", "[ts] event C"]
        )
        with patch("api.dependencies.state_store") as mock_store:
            mock_store.load = AsyncMock(return_value=state)
            r = client.get("/state/activities", headers=auth_header)
        assert r.status_code == 200
        assert len(r.json()["activities"]) == 3

    def test_limit_param_respected(self, client, auth_header):
        state = _fresh_state(
            recent_activities=[f"[ts] event {i}" for i in range(20)]
        )
        with patch("api.dependencies.state_store") as mock_store:
            mock_store.load = AsyncMock(return_value=state)
            r = client.get("/state/activities?limit=5", headers=auth_header)
        assert len(r.json()["activities"]) == 5


class TestGetTrends:

    def test_returns_trend_data(self, client, auth_header, state):
        with patch("api.dependencies.state_store") as mock_store:
            mock_store.load = AsyncMock(return_value=state)
            r = client.get("/state/trends", headers=auth_header)
        assert r.status_code == 200
        assert "trend_data" in r.json()


# ---------------------------------------------------------------------------
# POST /run/*   (graph triggers — graph itself is mocked)
# ---------------------------------------------------------------------------

def _mock_graph(return_state: AgentState):
    """Returns a MagicMock that behaves like a compiled LangGraph subgraph."""
    g = MagicMock()
    g.invoke = MagicMock(return_value=return_state.model_dump())
    return g


class TestRunMorning:

    def test_returns_summary_on_success(self, client, auth_header, state):
        updated = state.model_copy(update={
            "cognitive_state": CognitiveState(cognitive_load="high"),
            "last_calendar_blocks": [{"title": "Focus Block: Report"}],
        })
        with patch("api.dependencies.state_store") as mock_store, \
             patch("api.routes.graph.morning_graph", _mock_graph(updated)), \
             patch("api.routes.graph.state_store") as mock_gs:
            mock_store.load  = AsyncMock(return_value=state)
            mock_gs.save     = AsyncMock()
            mock_gs.snapshot = AsyncMock()
            r = client.post("/run/morning", headers=auth_header)
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "ok"
        assert "cognitive_load" in body
        assert body["calendar_blocks"] == 1

    def test_500_on_graph_error(self, client, auth_header, state):
        bad_graph = MagicMock()
        bad_graph.invoke = MagicMock(side_effect=RuntimeError("LLM down"))
        with patch("api.dependencies.state_store") as mock_store, \
             patch("api.routes.graph.morning_graph", bad_graph):
            mock_store.load = AsyncMock(return_value=state)
            r = client.post("/run/morning", headers=auth_header)
        assert r.status_code == 500


class TestRunWorkday:

    def test_returns_reminder_count(self, client, auth_header, state):
        updated = state.model_copy(update={
            "generated_reminders": [{"message": "Drink water"}],
            "micro_interventions": [],
        })
        with patch("api.dependencies.state_store") as mock_store, \
             patch("api.routes.graph.workday_graph", _mock_graph(updated)), \
             patch("api.routes.graph.state_store") as mock_gs:
            mock_store.load  = AsyncMock(return_value=state)
            mock_gs.save     = AsyncMock()
            mock_gs.snapshot = AsyncMock()
            r = client.post("/run/workday", headers=auth_header)
        assert r.status_code == 200
        assert r.json()["reminders"] == 1


class TestRunEvening:

    def test_returns_feedback_summary(self, client, auth_header, state):
        updated = state.model_copy(update={
            "last_feedback_summary": "User prefers fewer reminders."
        })
        with patch("api.dependencies.state_store") as mock_store, \
             patch("api.routes.graph.evening_graph", _mock_graph(updated)), \
             patch("api.routes.graph.state_store") as mock_gs:
            mock_store.load  = AsyncMock(return_value=state)
            mock_gs.save     = AsyncMock()
            mock_gs.snapshot = AsyncMock()
            r = client.post("/run/evening", headers=auth_header)
        assert r.status_code == 200
        assert "feedback_summary" in r.json()


class TestAddTask:

    def test_adds_task_and_runs_workday(self, client, auth_header, state):
        updated = state.model_copy(update={
            "tasks": [Task(id="t1", title="Review PR", priority="high")]
        })
        with patch("api.dependencies.state_store") as mock_store, \
             patch("api.routes.graph.workday_graph", _mock_graph(updated)), \
             patch("api.routes.graph.state_store") as mock_gs:
            mock_store.load  = AsyncMock(return_value=state)
            mock_gs.save     = AsyncMock()
            mock_gs.snapshot = AsyncMock()
            r = client.post("/run/task", headers=auth_header, json={
                "id": "t1", "title": "Review PR", "priority": "high"
            })
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "ok"
        assert body["task_id"] == "t1"

    def test_invalid_task_body_returns_422(self, client, auth_header, state):
        with patch("api.dependencies.state_store") as mock_store:
            mock_store.load = AsyncMock(return_value=state)
            r = client.post("/run/task", headers=auth_header, json={})
        assert r.status_code == 422


# ---------------------------------------------------------------------------
# POST /feedback
# ---------------------------------------------------------------------------

class TestFeedback:

    def test_submit_feedback_triggers_evening_graph(self, client, auth_header, state):
        updated = state.model_copy(update={
            "last_feedback_summary": "Adjusted reminder frequency.",
            "last_feedback_updates": [{"preference": "reminder_frequency"}],
        })
        with patch("api.dependencies.state_store") as mock_store, \
             patch("api.routes.feedback.evening_graph", _mock_graph(updated)), \
             patch("api.routes.feedback.state_store") as mock_gs:
            mock_store.load  = AsyncMock(return_value=state)
            mock_gs.save     = AsyncMock()
            mock_gs.snapshot = AsyncMock()
            r = client.post("/feedback", headers=auth_header,
                            json={"text": "Too many reminders."})
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "ok"
        assert body["updates"] == 1

    def test_missing_text_returns_422(self, client, auth_header, state):
        with patch("api.dependencies.state_store") as mock_store:
            mock_store.load = AsyncMock(return_value=state)
            r = client.post("/feedback", headers=auth_header, json={})
        assert r.status_code == 422


class TestReprioritizationDecisions:

    def test_accept_decision_applies_priority_change(self, client, auth_header):
        state = _fresh_state(
            tasks=[Task(id="t1", title="Report", priority="normal")],
            last_reprioritization=[{
                "task_id": "t1", "new_priority": "high",
                "reason": "deadline soon",
                "detected_pressure_factors": None,
                "requires_user_confirmation": True,
            }],
        )
        with patch("api.dependencies.state_store") as mock_store, \
             patch("api.routes.feedback.state_store") as mock_gs:
            mock_store.load = AsyncMock(return_value=state)
            mock_gs.save    = AsyncMock()
            r = client.post(
                "/feedback/reprioritization",
                headers=auth_header,
                json={"decisions": [{"task_id": "t1", "accepted": True}]},
            )
        assert r.status_code == 200
        body = r.json()
        assert body["applied"] == 1
        assert body["rejected"] == 0

    def test_reject_decision(self, client, auth_header):
        state = _fresh_state(
            tasks=[Task(id="t2", title="Meeting prep", priority="high")],
            last_reprioritization=[{
                "task_id": "t2", "new_priority": "low",
                "reason": "burnout risk",
                "detected_pressure_factors": ["high_stress"],
                "requires_user_confirmation": True,
            }],
        )
        with patch("api.dependencies.state_store") as mock_store, \
             patch("api.routes.feedback.state_store") as mock_gs:
            mock_store.load = AsyncMock(return_value=state)
            mock_gs.save    = AsyncMock()
            r = client.post(
                "/feedback/reprioritization",
                headers=auth_header,
                json={"decisions": [{"task_id": "t2", "accepted": False}]},
            )
        assert r.status_code == 200
        assert r.json()["rejected"] == 1


class TestInjectNotifications:

    def test_notifications_are_filtered(self, client, auth_header, state):
        # After workday graph the allowed list should reflect filter decisions.
        # Mock the graph to pass all notifications through unchanged.
        updated_state = state.model_copy(update={
            "pending_notifications": ["Email: Project deadline extended"]
        })
        with patch("api.dependencies.state_store") as mock_store, \
             patch("api.routes.feedback.workday_graph", _mock_graph(updated_state)), \
             patch("api.routes.feedback.state_store") as mock_gs:
            mock_store.load  = AsyncMock(return_value=state)
            mock_gs.save     = AsyncMock()
            mock_gs.snapshot = AsyncMock()
            r = client.post(
                "/feedback/notifications",
                headers=auth_header,
                json={"notifications": [
                    "Email: Project deadline extended",
                    "Slack: standup in 5 mins",
                ]},
            )
        assert r.status_code == 200
        body = r.json()
        assert body["total_received"] == 2
        assert "allowed" in body

    def test_empty_notifications_list(self, client, auth_header, state):
        updated_state = state.model_copy(update={"pending_notifications": []})
        with patch("api.dependencies.state_store") as mock_store, \
             patch("api.routes.feedback.workday_graph", _mock_graph(updated_state)), \
             patch("api.routes.feedback.state_store") as mock_gs:
            mock_store.load  = AsyncMock(return_value=state)
            mock_gs.save     = AsyncMock()
            mock_gs.snapshot = AsyncMock()
            r = client.post("/feedback/notifications",
                            headers=auth_header, json={"notifications": []})
        assert r.status_code == 200
        assert r.json()["total_received"] == 0


# ---------------------------------------------------------------------------
# WebSocket
# ---------------------------------------------------------------------------

class TestWebSocket:

    def test_ws_rejects_missing_token(self, client):
        from starlette.websockets import WebSocketDisconnect
        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect("/ws/test-user") as ws:
                ws.receive_text()

    def test_ws_rejects_invalid_token(self):
        from fastapi.testclient import TestClient
        from api.app import create_app
        c = TestClient(create_app())
        with pytest.raises(Exception):
            with c.websocket_connect("/ws/test-user?token=bad.token.here") as ws:
                ws.receive_text()

    def test_ws_rejects_user_mismatch(self):
        """Token sub=user-A trying to subscribe to user-B's stream."""
        from fastapi.testclient import TestClient
        from api.app import create_app
        c   = TestClient(create_app())
        tok = _make_token(user_id="user-A")
        with pytest.raises(Exception):
            with c.websocket_connect(f"/ws/user-B?token={tok}") as ws:
                ws.receive_text()

    def test_ws_valid_connection_receives_ping(self):
        from fastapi.testclient import TestClient
        from api.app import create_app
        c   = TestClient(create_app())
        tok = _make_token(user_id=_USER_ID)
        with c.websocket_connect(f"/ws/{_USER_ID}?token={tok}") as ws:
            msg = json.loads(ws.receive_text())
            assert msg["type"] == "ping"