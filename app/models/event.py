# models/event.py

from typing import TypedDict, List


class CalendarEventDict(TypedDict):
    id: str  # Unique identifier
    title: str  # Title of the event
    start_time: str  # ISO 8601 format
    end_time: str  # ISO 8601 format
    source: str  # e.g., Google Calendar, Outlook
    location: str  # Event location
    description: str  # Event description
    attendees: List[str]  # List of attendees
    is_meeting: bool  # True if it’s a meeting
    duration_minutes: float  # Duration in minutes
    is_recurring: bool  # True if the event is recurring
    status: str  # tentative | confirmed | cancelled
    last_adjustment_reason: str  # Reason for last adjustment
    last_adjustment_time: str  # ISO 8601 format of last adjustment
    priority: str  # low | medium | high
    reminders: List[str]  # List of reminders set for the event