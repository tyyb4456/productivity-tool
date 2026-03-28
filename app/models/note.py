# models/note.py

from typing import TypedDict, List
from datetime import datetime


class NoteDict(TypedDict):
    id: str  # Unique identifier for the note
    title: str  # Title of the note
    content: str  # Content/body of the note
    created_at: str  # ISO 8601 datetime string
    last_modified: str  # ISO 8601 datetime string
    tags: List[str]  # Tags/labels for categorization
    source: str  # Origin/source of the note (e.g., "user", "imported")
    is_archived: bool  # True if the note is archived
    is_pinned: bool  # True if the note is pinned for quick access
    priority: str  # low | medium | high
    attachments: List[str]  # List of attachment identifiers (e.g., file paths, URLs)
    related_events: List[str]  # List of related event IDs
    related_tasks: List[str]  # List of related task IDs
