# core/logging.py
#
# Call configure_logging() once at app startup (main.py / FastAPI lifespan).
# After that, every module uses:
#
#   import structlog
#   log = structlog.get_logger(__name__)
#   log.info("event.name", key=value, ...)
#
# In development: pretty coloured output.
# In production (LOG_FORMAT=json): JSON lines readable by Datadog / Grafana Loki.

from __future__ import annotations

import logging
import os
import sys

import structlog


def configure_logging() -> None:
    log_level  = os.getenv("LOG_LEVEL",  "INFO").upper()
    log_format = os.getenv("LOG_FORMAT", "pretty")   # "pretty" | "json"

    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]

    if log_format == "json":
        processors = shared_processors + [
            structlog.processors.dict_tracebacks,
            structlog.processors.JSONRenderer(),
        ]
        formatter = structlog.stdlib.ProcessorFormatter(
            processor=structlog.processors.JSONRenderer(),
            foreign_pre_chain=shared_processors,
        )
    else:
        processors = shared_processors + [
            structlog.dev.ConsoleRenderer(colors=True),
        ]
        formatter = structlog.stdlib.ProcessorFormatter(
            processor=structlog.dev.ConsoleRenderer(colors=True),
            foreign_pre_chain=shared_processors,
        )

    structlog.configure(
        processors=processors,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(getattr(logging, log_level, logging.INFO))

    # Quiet noisy libraries
    for noisy in ("httpx", "httpcore", "google.auth", "urllib3"):
        logging.getLogger(noisy).setLevel(logging.WARNING)