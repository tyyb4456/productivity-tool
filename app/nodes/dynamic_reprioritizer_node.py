# app/nodes/dynamic_reprioritizer_node.py

from state import AgentStateDict
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any

from langchain.prompts import PromptTemplate
from langchain.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field

from langchain_google_genai import ChatGoogleGenerativeAI
from dotenv import load_dotenv

load_dotenv()

llm = ChatGoogleGenerativeAI(model='gemini-2.0-flash')


# 🌟 Output Schema
class TaskPriorityUpdate(BaseModel):
    task_id: str = Field(..., description="ID of the task")
    new_priority: str = Field(..., description="low | medium | high")
    reason: Optional[str] = Field(None, description="Why this priority change is recommended")
    detected_pressure_factors: Optional[List[str]] = Field(
        None, description="Factors influencing reprioritization (e.g., ['high_cognitive_load', 'low_sleep_quality'])"
    )
    requires_user_confirmation: bool = Field(
        default=False, description="True if user should approve before applying this change"
    )


class ReprioritizationResponse(BaseModel):
    updates: List[TaskPriorityUpdate]


# ✅ Initialize Parser
parser = PydanticOutputParser(pydantic_object=ReprioritizationResponse)


# 🌟 Prompt Template
prompt = PromptTemplate(
    template="""
You are a task reprioritization expert AI helping balance productivity and wellbeing.

📊 **User State & Trends**
- Cognitive Load (current/trend): {cognitive_load} ({cognitive_load_trend})
- Energy Level (current/trend): {energy_level} ({energy_level_trend})
- Sleep Trends: {sleep_trends}
- Activity Trends: {activity_trends}
- Burnout Risk: {burnout_risk} ({burnout_trend})
- Stress Factors: {stress_factors}

📋 **Pending Tasks**
{task_list}

---

🎯 **Rules**
- If high burnout risk or high cognitive load persists, consider downgrading non-urgent tasks.
- Keep high-urgency tasks unless health indicators show critical strain.
- Identify detected_pressure_factors (e.g., 'low_sleep_quality', 'high_cognitive_load', 'late_night_activity').
- Flag requires_user_confirmation = True for major downgrades (high → low).

---

For each task provide:
- task_id
- new_priority (low, medium, high)
- reason
- detected_pressure_factors
- requires_user_confirmation (True/False)

{format_instructions}
""",
    input_variables=[
        "cognitive_load", "cognitive_load_trend", "energy_level", "energy_level_trend",
        "sleep_trends", "activity_trends", "burnout_risk", "burnout_trend",
        "stress_factors", "task_list"
    ],
    partial_variables={"format_instructions": parser.get_format_instructions()}
)


# 🎯 Node Function
def dynamic_reprioritizer(state: AgentStateDict, user_feedback: Optional[Dict[str, bool]] = None) -> AgentStateDict:
    print("⚖️ Running Dynamic Reprioritizer Node...")

    # 📝 Handle user feedback
    if user_feedback:
        for update in state.get("last_reprioritization", []):
            task = next((t for t in state["tasks"] if t["id"] == update["task_id"]), None)
            if not task:
                continue

            if user_feedback.get(update["task_id"], False):  # User accepted
                old_priority = task["priority"]
                task["priority"] = update["new_priority"]
                state["recent_activities"].append(
                    f"[{datetime.now(timezone.utc).isoformat()}] User confirmed reprioritization of '{task['title']}' "
                    f"from {old_priority} → {task['priority']}"
                )
            else:  # User rejected
                state["recent_activities"].append(
                    f"[{datetime.now(timezone.utc).isoformat()}] User rejected reprioritization of '{task['title']}'."
                )
        state["last_updated"] = datetime.now(timezone.utc).isoformat()
        return state

    # 📊 Prepare inputs
    trends = state["trend_data"]
    burnout = state.get("burnout_status", {})

    task_list_str = "\n".join([
        f"- {task['id']}: {task['title']} | due: {task.get('due_date')} | priority: {task['priority']} | status: {task['status']}"
        for task in state["tasks"] if task["status"] != 'completed'
    ]) or "None"

    formatted_prompt = prompt.format(
        cognitive_load=state["cognitive_state"]["cognitive_load"],
        cognitive_load_trend=trends["cognitive_load"][-3:],
        energy_level=state["cognitive_state"]["energy_level"],
        energy_level_trend=trends["energy_level"][-3:],
        sleep_trends=f"Deep: {trends['deep_sleep_hours'][-3:]}, REM: {trends['rem_sleep_hours'][-3:]}, Wake-ups: {trends['wake_up_counts'][-3:]}",
        activity_trends=f"Steps: {trends['steps'][-3:]}, Active Minutes: {trends['active_minutes'][-3:]}",
        burnout_risk=burnout.get("severity", "low"),
        burnout_trend=trends["burnout_risk"][-3:],
        stress_factors=burnout.get("detected_stress_factors", []),
        task_list=task_list_str
    )

    response = llm.invoke(formatted_prompt)

    # ✅ Parse response
    try:
        parsed = parser.parse(response.content)
    except Exception as e:
        print("❌ Parsing error:", e)
        print("Raw response:", response.content)
        return state

    reprioritization_log = []
    for update in parsed.updates:
        reprioritization_log.append(update.dict())

        # If no user confirmation needed, apply directly
        if not update.requires_user_confirmation:
            task = next((t for t in state["tasks"] if t["id"] == update.task_id), None)
            if task:
                old_priority = task["priority"]
                task["priority"] = update.new_priority
                state["recent_activities"].append(
                    f"[{datetime.now(timezone.utc).isoformat()}] Task '{task['title']}' reprioritized {old_priority} → {update.new_priority} "
                    f"(Factors: {update.detected_pressure_factors}, Reason: {update.reason})"
                )
        else:
            # Ask user for confirmation
            state["pending_user_decisions"].append({
                "type": "reprioritization",
                "task_id": update.task_id,
                "suggestion": update.dict()
            })
            state["recent_activities"].append(
                f"[{datetime.now(timezone.utc).isoformat()}] Suggested reprioritization for '{update.task_id}': "
                f"{update.new_priority} (Confirmation needed)"
            )

    state["last_reprioritization"] = reprioritization_log

    print("\n\n-----------------------------------\n\n")
    print('Reprioritization Log:', state["last_reprioritization"])
    print("\n\n-----------------------------------\n\n")

    state["last_updated"] = datetime.now(timezone.utc).isoformat()
    return state
