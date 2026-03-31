# api/app.py
#
# FastAPI application factory.
#
# Run with:
#   uvicorn api.app:app --reload --port 8000
#
# Or from project root:
#   cd app && uvicorn api.app:app --reload --port 8000

from __future__ import annotations

import os
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.routes import feedback, graph, state, websocket
from core.logging import configure_logging

log = structlog.get_logger(__name__)

_ALLOWED_ORIGINS = os.getenv(
    "CORS_ORIGINS",
    "http://localhost:3000,http://localhost:5173",   # React / Vite dev servers
).split(",")


# ---------------------------------------------------------------------------
# Lifespan  (startup / shutdown)
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    log.info("zenmaster.api.starting")
    yield
    log.info("zenmaster.api.stopping")


# ---------------------------------------------------------------------------
# Application factory
# ---------------------------------------------------------------------------

def create_app() -> FastAPI:
    application = FastAPI(
        title="ZenMaster API",
        description=(
            "AI-powered productivity and wellbeing agent. "
            "Manages cognitive state, task prioritization, "
            "schedule blocking, and micro-interventions."
        ),
        version="0.3.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # --- CORS ---
    application.add_middleware(
        CORSMiddleware,
        allow_origins=_ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # --- Global exception handler ---
    @application.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        log.error("api.unhandled_exception",
                  path=str(request.url), error=str(exc))
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error."},
        )

    # --- Health check (no auth required) ---
    @application.get("/health", tags=["meta"])
    async def health() -> dict:
        return {"status": "ok", "service": "zenmaster"}

    # --- Routers ---
    application.include_router(state.router)
    application.include_router(graph.router)
    application.include_router(feedback.router)
    application.include_router(websocket.router)

    return application


# Module-level app instance — used by uvicorn
app = create_app()