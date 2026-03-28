# app/nodes/information_flow_filter_node.py

from state import AgentStateDict
from datetime import datetime
from typing import List, Optional, Dict

from langchain.prompts import PromptTemplate
from langchain.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field

from langchain_google_genai import ChatGoogleGenerativeAI
from dotenv import load_dotenv

load_dotenv()

llm = ChatGoogleGenerativeAI(model='gemini-2.0-flash')


# 🌟 Output Schema
class NotificationDecision(BaseModel):
    notification: str = Field(..., description="The content/summary of the notification.")
    action: str = Field(..., description="urgent | batch | ignore | mute")
    reason: Optional[str] = Field(None, description="Reason for this decision")


class NotificationFilterResponse(BaseModel):
    decisions: List[NotificationDecision]


# ✅ Parser
parser = PydanticOutputParser(pydantic_object=NotificationFilterResponse)


# 🌟 Prompt Template
prompt = PromptTemplate(
    template="""
You are ZenMaster's Information Flow Filter – an advanced focus management system.

---

🧠 **User Context:**
- Cognitive load: {cognitive_load}
- Focus level: {focus_level}
- Stress level: {stress_level}
- Burnout risk: {burnout_risk}
- Detected Stress Signatures: {stress_signatures}
- Current Focus Mode: {focus_mode}
- Active Focus Block: {active_focus_block}

📨 **Incoming Notifications:**
{notification_list}

---

🎯 **Your Task:**
For each notification:
1. Analyze importance using:
   - Keywords ("urgent", "critical")
   - Sender priority (e.g., manager/team lead)
2. Consider user state:
   - Suppress interruptions during Focus Mode or Active Focus Block.
   - If stress or burnout risk is high, minimize low-importance notifications.
3. Decide action:
   - **urgent** → Notify immediately
   - **batch** → Hold for next "Catch-up" slot
   - **ignore** → Suppress completely
   - **mute** → Temporarily mute sender/channel/app (e.g., Slack, Teams)

📝 Provide a clear reason for each decision.

---

{format_instructions}
""",
    input_variables=[
        "cognitive_load", "focus_level", "stress_level", "burnout_risk",
        "stress_signatures", "focus_mode", "active_focus_block", "notification_list"
    ],
    partial_variables={"format_instructions": parser.get_format_instructions()}
)


# 🎯 Node Function
def information_flow_filter(state: AgentStateDict) -> AgentStateDict:
    print("🔔 Running Information Flow Filter Node...")

    if not state["pending_notifications"]:
        print("No notifications to filter.")
        return state

    notification_list_str = "\n".join([
        f"- {notif}" for notif in state["pending_notifications"]
    ])

    # 🧠 Context Inputs
    stress_signatures = ", ".join(state["cognitive_state"].get("detected_stress_signatures", [])) or "None"
    focus_mode = "Active" if state["cognitive_state"].get("in_focus_mode", False) else "Inactive"

    active_focus_block = "Yes" if state.get("active_focus_block", False) else "No"

    # 📝 Format Prompt
    formatted_prompt = prompt.format(
        cognitive_load=state["cognitive_state"].get("cognitive_load", "unknown"),
        focus_level=state["cognitive_state"].get("focus_level", "unknown"),
        stress_level=state["cognitive_state"].get("stress_level", "unknown"),
        burnout_risk=state["cognitive_state"].get("burnout_risk", "low"),
        stress_signatures=stress_signatures,
        focus_mode=focus_mode,
        active_focus_block=active_focus_block,
        notification_list=notification_list_str
    )

    # 🔥 Invoke LLM
    response = llm.invoke(formatted_prompt)

    # ✅ Parse Output
    try:
        parsed = parser.parse(response.content)
    except Exception as e:
        print("❌ Parsing error:", e)
        print("Raw response:", response.content)
        return state  # Fallback: pass all notifications through

    # 🔥 Apply Filtering Logic
    allowed_notifications = []
    for decision in parsed.decisions:
        if decision.action == "urgent":
            allowed_notifications.append(decision.notification)
            state["recent_activities"].append(
                f"[{datetime.utcnow().isoformat()}] Urgent notification delivered: '{decision.notification}' "
                f"({decision.reason})"
            )
        elif decision.action == "batch":
            state["recent_activities"].append(
                f"[{datetime.utcnow().isoformat()}] Batched notification: '{decision.notification}' "
                f"({decision.reason})"
            )
        elif decision.action == "ignore":
            state["recent_activities"].append(
                f"[{datetime.utcnow().isoformat()}] Ignored notification: '{decision.notification}' "
                f"({decision.reason})"
            )
        elif decision.action == "mute":
            # 📴 Automatically mute the app/channel until focus block ends
            state["recent_activities"].append(
                f"[{datetime.utcnow().isoformat()}] Muted source of '{decision.notification}' temporarily "
                f"({decision.reason})"
            )
            muted_source = decision.notification.split(":")[0]  # crude extract (e.g., "Slack", "Email")
            if muted_source not in state["cognitive_state"].get("muted_channels", []):
                state["cognitive_state"].setdefault("muted_channels", []).append(muted_source)

    # ✅ Update pending notifications with only those allowed to pass through
    state["pending_notifications"] = allowed_notifications
    state["last_updated"] = datetime.utcnow().isoformat()

    return state
