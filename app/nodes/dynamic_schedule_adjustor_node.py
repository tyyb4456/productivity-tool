from state import AgentStateDict
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Dict

from langchain.prompts import PromptTemplate
from langchain.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field
from langchain_google_genai import ChatGoogleGenerativeAI
from dotenv import load_dotenv

load_dotenv()

llm = ChatGoogleGenerativeAI(model='gemini-2.0-flash')


# 🌟 Output Schema
class Adjustment(BaseModel):
    item_id: str = Field(..., description="ID of the task or event")
    item_type: str = Field(..., description="task | event")
    suggested_status: str = Field(
        ..., description="prioritize | reschedule | defer | cancel"
    )
    new_start_time: Optional[str] = Field(
        None, description="New start time (ISO 8601) if rescheduled"
    )
    new_end_time: Optional[str] = Field(
        None, description="New end time (ISO 8601) if rescheduled"
    )
    reason: Optional[str] = Field(None, description="Rationale for the adjustment")


class ScheduleAdjustmentResponse(BaseModel):
    adjustments: List[Adjustment]
    active_focus_block: Optional[bool] = Field(
        None, description="Is there an active focus block?"
    )
    muted_channels: Optional[List[str]] = Field(
        None, description="List of muted channels during this adjustment"
    )


# ✅ Initialize Parser
parser = PydanticOutputParser(pydantic_object=ScheduleAdjustmentResponse)


# 🌟 Prompt Template
prompt = PromptTemplate(
    template="""You are ZenMaster, a hyper-adaptive personal productivity agent.
Your goal is to **optimize the user's day** for both productivity and wellbeing by adjusting their tasks and calendar events intelligently.

---

🧠 **Context:**
- Cognitive load: {cognitive_load}
- Focus level: {focus_level}
- Stress level: {stress_level}
- Burnout risk: {burnout_risk}
- Energy level: {energy_level}
- Detected Stress Signatures: {stress_signatures}

💡 **User Preferences:**
- Work Hours: {work_hours}
- Deep Work Block: {deep_work_duration} mins
- Break Interval: {break_interval} mins
- Stress Hot Zones: {stress_hot_zones}

📆 **Current Schedule:**
Tasks:
{task_list}

Events:
{event_list}

Free/Busy slots:
{busy_slots}

---

🔮 **Your Task:**
For each **task or event**, suggest one of:
- "prioritize" (focus now)
- "reschedule" (move to a better time)
- "defer" (postpone)
- "cancel" (drop)

If rescheduling, provide:
- `new_start_time` (ISO)
- `new_end_time` (ISO)

Also consider:
✅ Blocking Focus Time during user's high energy periods.
✅ Inserting Recovery Blocks after heavy cognitive loads or consecutive meetings.
✅ Avoiding overlaps and staying within preferred work hours.

Provide a **clear and concise reason** for each decision.

---

{format_instructions}
""",
    input_variables=[
        "cognitive_load", "focus_level", "stress_level", "burnout_risk",
        "energy_level", "stress_signatures", "work_hours", "deep_work_duration",
        "break_interval", "stress_hot_zones", "task_list", "event_list", "busy_slots"
    ],
    partial_variables={"format_instructions": parser.get_format_instructions()}
)


# 🎯 Node Function
def dynamic_schedule_adjustor(state: AgentStateDict) -> AgentStateDict:
    print("📅 Running Dynamic Schedule Adjustor Node...")

    if not state["tasks"] and not state["calendar_events"]:
        print("No tasks or events to adjust.")
        return state

    # 📝 Build task and event list strings
    task_list_str = "\n".join([
        f"- {task['id']}: {task['title']} | due: {task.get('due_date')} | priority: {task['priority']}"
        for task in state["tasks"]
    ]) or "None"

    event_list_str = "\n".join([
        f"- {event['id']}: {event['title']} | start: {event['start_time']} | end: {event['end_time']}"
        for event in state["calendar_events"]
    ]) or "None"

    # ⚙️ Get user preferences
    prefs = state["user_preferences"]
    work_hours = f"{prefs['preferred_work_hours']['start']} - {prefs['preferred_work_hours']['end']}"
    deep_work_duration = prefs.get("preferred_deep_work_duration", 90)
    break_interval = prefs.get("preferred_break_interval", 60)
    stress_patterns = prefs.get("stress_patterns", {})
    stress_hot_zones = ", ".join([f"{k} ({v})" for k, v in stress_patterns.items()]) or "None"

    stress_signatures = ", ".join(state["cognitive_state"].get("detected_stress_signatures", [])) or "None"

    free_busy = state.get("free_busy", "None")

    # 🧠 Format LLM prompt
    formatted_prompt = prompt.format(
        cognitive_load=state["cognitive_state"]["cognitive_load"],
        focus_level=state["cognitive_state"]["focus_level"],
        stress_level=state["cognitive_state"]["stress_level"],
        burnout_risk=str(state["cognitive_state"]["burnout_risk"]),
        energy_level=state["cognitive_state"].get("energy_level", "normal"),
        stress_signatures=stress_signatures,
        work_hours=work_hours,
        deep_work_duration=deep_work_duration,
        break_interval=break_interval,
        stress_hot_zones=stress_hot_zones,
        task_list=task_list_str,
        event_list=event_list_str,
        busy_slots=free_busy
    )

    response = llm.invoke(formatted_prompt)

    # ✅ Parse LLM response
    try:
        parsed = parser.parse(response.content)
    except Exception as e:
        print("❌ Parsing error:", e)
        print("Raw response:", response.content)
        return state

    # 🔥 Apply adjustments
    adjustments_log = []
    for adj in parsed.adjustments:
        item = None
        if adj.item_type == "task":
            item = next((t for t in state["tasks"] if t["id"] == adj.item_id), None)
        elif adj.item_type == "event":
            item = next((e for e in state["calendar_events"] if e["id"] == adj.item_id), None)

        if not item:
            continue

        if adj.suggested_status == "prioritize" and adj.item_type == "task":
            item["priority"] = "high"

        elif adj.suggested_status == "reschedule":
            if adj.new_start_time:
                item["start_time"] = adj.new_start_time
            if adj.new_end_time:
                item["end_time"] = adj.new_end_time

        elif adj.suggested_status == "defer" and adj.item_type == "task":
            due_time = item.get("due_time")
            if due_time:
                # Assuming ISO format date string
                new_due = datetime.fromisoformat(due_time) + timedelta(days=1)
                item["due_time"] = new_due.isoformat()

        elif adj.suggested_status == "cancel":
            item["status"] = "cancelled"

        # Log activity
        reason = f" - {adj.reason}" if adj.reason else ""
        state["recent_activities"].append(
            f"[{datetime.now(timezone.utc).isoformat()}] {adj.item_type.title()} '{item['title']}': {adj.suggested_status}{reason}"
        )

        adjustments_log.append(adj.dict())

    # Save adjustments summary to state
    state["last_schedule_adjustments"] = adjustments_log
    state["active_focus_block"] = parsed.active_focus_block
    state["muted_channels"] = parsed.muted_channels

    print("\n\n-----------------------------------\n\n")
    print('Dynamic Schedule Adjustments:', adjustments_log)
    print("\n\n-----------------------------------\n\n")

    state["last_updated"] = datetime.now(timezone.utc).isoformat()
    return state
