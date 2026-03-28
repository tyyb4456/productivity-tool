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
class Reminder(BaseModel):
    reminder_id: str = Field(..., description="Unique ID for the reminder")
    type: str = Field(..., description="task | wellbeing | focus | hydration | sleep | break")
    message: str = Field(..., description="Reminder message content")
    urgency: str = Field(..., description="low | medium | high")
    reason: Optional[str] = Field(None, description="Why this reminder is being generated")


class ReminderResponse(BaseModel):
    reminders: List[Reminder]


# ✅ Initialize Parser
parser = PydanticOutputParser(pydantic_object=ReminderResponse)


# 🌟 Prompt Template
prompt = PromptTemplate(
    template="""
You are ZenMaster's Intelligent Reminder Generator.

---

🧠 **User Cognitive State:**
- Cognitive load: {cognitive_load}
- Focus level: {focus_level}
- Stress level: {stress_level}
- Burnout risk: {burnout_risk}
- Active Focus Block: {active_focus_block}
- Muted Channels: {muted_channels}

💖 **Health Data:**
- Sleep hours last night: {sleep_hours}
- Steps today: {steps_today}
- Mood: {mood}
- Hydration Status: {hydration_status}

📅 **Upcoming Tasks/Events:**
{task_list}

---

🎯 **Your Task:**
Generate intelligent reminders that:
- Respect active Focus Blocks (delay non-critical reminders if focus is active).
- Encourage micro-breaks if user has been in Deep Work for 90+ minutes.
- Prompt hydration if hydration status is low.
- Warn if burnout risk is high.
- Remind about sleep preparation if it's evening.

For each reminder specify:
- `type` (task, wellbeing, focus, hydration, sleep, break)
- `message` (short and clear)
- `urgency` (low, medium, high)
- `reason` (why this reminder is relevant now)

---

{format_instructions}
""",
    input_variables=[
        "cognitive_load", "focus_level", "stress_level", "burnout_risk",
        "active_focus_block", "muted_channels", "sleep_hours", "steps_today",
        "mood", "hydration_status", "task_list"
    ],
    partial_variables={"format_instructions": parser.get_format_instructions()}
)


# 🎯 Node Function
def intelligent_reminder_generator(state: AgentStateDict) -> AgentStateDict:
    print("⏰ Running Intelligent Reminder Generator Node...")

    # 📋 Prepare task list string
    task_list_str = "\n".join([
        f"- {task['id']}: {task['title']} | due: {task.get('due_date')} | priority: {task.get('priority')} | status: {task.get('status')}"
        for task in state.get("tasks", []) if task.get('status') != 'completed'
    ]) or "None"

    # 🌿 Get hydration status (assume we track water intake in health_data)
    hydration_status = state.get("health_data", {}).get("hydration_level", "unknown")

    # 🔥 Check for active focus block and muted channels
    active_focus_block = "Yes" if state.get("active_focus_block") else "No"
    muted_channels_list = state.get("muted_channels") or []
    muted_channels = ", ".join(muted_channels_list) if muted_channels_list else "None"

    # 📝 Fill Prompt
    formatted_prompt = prompt.format(
        cognitive_load=state["cognitive_state"]["cognitive_load"],
        focus_level=state["cognitive_state"]["focus_level"],
        stress_level=state["cognitive_state"]["stress_level"],
        burnout_risk=str(state["cognitive_state"]["burnout_risk"]),
        active_focus_block=active_focus_block,
        muted_channels=muted_channels,
        sleep_hours=state.get("health_data", {}).get("sleep_hours", 0),
        steps_today=state.get("health_data", {}).get("steps_today", 0),
        mood=state.get("health_data", {}).get("mood", "neutral"),
        hydration_status=hydration_status,
        task_list=task_list_str
    )

    # 🔥 Invoke LLM
    response = llm.invoke(formatted_prompt)

    # ✅ Parse response
    try:
        parsed = parser.parse(response.content)
    except Exception as e:
        print("❌ Parsing error:", e)
        print("Raw response:", response.content)
        return state

    # 🔥 Apply reminders
    reminder_log = []
    for reminder in parsed.reminders:
        # ⏳ Delay low urgency reminders if Focus Block active
        if active_focus_block == "Yes" and reminder.urgency == "low":
            state["recent_activities"].append(
                f"[{datetime.utcnow().isoformat()}] Delayed reminder (Focus Block active): {reminder.message} "
                f"(Reason: {reminder.reason})"
            )
            continue

        # ✅ Add reminder to log
        reminder_log.append(reminder.model_dump())
        state["recent_activities"].append(
            f"[{datetime.utcnow().isoformat()}] Reminder: {reminder.message} "
            f"(Type: {reminder.type}, Urgency: {reminder.urgency}, Reason: {reminder.reason})"
        )

    # ✅ Update state
    state["generated_reminders"] = reminder_log
    state["last_updated"] = datetime.utcnow()

    print("\n\n-----------------------------------\n\n")
    print('Intelligent reminder: ', state["generated_reminders"])
    print("\n\n-----------------------------------\n\n")
    
    return state
