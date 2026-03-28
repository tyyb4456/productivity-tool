# app/state.py

import json
from typing import TypedDict, List, Dict, Any
from datetime import datetime

from models.cognitive import CognitiveStateDict, create_default_cognitive_state
from models.event import CalendarEventDict
from models.health import HealthDataDict, create_default_health_data
from models.note import NoteDict
from models.tesk import TaskDict
from models.communicate import CommunicationInsightDict
from models.preference import UserPreferencesDict, create_default_user_preferences
from models.trend import TrendDataDict, create_default_trend_data
from models.assessment import CognitiveAssessmentSnapshotDict

class AgentStateDict(TypedDict):
    user_id: str
    calendar_events: List[CalendarEventDict]
    free_busy: Dict[str, Any]
    tasks: List[TaskDict]
    notes: List[NoteDict]
    communication_insight: CommunicationInsightDict
    health_data: HealthDataDict
    cognitive_state: CognitiveStateDict
    alerts: List[str]
    recent_activities: List[str]
    last_updated: str  # ISO 8601 string
    recent_communication_messages: List[str]
    trend_data: TrendDataDict
    burnout_status: Dict[str, Any]
    schedule_adjustment_required: bool
    wellbeing_reminder_required: bool
    pending_user_decisions: Dict[str, Any]
    last_reprioritization: List[Dict[str, Any]]
    last_schedule_adjustments: List[Dict[str, Any]]
    micro_interventions: List[Dict[str, Any]]
    next_action_suggestion: str
    next_action_params: Dict[str, Any]
    user_feedback_prompt: str
    last_feedback_summary: str
    generated_reminders: List[Dict[str, Any]]
    pending_notifications: List[str]
    last_model_refinement_summary: str
    last_model_refinement_updates: List[Dict[str, Any]]
    assessment_history: List[CognitiveAssessmentSnapshotDict]
    user_preferences: UserPreferencesDict
    active_focus_block: bool
    muted_channels: List[str]
    current_activity: str
    user_location: str
    recent_feedback: str
    active_focus_session: Dict[str, Any]
    last_cognitive_assessment: Dict[str, Any]
    last_information_filter_decisions: List[Dict[str, Any]]
    active_reminders: List[Dict[str, Any]]
    model_refinement_profile: Dict[str, Any]
    last_calendar_blocks: List[Dict[str, Any]]


def create_default_agent_state(user_id: str) -> AgentStateDict:
    return AgentStateDict(
        user_id=user_id,
        calendar_events=[],
        free_busy={},
        tasks=[],
        notes=[],
        communication_insight=CommunicationInsightDict(
            message_volume=0,
            avg_message_length=0,
            late_night_activity=False,
            sentiment_score=0.0,
            sentiment_trend="neutral",
            source="N/A"
        ),
        health_data=create_default_health_data(),
        cognitive_state=create_default_cognitive_state(),
        alerts=[],
        recent_activities=[],
        last_updated=datetime.utcnow().isoformat(),
        recent_communication_messages=[],
        trend_data=create_default_trend_data(),
        burnout_status={},
        schedule_adjustment_required=False,
        wellbeing_reminder_required=False,
        pending_user_decisions={},
        last_reprioritization=[],
        last_schedule_adjustments=[],
        micro_interventions=[],
        next_action_suggestion="",
        next_action_params={},
        user_feedback_prompt="",
        last_feedback_summary="",
        generated_reminders=[],
        pending_notifications=[],
        last_model_refinement_summary="",
        last_model_refinement_updates=[],
        assessment_history=[],
        user_preferences=create_default_user_preferences(),
        active_focus_block=False,
        muted_channels=[],
        current_activity="",
        user_location="",
        recent_feedback="",
        active_focus_session={},
        last_cognitive_assessment={},
        last_information_filter_decisions=[],
        active_reminders=[],
        model_refinement_profile={},
        last_calendar_blocks=[]
    )


# 🌟 State Persistence
STATE_FILE = "agent_state.json"


def load_initial_state() -> AgentStateDict:
    try:
        with open(STATE_FILE, "r") as f:
            data = json.load(f)
        print("📦 Loaded existing AgentState.")
        return data  # Already a dict
    except (FileNotFoundError, json.JSONDecodeError):
        print("🆕 No saved state found. Initializing fresh AgentState.")
        return create_default_agent_state()


def save_state(state: AgentStateDict):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)
    print("💾 AgentState saved.")
