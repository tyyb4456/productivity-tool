# nodes/information_flow_filter_node.py

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

class _NotificationDecision(BaseModel):
    notification: str
    action: str = Field(..., pattern="^(urgent|batch|ignore|mute)$")
    reason: Optional[str] = None


class _NotificationFilterResponse(BaseModel):
    decisions: List[_NotificationDecision]


_parser = PydanticOutputParser(pydantic_object=_NotificationFilterResponse)

_PROMPT = PromptTemplate(
    template="""
You are ZenMaster's Information Flow Filter — an advanced focus management system.

🧠 User Context:
- Cognitive load: {cognitive_load}
- Focus level: {focus_level}
- Stress level: {stress_level}
- Burnout risk: {burnout_risk}
- Detected stress signatures: {stress_signatures}
- Focus mode active: {focus_mode}
- Active focus block: {active_focus_block}

📨 Incoming Notifications:
{notification_list}

For each notification decide:
- urgent  → notify immediately
- batch   → hold for next catch-up slot
- ignore  → suppress completely
- mute    → temporarily mute sender/channel/app

Suppress interruptions during Focus Mode or active Focus Block.
If stress or burnout risk is high, minimise low-importance notifications.
Provide a clear reason for each decision.

{format_instructions}
""",
    input_variables=[
        "cognitive_load", "focus_level", "stress_level", "burnout_risk",
        "stress_signatures", "focus_mode", "active_focus_block", "notification_list",
    ],
    partial_variables={"format_instructions": _parser.get_format_instructions()},
)


# ---------------------------------------------------------------------------
# Node
# ---------------------------------------------------------------------------

def information_flow_filter(state: AgentState) -> Dict[str, Any]:
    log.info("information_flow_filter.start", user_id=state.user_id,
             notifications=len(state.pending_notifications))

    if not state.pending_notifications:
        log.info("information_flow_filter.skip", reason="no pending notifications")
        return {}

    cog = state.cognitive_state
    stress_signatures = ", ".join(cog.detected_stress_signatures) or "None"
    focus_mode        = "Active" if cog.in_focus_mode else "Inactive"
    active_focus      = "Yes" if state.active_focus_block else "No"

    notification_list_str = "\n".join(
        f"- {n}" for n in state.pending_notifications
    )

    prompt_str = _PROMPT.format(
        cognitive_load=cog.cognitive_load,
        focus_level=cog.focus_level,
        stress_level=cog.stress_level,
        burnout_risk=str(cog.burnout_risk),
        stress_signatures=stress_signatures,
        focus_mode=focus_mode,
        active_focus_block=active_focus,
        notification_list=notification_list_str,
    )

    try:
        response = llm_service.invoke(
            prompt=prompt_str,
            node_name="InformationFlowFilter",
            user_id=state.user_id,
        )
        parsed: _NotificationFilterResponse = _parser.parse(response.content)
    except Exception as exc:
        log.error("information_flow_filter.parse_failed", error=str(exc))
        return {}

    # --- Apply decisions ---
    allowed: List[str] = []
    activities  = list(state.recent_activities)
    muted       = list(state.muted_channels)
    decisions_log: List[Dict] = []

    for decision in parsed.decisions:
        ts = datetime.now(timezone.utc).isoformat()
        decisions_log.append(decision.model_dump())

        if decision.action == "urgent":
            allowed.append(decision.notification)
            activities.append(
                f"[{ts}] Urgent notification delivered: "
                f"'{decision.notification}' ({decision.reason})"
            )
        elif decision.action == "batch":
            activities.append(
                f"[{ts}] Batched notification: "
                f"'{decision.notification}' ({decision.reason})"
            )
        elif decision.action == "ignore":
            activities.append(
                f"[{ts}] Ignored notification: "
                f"'{decision.notification}' ({decision.reason})"
            )
        elif decision.action == "mute":
            activities.append(
                f"[{ts}] Muted source of "
                f"'{decision.notification}' ({decision.reason})"
            )
            source = decision.notification.split(":")[0].strip()
            if source and source not in muted:
                muted.append(source)

    log.info("information_flow_filter.done", user_id=state.user_id,
             allowed=len(allowed), total=len(parsed.decisions))

    return {
        "pending_notifications": allowed,
        "muted_channels": muted,
        "last_information_filter_decisions": decisions_log,
        "recent_activities": activities,
        "last_updated": datetime.now(timezone.utc).isoformat(),
    }