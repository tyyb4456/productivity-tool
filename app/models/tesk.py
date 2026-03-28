# models/task.py

from typing import TypedDict, List, Optional
from datetime import datetime


class TaskDict(TypedDict):
    id: str
    title: str
    description: str  # Default to empty string if not provided
    due_date: str  # ISO 8601 format string (keep as str for simplicity)
    priority: str  # low | normal | high | critical
    status: str  # pending | completed | deferred | cancelled
    source: str  # e.g., "Todoist", "GoogleTasks"
    tags: List[str]
    estimated_duration_minutes: int  # Estimated duration in minutes