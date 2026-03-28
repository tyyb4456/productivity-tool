# models/task.py

from __future__ import annotations
from typing import List, Optional
from pydantic import BaseModel, Field


class Task(BaseModel):
    """A task from Todoist or any integrated task manager."""

    id: str
    title: str
    description: str = ""
    due_date: Optional[str] = None                    # ISO 8601 string
    priority: str = Field(
        default="normal",
        pattern="^(low|normal|high|urgent)$",
    )
    status: str = Field(
        default="pending",
        pattern="^(pending|in_progress|completed|deferred|cancelled)$",
    )
    source: str = "unknown"
    tags: List[str] = Field(default_factory=list)
    estimated_duration_minutes: Optional[int] = Field(default=None, ge=1)

    # Enriched by agent nodes
    last_adjustment_reason: Optional[str] = None
    location: Optional[str] = None