# app/main.py
#
# ZenMaster agent scheduler.
#
# Replaces the broken schedule + shared-state while-True loop with Celery,
# which gives us: retries, distributed workers, dead-letter queues, and a
# proper separation between periodic triggers and event-driven triggers.
#
# How to run:
#   # Start the Celery worker (in one terminal)
#   celery -A main.celery_app worker --loglevel=info
#
#   # Start the Celery beat scheduler (in another terminal)
#   celery -A main.celery_app beat --loglevel=info
#
# Requires Redis:  REDIS_URL=redis://localhost:6379/0  (set in .env)

from __future__ import annotations

import asyncio
import os
from datetime import datetime, timezone
from typing import Any, Dict

import structlog
from celery import Celery
from celery.schedules import crontab
from dotenv import load_dotenv

from core.logging import configure_logging
from graph_builder import evening_graph, morning_graph, workday_graph
from services.state_store import state_store
from state import AgentState

load_dotenv()
configure_logging()

log = structlog.get_logger(__name__)

_REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")


# ---------------------------------------------------------------------------
# Celery application
# ---------------------------------------------------------------------------

celery_app = Celery(
    "zenmaster",
    broker=_REDIS_URL,
    backend=_REDIS_URL,
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,           # re-queue on worker crash
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,  # one task at a time per worker
)

# ---------------------------------------------------------------------------
# Periodic schedule  (Celery Beat)
# ---------------------------------------------------------------------------

celery_app.conf.beat_schedule = {
    # 07:00 every day — ingest data, build context, block calendar
    "morning-routine": {
        "task": "main.run_morning_routine",
        "schedule": crontab(hour=7, minute=0),
        "args": [],
    },
    # Every hour during work hours — reprioritize, filter, remind
    "workday-loop": {
        "task": "main.run_workday_loop",
        "schedule": crontab(minute=0, hour="8-19"),
        "args": [],
    },
    # 19:00 — feedback, preferences, (weekly) meta-refinement
    "evening-routine": {
        "task": "main.run_evening_routine",
        "schedule": crontab(hour=19, minute=0),
        "args": [],
    },
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run_graph(graph, user_id: str) -> AgentState:
    """
    Load state → invoke graph → save state → return updated AgentState.
    Runs the async store calls in a fresh event loop (Celery tasks are sync).
    """
    loop = asyncio.new_event_loop()
    try:
        state = loop.run_until_complete(state_store.load(user_id))
        raw_out: Dict[str, Any] = graph.invoke(state.model_dump())

        # Merge graph output back into state
        merged = state.model_dump()
        merged.update(raw_out)
        updated_state = AgentState.model_validate(merged)

        loop.run_until_complete(state_store.save(updated_state))
        loop.run_until_complete(state_store.snapshot(updated_state))
        return updated_state
    finally:
        loop.close()


def _get_all_user_ids() -> list[str]:
    """
    Return every active user_id.
    Replace with a DB query once you have a users table.
    """
    raw = os.getenv("ZENMASTER_USER_IDS", "")
    return [uid.strip() for uid in raw.split(",") if uid.strip()]


# ---------------------------------------------------------------------------
# Periodic Celery tasks
# ---------------------------------------------------------------------------

@celery_app.task(
    name="main.run_morning_routine",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def run_morning_routine(self):
    log.info("task.morning_routine.start")
    for user_id in _get_all_user_ids():
        try:
            state = _run_graph(morning_graph, user_id)
            log.info("task.morning_routine.done", user_id=user_id,
                     cognitive_load=state.cognitive_state.cognitive_load)
        except Exception as exc:
            log.error("task.morning_routine.failed", user_id=user_id, error=str(exc))
            self.retry(exc=exc)


@celery_app.task(
    name="main.run_workday_loop",
    bind=True,
    max_retries=3,
    default_retry_delay=30,
)
def run_workday_loop(self):
    log.info("task.workday_loop.start")
    for user_id in _get_all_user_ids():
        try:
            state = _run_graph(workday_graph, user_id)
            log.info("task.workday_loop.done", user_id=user_id)
        except Exception as exc:
            log.error("task.workday_loop.failed", user_id=user_id, error=str(exc))
            self.retry(exc=exc)


@celery_app.task(
    name="main.run_evening_routine",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def run_evening_routine(self):
    log.info("task.evening_routine.start")
    for user_id in _get_all_user_ids():
        try:
            state = _run_graph(evening_graph, user_id)
            log.info("task.evening_routine.done", user_id=user_id)
        except Exception as exc:
            log.error("task.evening_routine.failed", user_id=user_id, error=str(exc))
            self.retry(exc=exc)


# ---------------------------------------------------------------------------
# Event-driven Celery tasks  (called by API layer / webhooks)
# ---------------------------------------------------------------------------

@celery_app.task(name="main.on_new_task_added", bind=True, max_retries=3)
def on_new_task_added(self, user_id: str, task_dict: Dict[str, Any]):
    """Called when a new task arrives (e.g. Todoist webhook)."""
    log.info("task.on_new_task_added", user_id=user_id)
    try:
        loop = asyncio.new_event_loop()
        state = loop.run_until_complete(state_store.load(user_id))
        loop.close()

        from models import Task
        new_task = Task.model_validate(task_dict)
        state = state.model_copy(update={"tasks": state.tasks + [new_task]})

        _run_graph(workday_graph, user_id)
    except Exception as exc:
        log.error("task.on_new_task_added.failed", user_id=user_id, error=str(exc))
        self.retry(exc=exc)


@celery_app.task(name="main.on_user_feedback_received", bind=True, max_retries=3)
def on_user_feedback_received(self, user_id: str, feedback: str):
    """Called when user submits feedback via the frontend."""
    log.info("task.on_user_feedback_received", user_id=user_id)
    try:
        loop = asyncio.new_event_loop()
        state = loop.run_until_complete(state_store.load(user_id))
        loop.close()

        state = state.model_copy(
            update={"recent_feedback": state.recent_feedback + [feedback]}
        )
        loop2 = asyncio.new_event_loop()
        loop2.run_until_complete(state_store.save(state))
        loop2.close()

        _run_graph(evening_graph, user_id)
    except Exception as exc:
        log.error("task.on_user_feedback_received.failed",
                  user_id=user_id, error=str(exc))
        self.retry(exc=exc)


@celery_app.task(name="main.on_burnout_sign_detected", bind=True, max_retries=3)
def on_burnout_sign_detected(self, user_id: str):
    """Called by a health device webhook or wearable integration."""
    log.info("task.on_burnout_sign_detected", user_id=user_id)
    try:
        _run_graph(workday_graph, user_id)
    except Exception as exc:
        log.error("task.on_burnout_sign_detected.failed",
                  user_id=user_id, error=str(exc))
        self.retry(exc=exc)