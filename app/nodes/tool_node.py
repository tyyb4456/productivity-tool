# nodes/tool_node.py
#
# Fetches data from all external integrations via Composio.
# Each integration is isolated: one failing does NOT abort the others.
# Health flags are set on state so downstream nodes can degrade gracefully.

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

import structlog
from composio import Composio

from models import CalendarEvent, CommunicationInsight, HealthData, Note, Task
from state import AgentState
from utils.help_func import analyze_sentiment, analyze_stress_marker, detect_sentiment_trend

log = structlog.get_logger(__name__)

_USER_ID    = os.getenv("COMPOSIO_USER_ID", "")
_composio   = Composio(api_key=os.getenv("COMPOSIO_API_KEY", ""))
_LOOK_AHEAD = int(os.getenv("CALENDAR_LOOKAHEAD_DAYS", "30"))


# ---------------------------------------------------------------------------
# Node entry point
# ---------------------------------------------------------------------------

def tool_node(state: AgentState) -> Dict[str, Any]:
    """
    LangGraph node.  Returns a dict of state fields to merge.
    Each integration is wrapped in its own try/except so partial failures
    leave the rest of the state intact.
    """
    log.info("tool_node.start", user_id=state.user_id)

    updates: Dict[str, Any] = {}

    updates.update(_fetch_calendar(state))
    updates.update(_fetch_tasks(state))
    updates.update(_fetch_notes(state))
    updates.update(_fetch_communication(state))
    updates.update(_fetch_health(state))

    log.info(
        "tool_node.done",
        user_id=state.user_id,
        events=len(updates.get("calendar_events", [])),
        tasks=len(updates.get("tasks", [])),
    )
    return updates


# ---------------------------------------------------------------------------
# Calendar
# ---------------------------------------------------------------------------

def _fetch_calendar(state: AgentState) -> Dict[str, Any]:
    now      = datetime.now(timezone.utc)
    start    = now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
    end      = (now + timedelta(days=_LOOK_AHEAD)).replace(
                    hour=23, minute=59, second=59).isoformat()

    try:
        result = _composio.tools.execute(
            "GOOGLECALENDAR_EVENTS_LIST",
            user_id=_USER_ID,
            arguments={"calendarId": "primary", "timeMin": start, "timeMax": end},
        )
        raw_events: List[Dict] = result.get("data", {}).get("items", [])
    except Exception as exc:
        log.warning("tool_node.calendar_failed", error=str(exc))
        return {}

    events: List[CalendarEvent] = []
    busy_slots: List[Dict[str, str]] = []

    for ev in raw_events:
        start_dt = ev.get("start", {}).get("dateTime")
        end_dt   = ev.get("end",   {}).get("dateTime")
        duration: float | None = None
        if start_dt and end_dt:
            duration = (
                datetime.fromisoformat(end_dt) - datetime.fromisoformat(start_dt)
            ).total_seconds() / 60
            busy_slots.append({"start": start_dt, "end": end_dt})

        events.append(CalendarEvent(
            id=ev.get("id", ""),
            title=ev.get("summary", "Untitled"),
            start_time=start_dt or "",
            end_time=end_dt or "",
            description=ev.get("description"),
            location=ev.get("location"),
            attendees=[a.get("email", "") for a in ev.get("attendees", []) if a.get("email")],
            is_meeting=bool(ev.get("attendees")),
            duration_minutes=duration,
            is_recurring=bool(ev.get("recurringEventId")),
            status="confirmed",
            source="GOOGLE_CALENDAR",
        ))

    return {"calendar_events": events, "busy_slots": busy_slots}


# ---------------------------------------------------------------------------
# Tasks (Todoist)
# ---------------------------------------------------------------------------

_PRIORITY_MAP = {1: "low", 2: "normal", 3: "high", 4: "urgent"}


def _fetch_tasks(state: AgentState) -> Dict[str, Any]:
    try:
        result = _composio.tools.execute(
            "TODOIST_TASKS_LIST", user_id=_USER_ID, arguments={}
        )
        raw_tasks: List[Dict] = result.get("data", [])
    except Exception as exc:
        log.warning("tool_node.tasks_failed", error=str(exc))
        return {}

    tasks = [
        Task(
            id=t.get("id", ""),
            title=t.get("content", ""),
            description=t.get("description", ""),
            due_date=(t.get("due") or {}).get("datetime") or (t.get("due") or {}).get("date"),
            priority=_PRIORITY_MAP.get(t.get("priority", 1), "normal"),
            status="completed" if t.get("is_completed") else "pending",
            source="Todoist",
            tags=t.get("labels", []),
        )
        for t in raw_tasks
    ]
    return {"tasks": tasks}


