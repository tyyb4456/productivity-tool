# api/dependencies.py
#
# FastAPI dependency injection for auth and state loading.
# Every protected route calls get_current_user() to resolve the user_id
# from a JWT, then passes it to get_state() to hydrate AgentState.

from __future__ import annotations

import os
from typing import Annotated

import jwt
import structlog
from fastapi import Depends, Header, HTTPException, status

from services.state_store import state_store
from state import AgentState

log = structlog.get_logger(__name__)

_JWT_SECRET    = os.getenv("JWT_SECRET", "change-me-in-production")
_JWT_ALGORITHM = "HS256"


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

async def get_current_user(
    authorization: Annotated[str | None, Header()] = None,
) -> str:
    """
    Resolve user_id from Bearer JWT.
    Returns the user_id string on success, raises 401 on failure.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Authorization header.",
        )
    token = authorization.removeprefix("Bearer ").strip()
    try:
        payload = jwt.decode(token, _JWT_SECRET, algorithms=[_JWT_ALGORITHM])
        user_id: str = payload["sub"]
        return user_id
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired.")
    except jwt.InvalidTokenError as exc:
        raise HTTPException(status_code=401, detail=f"Invalid token: {exc}")


CurrentUser = Annotated[str, Depends(get_current_user)]


# ---------------------------------------------------------------------------
# State hydration
# ---------------------------------------------------------------------------

async def get_state(user_id: CurrentUser) -> AgentState:
    """Load AgentState for the current user from the state store."""
    return await state_store.load(user_id)


CurrentState = Annotated[AgentState, Depends(get_state)]