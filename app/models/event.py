# models/event.py

from __future__ import annotations
from typing import List, Optional
from pydantic import BaseModel, Field


class CalendarEvent(BaseModel):
    """A calendar event from Google Calendar or similar."""

    id: str
    title: str
    start_time: str                                   # ISO 8601
    end_time: str                                     # ISO 8601
    source: str = "unknown"

    location: Optional[str] = None
    description: Optional[str] = None
    attendees: List[str] = Field(default_factory=list)

    is_meeting: bool = False
    duration_minutes: Optional[float] = None
    is_recurring: bool = False

    status: str = Field(
        default="confirmed",
        pattern="^(tentative|confirmed|cancelled)$",
    )
    priority: str = Field(
        default="normal",
        pattern="^(low|normal|high)$",
    )

    # Enriched by DynamicScheduleAdjustor
    last_adjustment_reason: Optional[str] = None
    last_adjustment_time: Optional[str] = None
    reminders: List[str] = Field(default_factory=list)