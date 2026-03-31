# nodes/adaptive_model_refiner_node.py

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

class _RefinementUpdate(BaseModel):
    parameter: str
    new_value: str
    reason: Optional[str] = None


class _RefinementResponse(BaseModel):
    updates: List[_RefinementUpdate]
    summary: str


_parser = PydanticOutputParser(pydantic_object=_RefinementResponse)

_PROMPT = PromptTemplate(
    template="""
You are a meta-cognitive agent performing a weekly reflection on the user's patterns.

Current data:
- Cognitive state patterns: {cognitive_patterns}
- Burnout history: {burnout_history}
- Intervention logs: {intervention_logs}
- Task reprioritisation history: {reprioritization_logs}
- User preferences: {user_preferences}
- Last feedback summary: {last_feedback_summary}

Determine which meta-parameters of the agent's behaviour should be adjusted.

Meta-parameters:
- intervention_aggressiveness (low | medium | high)
- notification_filtering_level (conservative | balanced | aggressive)
- schedule_rigidity (flexible | semi-flexible | rigid)
- burnout_sensitivity (low | medium | high)

For each update provide: parameter, new_value, reason.
Also provide a concise summary of the overall refinement rationale.

{format_instructions}
""",
    input_variables=[
        "cognitive_patterns", "burnout_history", "intervention_logs",
        "reprioritization_logs", "user_preferences", "last_feedback_summary",
    ],
    partial_variables={"format_instructions": _parser.get_format_instructions()},
)


# ---------------------------------------------------------------------------
# Node
# ---------------------------------------------------------------------------

def adaptive_model_refiner(state: AgentState) -> Dict[str, Any]:
    log.info("adaptive_model_refiner.start", user_id=state.user_id)

    prompt_str = _PROMPT.format(
        cognitive_patterns=str(state.cognitive_state.model_dump()),
        burnout_history=str(state.burnout_status or "None"),
        intervention_logs=str(state.micro_interventions or "None"),
        reprioritization_logs=str(state.last_reprioritization or "None"),
        user_preferences=str(state.user_preferences.model_dump()),
        last_feedback_summary=state.last_feedback_summary or "None",
    )

    try:
        response = llm_service.invoke(
            prompt=prompt_str,
            node_name="AdaptiveModelRefiner",
            user_id=state.user_id,
        )
        parsed: _RefinementResponse = _parser.parse(response.content)
    except Exception as exc:
        log.error("adaptive_model_refiner.parse_failed", error=str(exc))
        return {}

    profile    = dict(state.model_refinement_profile)
    refinement_log: List[Dict] = []
    activities = list(state.recent_activities)

    for update in parsed.updates:
        old_value = profile.get(update.parameter, "Not set")
        profile[update.parameter] = update.new_value
        refinement_log.append({
            "parameter": update.parameter,
            "old_value": old_value,
            "new_value": update.new_value,
            "reason":    update.reason,
        })
        ts = datetime.now(timezone.utc).isoformat()
        activities.append(
            f"[{ts}] Model refinement: '{update.parameter}' "
            f"'{old_value}' → '{update.new_value}' "
            f"(Reason: {update.reason})"
        )

    log.info("adaptive_model_refiner.done", user_id=state.user_id,
             updates=len(refinement_log))

    return {
        "model_refinement_profile": profile,
        "last_model_refinement_summary": parsed.summary,
        "last_model_refinement_updates": refinement_log,
        "recent_activities": activities,
        "last_updated": datetime.now(timezone.utc).isoformat(),
    }