# nodes/feedback_loop_node.py

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import structlog
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import PromptTemplate
from pydantic import BaseModel, Field

from services.llm_service import llm_service
from state import AgentState

log = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# LLM output schema
# ---------------------------------------------------------------------------

class _PreferenceUpdate(BaseModel):
    preference: str
    new_value: str
    reason: Optional[str] = None


class _FeedbackResponse(BaseModel):
    updates: List[_PreferenceUpdate]
    summary: str


_parser = PydanticOutputParser(pydantic_object=_FeedbackResponse)

_PROMPT = PromptTemplate(
    template="""
You are an AI assistant personalising a user's productivity and wellbeing experience.

📝 User Feedback:
{feedback_text}

📋 Current Preferences:
{current_preferences}

Analyse the feedback and suggest adjustments to:
- Task prioritisation style
- Reminder frequency / tone
- Break recommendations
- Notification filtering
- Any other relevant settings

For each adjustment specify: preference, new_value, reason.
Also provide a brief summary of how you interpreted the feedback.

{format_instructions}
""",
    input_variables=["feedback_text", "current_preferences"],
    partial_variables={"format_instructions": _parser.get_format_instructions()},
)


# ---------------------------------------------------------------------------
# Node
# ---------------------------------------------------------------------------

def feedback_loop_node(state: AgentState) -> Dict[str, Any]:
    log.info("feedback_loop_node.start", user_id=state.user_id,
             feedback_count=len(state.recent_feedback))

    if not state.recent_feedback:
        log.info("feedback_loop_node.skip", reason="no recent feedback")
        return {}

    feedback_text = "\n".join(state.recent_feedback)
    preferences_text = "\n".join(
        f"- {k}: {v}"
        for k, v in state.user_preferences.model_dump().items()
    )

    prompt_str = _PROMPT.format(
        feedback_text=feedback_text,
        current_preferences=preferences_text,
    )

    try:
        response = llm_service.invoke(
            prompt=prompt_str,
            node_name="FeedbackLoop",
            user_id=state.user_id,
        )
        parsed: _FeedbackResponse = _parser.parse(response.content)
    except Exception as exc:
        log.error("feedback_loop_node.parse_failed", error=str(exc))
        return {}

    # Apply preference updates
    prefs      = state.user_preferences.model_copy(deep=True)
    update_log: List[Dict] = []
    activities = list(state.recent_activities)

    for update in parsed.updates:
        old_value = getattr(prefs, update.preference, "Not set")
        # Only set if the field actually exists on UserPreferences
        if hasattr(prefs, update.preference):
            object.__setattr__(prefs, update.preference, update.new_value)
        else:
            # Dynamically extend preferences dict for learned fields
            prefs.__pydantic_fields_set__.add(update.preference)

        update_log.append({
            "preference": update.preference,
            "old_value":  str(old_value),
            "new_value":  update.new_value,
            "reason":     update.reason,
        })
        ts = datetime.now(timezone.utc).isoformat()
        activities.append(
            f"[{ts}] Preference '{update.preference}' changed "
            f"from '{old_value}' to '{update.new_value}' "
            f"(Reason: {update.reason})"
        )

    log.info("feedback_loop_node.done", user_id=state.user_id,
             updates=len(update_log))

    return {
        "user_preferences": prefs,
        "last_feedback_summary": parsed.summary,
        "last_feedback_updates": update_log,
        "recent_feedback": [],           # clear processed feedback
        "recent_activities": activities,
        "last_updated": datetime.now(timezone.utc).isoformat(),
    }