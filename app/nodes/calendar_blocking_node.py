# nodes/calendar_blocking_node.py

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

import structlog

from models import CalendarEvent
from state import AgentState

log = structlog.get_logger(__name__)


def calendar_blocking_node(state: AgentState) -> Dict[str, Any]:
    log.info("calendar_blocking_node.start", user_id=state.user_id)

    prefs = state.user_preferences
    work_start_str   = prefs.preferred_work_hours.get("start", "09:00")
    work_end_str     = prefs.preferred_work_hours.get("end",   "17:00")
    deep_work_mins   = prefs.preferred_deep_work_duration
    break_duration   = 15       # minutes — fixed, could become a preference

    today          = datetime.now(timezone.utc).date()
    work_start     = datetime.strptime(
        f"{today}T{work_start_str}", "%Y-%m-%dT%H:%M"
    ).replace(tzinfo=timezone.utc)
    work_end       = datetime.strptime(
        f"{today}T{work_end_str}", "%Y-%m-%dT%H:%M"
    ).replace(tzinfo=timezone.utc)

    # Build a list of (start, end) busy intervals from existing events today
    existing: List[tuple] = []
    for ev in state.calendar_events:
        try:
            s = datetime.fromisoformat(ev.start_time)
            e = datetime.fromisoformat(ev.end_time)
            if s.date() == today:
                existing.append((s, e))
        except (ValueError, AttributeError):
            pass

    def _is_free(start: datetime, end: datetime) -> bool:
        return all(start >= e or end <= s for s, e in existing)

    # Sort pending tasks by priority (high first)
    _priority_order = {"urgent": 0, "high": 1, "normal": 2, "medium": 2, "low": 3}
    pending = sorted(
        [tk for tk in state.tasks if tk.status != "completed"],
        key=lambda tk: _priority_order.get(tk.priority, 2),
    )

    new_blocks: List[Dict] = []
    current = work_start

    for task in pending:
        block_end = current + timedelta(minutes=deep_work_mins)
        if block_end > work_end:
            break

        # Find first free slot (skip 15 min at a time if occupied)
        attempts = 0
        while not _is_free(current, block_end) and attempts < 20:
            current   += timedelta(minutes=15)
            block_end  = current + timedelta(minutes=deep_work_mins)
            attempts  += 1

        if block_end > work_end:
            break

        block = {
            "title": f"Focus Block: {task.title}",
            "start_time": current.isoformat(),
            "end_time":   block_end.isoformat(),
        }
        new_blocks.append(block)
        existing.append((current, block_end))
        log.info("calendar_blocking_node.focus_block",
                 task=task.title, start=current.isoformat())
        current = block_end

        # Insert break after each focus block
        break_end = current + timedelta(minutes=break_duration)
        if break_end <= work_end and _is_free(current, break_end):
            brk = {
                "title":      "Break: Stretch & Hydrate",
                "start_time": current.isoformat(),
                "end_time":   break_end.isoformat(),
            }
            new_blocks.append(brk)
            existing.append((current, break_end))
            current = break_end

    # Add wind-down block if burnout risk is active
    if state.cognitive_state.burnout_risk:
        wind_start = work_end - timedelta(minutes=30)
        if _is_free(wind_start, work_end):
            new_blocks.append({
                "title":      "Wind-down: Mindfulness / Journaling",
                "start_time": wind_start.isoformat(),
                "end_time":   work_end.isoformat(),
            })
            log.info("calendar_blocking_node.wind_down_added")

    # Merge into calendar_events as CalendarEvent objects
    merged_events = list(state.calendar_events)
    for blk in new_blocks:
        merged_events.append(CalendarEvent(
            id=f"zenmaster-block-{blk['start_time']}",
            title=blk["title"],
            start_time=blk["start_time"],
            end_time=blk["end_time"],
            source="ZenMaster",
            status="confirmed",
        ))

    ts = datetime.now(timezone.utc).isoformat()
    activities = list(state.recent_activities)
    activities.append(f"[{ts}] Calendar blocked {len(new_blocks)} new events.")

    log.info("calendar_blocking_node.done", user_id=state.user_id,
             blocks=len(new_blocks))

    return {
        "calendar_events": merged_events,
        "last_calendar_blocks": new_blocks,
        "recent_activities": activities,
        "last_updated": ts,
    }