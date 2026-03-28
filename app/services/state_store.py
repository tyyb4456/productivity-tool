# services/state_store.py
#
# Two-tier state persistence:
#
#   Hot  (Redis)    — current session state for a user; expires after 24 h.
#                     Fast reads/writes during workday cycles.
#
#   Cold (Postgres) — full state snapshots, versioned, never deleted.
#                     Used for assessment history, model refinement, weekly
#                     rollups, and disaster recovery.
#
# Both tiers are optional and gracefully degrade:
#   - No Redis  → warn + use in-memory dict (single-process only).
#   - No Postgres → warn + skip cold persistence.
#
# Usage
# -----
#   from services.state_store import state_store
#
#   state = await state_store.load(user_id)     # Redis → Postgres → default
#   state = await state_store.save(state)       # Redis (always) + Postgres (snapshot)
#   await state_store.snapshot(state)           # Postgres only (versioned)

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Optional

import structlog

from state import AgentState

log = structlog.get_logger(__name__)

_REDIS_URL    = os.getenv("REDIS_URL",    "redis://localhost:6379/0")
_DATABASE_URL = os.getenv("DATABASE_URL", "")
_HOT_TTL_SEC  = int(os.getenv("STATE_HOT_TTL_SEC", "86400"))   # 24 h


# ---------------------------------------------------------------------------
# StateStore
# ---------------------------------------------------------------------------

class StateStore:

    def __init__(self) -> None:
        self._redis  = self._init_redis()
        self._db     = self._init_db()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def load(self, user_id: str) -> AgentState:
        """
        Load state for a user.
        Priority: Redis hot state → Postgres latest snapshot → fresh default.
        """
        # 1. Redis
        state = await self._load_from_redis(user_id)
        if state:
            log.debug("state.loaded_from_redis", user_id=user_id)
            return state

        # 2. Postgres
        state = await self._load_from_db(user_id)
        if state:
            log.debug("state.loaded_from_db", user_id=user_id)
            await self._save_to_redis(state)        # warm the cache
            return state

        # 3. Fresh
        log.info("state.created_fresh", user_id=user_id)
        return AgentState(user_id=user_id)

    async def save(self, state: AgentState) -> AgentState:
        """
        Write to Redis (always) and return the state untouched.
        Call snapshot() separately for versioned Postgres writes.
        """
        state = state.touch()
        await self._save_to_redis(state)
        return state

    async def snapshot(self, state: AgentState) -> None:
        """
        Write a versioned snapshot to Postgres.
        Call this at the end of each graph run.
        """
        await self._save_to_db(state)

    async def delete(self, user_id: str) -> None:
        """Delete hot state (GDPR / account deletion)."""
        if self._redis:
            try:
                self._redis.delete(self._redis_key(user_id))
            except Exception as exc:
                log.warning("state.redis_delete_failed", user_id=user_id, error=str(exc))

    # ------------------------------------------------------------------
    # Redis helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _redis_key(user_id: str) -> str:
        return f"zenmaster:state:{user_id}"

    def _init_redis(self):
        try:
            import redis
            client = redis.from_url(_REDIS_URL, decode_responses=True)
            client.ping()
            log.info("state_store.redis_connected", url=_REDIS_URL)
            return client
        except Exception as exc:
            log.warning(
                "state_store.redis_unavailable",
                error=str(exc),
                fallback="in-memory (single-process only)",
            )
            return None

    async def _load_from_redis(self, user_id: str) -> Optional[AgentState]:
        if not self._redis:
            return None
        try:
            raw = self._redis.get(self._redis_key(user_id))
            if raw:
                return AgentState.model_validate_json(raw)
        except Exception as exc:
            log.warning("state.redis_load_failed", user_id=user_id, error=str(exc))
        return None

    async def _save_to_redis(self, state: AgentState) -> None:
        if not self._redis:
            return
        try:
            self._redis.setex(
                self._redis_key(state.user_id),
                _HOT_TTL_SEC,
                state.model_dump_json(),
            )
        except Exception as exc:
            log.warning("state.redis_save_failed", user_id=state.user_id, error=str(exc))

    # ------------------------------------------------------------------
    # Postgres helpers
    # ------------------------------------------------------------------

    def _init_db(self):
        if not _DATABASE_URL:
            log.warning(
                "state_store.db_unavailable",
                reason="DATABASE_URL not set",
                fallback="cold persistence disabled",
            )
            return None
        try:
            import psycopg2
            conn = psycopg2.connect(_DATABASE_URL)
            self._ensure_schema(conn)
            log.info("state_store.db_connected")
            return conn
        except Exception as exc:
            log.warning("state_store.db_unavailable", error=str(exc))
            return None

    @staticmethod
    def _ensure_schema(conn) -> None:
        """Create the state snapshots table if it doesn't exist."""
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS agent_state_snapshots (
                    id          BIGSERIAL PRIMARY KEY,
                    user_id     TEXT        NOT NULL,
                    version     INT         NOT NULL DEFAULT 1,
                    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    payload     JSONB       NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_snapshots_user_created
                    ON agent_state_snapshots (user_id, created_at DESC);
            """)
        conn.commit()

    async def _load_from_db(self, user_id: str) -> Optional[AgentState]:
        if not self._db:
            return None
        try:
            with self._db.cursor() as cur:
                cur.execute(
                    """
                    SELECT payload FROM agent_state_snapshots
                    WHERE user_id = %s
                    ORDER BY created_at DESC
                    LIMIT 1
                    """,
                    (user_id,),
                )
                row = cur.fetchone()
            if row:
                return AgentState.model_validate(row[0])
        except Exception as exc:
            log.warning("state.db_load_failed", user_id=user_id, error=str(exc))
        return None

    async def _save_to_db(self, state: AgentState) -> None:
        if not self._db:
            return
        try:
            with self._db.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO agent_state_snapshots (user_id, payload)
                    VALUES (%s, %s)
                    """,
                    (state.user_id, json.dumps(state.model_dump())),
                )
            self._db.commit()
            log.debug("state.db_snapshot_saved", user_id=state.user_id)
        except Exception as exc:
            log.warning("state.db_save_failed", user_id=state.user_id, error=str(exc))
            try:
                self._db.rollback()
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

state_store = StateStore()