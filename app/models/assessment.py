# models/assessment.py

from typing import TypedDict, Dict, Any
from datetime import datetime
from models.cognitive import CognitiveStateDict


class CognitiveAssessmentSnapshotDict(TypedDict):
    timestamp: str  # ISO formatted datetime string
    inputs: Dict[str, Any]  # Raw inputs observed at assessment time
    assessment: CognitiveStateDict  # Cognitive state at this snapshot