# ---------------------------------------------------------------------------
# Notes (Notion)
# ---------------------------------------------------------------------------

def _fetch_notes(state: AgentState) -> Dict[str, Any]:
    notion_db = os.getenv("NOTION_DATABASE_ID", "")
    if not notion_db:
        return {}
    try:
        result = _composio.tools.execute(
            "NOTION_PAGES_LIST",
            user_id=_USER_ID,
            arguments={"database_id": notion_db},
        )
        raw_notes: List[Dict] = result.get("data", {}).get("results", [])[:5]
    except Exception as exc:
        log.warning("tool_node.notes_failed", error=str(exc))
        return {}

    notes = [
        Note(
            id=n["id"],
            title=n.get("title", "Untitled"),
            created_at=n.get("created_time", ""),
            last_modified=n.get("last_edited_time", ""),
            source="Notion",
        )
        for n in raw_notes
    ]
    return {"notes": notes}


# ---------------------------------------------------------------------------
# Communication (Slack)
# ---------------------------------------------------------------------------

def _fetch_communication(state: AgentState) -> Dict[str, Any]:
    channel = os.getenv("SLACK_CHANNEL_ID", "")
    if not channel:
        return {}
    try:
        result = _composio.tools.execute(
            "SLACK_MESSAGES_LIST",
            user_id=_USER_ID,
            arguments={"channel": channel, "limit": 100},
        )
        messages: List[Dict] = result.get("data", {}).get("messages", [])
    except Exception as exc:
        log.warning("tool_node.slack_failed", error=str(exc))
        return {}

    volume      = len(messages)
    avg_length  = sum(len(m.get("text", "")) for m in messages) / max(volume, 1)
    late_night  = any(
        datetime.fromisoformat(m["timestamp"]).hour >= 22
        or datetime.fromisoformat(m["timestamp"]).hour < 6
        for m in messages
        if m.get("timestamp")
    )
    sentiments  = [analyze_sentiment(m.get("text", "")) for m in messages if m.get("text")]
    avg_sent    = sum(sentiments) / len(sentiments) if sentiments else 0.0

    return {
        "communication_insight": CommunicationInsight(
            message_volume=volume,
            avg_message_length=int(avg_length),
            late_night_activity=late_night,
            sentiment_score=avg_sent,
            sentiment_trend=detect_sentiment_trend(sentiments),
            source="Slack",
        ),
        "recent_communication_messages": messages,
    }


# ---------------------------------------------------------------------------
# Health (Apple HealthKit)
# ---------------------------------------------------------------------------

def _fetch_health(state: AgentState) -> Dict[str, Any]:
    try:
        result = _composio.tools.execute(
            "APPLEHEALTHKIT_DATA_GET",
            user_id=_USER_ID,
            arguments={
                "data_types": ["sleep", "steps", "heart_rate", "mood", "hydration"],
                "days": 7,
            },
        )
        hd: Dict = result.get("data", {})
    except Exception as exc:
        log.warning("tool_node.health_failed", error=str(exc))
        return {}

    return {
        "health_data": HealthData(
            sleep_hours=hd.get("sleep_hours", 0.0),
            deep_sleep_hours=hd.get("deep_sleep_hours", 0.0),
            rem_sleep_hours=hd.get("remaining_sleep_hours", 0.0),
            wake_up_count=hd.get("wake_up_counts", 0),
            steps_today=hd.get("steps", 0),
            active_minutes=hd.get("active_minutes", 0),
            sedentary_period=hd.get("sedentary_period", 0),
            hrv=hd.get("heart_rate_variability"),
            resting_heart_rate=hd.get("resting_hr"),
            mood=hd.get("mood", "neutral"),
            mood_score=hd.get("mood_score", 50),
            stress_marker=analyze_stress_marker(hd),
            hydration_level=hd.get("hydration_level", "normal"),
        )
    }