# api/routes/websocket.py
#
# WebSocket endpoint that streams live agent updates to the frontend.
#
# Protocol:
#   Client connects to  ws://.../ws/{user_id}?token=<jwt>
#   Server sends JSON frames of shape:
#       { "type": "activity",  "data": "<log line>" }
#       { "type": "state",     "data": { ...summary dict... } }
#       { "type": "ping" }
#
#   Client can send:
#       { "type": "ping" }   → server echoes pong
#
# Architecture:
#   A per-user asyncio.Queue lives in _user_queues.
#   Graph runs (triggered via API or Celery) call publish_update(user_id, msg)
#   to push messages onto the queue.
#   The WebSocket handler drains the queue and forwards to the browser.

from __future__ import annotations

import asyncio
import json
from collections import defaultdict
from typing import Any, Dict

import jwt
import structlog
from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect, status

import os
_JWT_SECRET    = os.getenv("JWT_SECRET", "change-me-in-production")
_JWT_ALGORITHM = "HS256"

log    = structlog.get_logger(__name__)
router = APIRouter(tags=["websocket"])

# user_id → asyncio.Queue  (created on first connection, shared across tabs)
_user_queues: Dict[str, asyncio.Queue] = defaultdict(asyncio.Queue)


# ---------------------------------------------------------------------------
# Public helper — called by graph runs to push updates
# ---------------------------------------------------------------------------

async def publish_update(user_id: str, message: Dict[str, Any]) -> None:
    """
    Push a message onto the user's WebSocket queue.
    Safe to call from graph nodes or Celery callbacks.
    """
    await _user_queues[user_id].put(message)


def publish_update_sync(user_id: str, message: Dict[str, Any]) -> None:
    """
    Synchronous version for Celery tasks running outside an event loop.
    Creates a temporary loop if needed.
    """
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.ensure_future(publish_update(user_id, message))
        else:
            loop.run_until_complete(publish_update(user_id, message))
    except RuntimeError:
        asyncio.run(publish_update(user_id, message))


# ---------------------------------------------------------------------------
# WebSocket endpoint
# ---------------------------------------------------------------------------

@router.websocket("/ws/{user_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    user_id:   str,
    token:     str = Query(..., description="JWT auth token"),
) -> None:
    """Stream live agent updates to the frontend."""

    # --- Auth ---
    try:
        payload = jwt.decode(token, _JWT_SECRET, algorithms=[_JWT_ALGORITHM])
        token_user_id: str = payload["sub"]
    except jwt.InvalidTokenError as exc:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        log.warning("ws.auth_failed", user_id=user_id, error=str(exc))
        return

    # Prevent one user from subscribing to another user's stream
    if token_user_id != user_id:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        log.warning("ws.user_mismatch",
                    token_user=token_user_id, path_user=user_id)
        return

    await websocket.accept()
    log.info("ws.connected", user_id=user_id)

    queue = _user_queues[user_id]

    # Send initial ping so the client knows the connection is live
    await websocket.send_text(json.dumps({"type": "ping"}))

    # Run two concurrent tasks:
    #   _sender  — drains the queue and forwards to the browser
    #   _receiver — handles incoming client messages (pings)
    sender_task   = asyncio.create_task(_sender(websocket, queue, user_id))
    receiver_task = asyncio.create_task(_receiver(websocket, user_id))

    try:
        # Exit as soon as either task finishes (disconnect or error)
        done, pending = await asyncio.wait(
            [sender_task, receiver_task],
            return_when=asyncio.FIRST_COMPLETED,
        )
        for task in pending:
            task.cancel()
    except Exception as exc:
        log.warning("ws.error", user_id=user_id, error=str(exc))
    finally:
        log.info("ws.disconnected", user_id=user_id)


# ---------------------------------------------------------------------------
# Internal coroutines
# ---------------------------------------------------------------------------

async def _sender(
    websocket: WebSocket,
    queue:     asyncio.Queue,
    user_id:   str,
) -> None:
    """Drain the queue and forward every message to the WebSocket."""
    while True:
        try:
            # 30-second timeout so we can send keepalive pings
            msg = await asyncio.wait_for(queue.get(), timeout=30.0)
            await websocket.send_text(json.dumps(msg))
            queue.task_done()
        except asyncio.TimeoutError:
            # Send keepalive ping
            try:
                await websocket.send_text(json.dumps({"type": "ping"}))
            except WebSocketDisconnect:
                return
        except WebSocketDisconnect:
            return
        except Exception as exc:
            log.warning("ws.sender_error", user_id=user_id, error=str(exc))
            return


async def _receiver(websocket: WebSocket, user_id: str) -> None:
    """Handle incoming messages from the client."""
    while True:
        try:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue

            if msg.get("type") == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))

        except WebSocketDisconnect:
            return
        except Exception as exc:
            log.warning("ws.receiver_error", user_id=user_id, error=str(exc))
            return