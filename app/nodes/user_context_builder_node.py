# app/nodes/user_context_builder_node.py

from state import AgentStateDict
from datetime import datetime

from langchain.prompts import PromptTemplate
from langchain.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field
from typing import Optional


from langchain_google_genai import ChatGoogleGenerativeAI
from dotenv import load_dotenv

load_dotenv()

llm = ChatGoogleGenerativeAI(model='gemini-2.0-flash')


class CognitiveAssessment(BaseModel):
    cognitive_load: str = Field(..., description="Overall mental workload based on meetings, tasks, and patterns. Options: low, normal, high, overloaded.")
    cognitive_load_score: float = Field(..., description="Optional score for cognitive load, if applicable." )
    focus_level: str = Field(...,description="Predicted concentration ability at current time. Options: low, normal, high.")
    stress_level: str = Field(...,description="Current stress state considering workload, mood, and late-night activity. Options: low, normal, high, burnout_risk.")
    stress_level_score: float = Field(..., description="Optional score for stress level, if applicable." )
    burnout_risk: bool = Field(..., description="True if cumulative patterns suggest burnout risk.")
    energy_level: str = Field(..., description="Current physical and mental energy reserves. Options: low, moderate, high.")
    energy_level_score: float = Field(..., description="Optional score for energy level, if applicable.")
    wellbeing_suggestion: str = Field(..., description='A small, supportive action to help restore balance. (e.g., hydration, stretch, mindfulness).')
    productivity_suggestion: str = Field(..., description='A focus-enhancing action. (e.g., batch emails, start deep work, plan next day).')
    reasoning: str = Field(... , description="A clear explanation of how this assessment was made, referencing the provided inputs and patterns.")
    detected_stress_signatures : list[str] = Field(..., description="Any detected stress signatures based on the assessment. (e.g., high_stress_burnout, low_energy).")



parser = PydanticOutputParser(pydantic_object=CognitiveAssessment)


from langchain.prompts import PromptTemplate

prompt = PromptTemplate(
    template="""
You are ZenMaster, a hyper-intelligent wellbeing and productivity coach.

Synthesize multi-source user data to:
1. Assess real-time cognitive & physical state
2. Detect stress/burnout patterns
3. Provide dual actionable recommendations (wellbeing + productivity)
4. Update long-term preferences if patterns emerge

---

📅 Calendar Summary:
{calendar_summary}

✅ Task Summary:
{task_summary}

💬 Communication Summary:
{comm_summary}

🛌 Health Summary:
{health_summary}

😌 Mood: {mood}
⏰ Time of Day: {time_of_day}

---

💡 **Your Task:**
1. **Assess Cognitive State:**
    - cognitive_load (low | normal | high | overloaded)
    - cognitive_load_score (1–10)
    - focus_level (low | normal | high)
    - stress_level (low | normal | high | burnout_risk)
    - stress_level_score (1–10)
    - burnout_risk (true | false)
    - energy_level (low | moderate | high)
    - energy_level_score (1–10)
    - wellbeing_suggestion (short, supportive)
    - productivity_suggestion (short, actionable)
    - reasoning (explain how scores and suggestions were derived)

2. **Generate Dual Suggestions (context-aware):**
    - 🧘‍♀️ `wellbeing`: Recommend a small, supportive action to help restore balance. (e.g., hydration, stretch, mindfulness).
    - 📈 `productivity`: Suggest a focus-enhancing action. (e.g., batch emails, start deep work, plan next day).

   ✅ If time_of_day == "morning":
      - wellbeing tone: energizing
      - productivity tone: planning/preparation
   ✅ If time_of_day == "evening":
      - wellbeing tone: winding down
      - productivity tone: reflection/closure

3. **Explain Your Reasoning:**
   - Summarize how you derived your assessment.
   - Reference meetings, tasks, sleep, steps, mood, and time of day.

---

{format_instructions}
""",
    input_variables=[
        "calendar_summary", "task_summary","comm_summary", "health_summary", "mood", "time_of_day"
    ],
    partial_variables={"format_instructions": parser.get_format_instructions()}
)



def user_context_builder(state: AgentStateDict) -> AgentStateDict:
    print("🧠 Running User Context Builder Node...")

    # 📅 Summarize calendar events
    today_str = datetime.utcnow().date().isoformat()
    calendar_summary = "\n".join([
        f"- {event['title']} ({event['start_time'][11:16]}–{event['end_time'][11:16]})"
        for event in state["calendar_events"]
        if event.get("start_time", "").startswith(today_str)
    ]) or "No meetings today."

    # ✅ Summarize tasks
    task_summary = "\n".join([
        f"- {task['title']} | Due: {task.get('due_date', 'N/A')} | Priority: {task['priority']}"
        for task in state["tasks"] if task["status"] != "completed"
    ]) or "No pending tasks."

    # 💬 Summarize communication activity
    comm_insight = state.get("communication_insight", {})
    comm_summary = (
        f"Volume: {comm_insight.get('message_volume', 0)}, "
        f"Avg Length: {comm_insight.get('avg_message_length', 0)}, "
        f"Late Night: {comm_insight.get('late_night_activity', False)}, "
        f"Recent Tone: {comm_insight.get('sentiment_trend', 'neutral')}"
    ) if comm_insight else "No recent communication data available."

    # 🛌 Summarize health data
    health_data = state.get("health_data", {})
    health_summary = (
        f"Sleep: {health_data.get('sleep_hours', 0)}h, "
        f"Steps: {health_data.get('steps_today', 0)}, "
        f"HRV: {health_data.get('hrv', 'N/A')}, "
        f"RHR: {health_data.get('resting_heart_rate', 'N/A')}"
    )

    # 😌 Mood & Time
    mood = health_data.get("mood", "neutral")
    time_of_day = "morning" if datetime.utcnow().hour < 12 else "evening"

    # 📝 Format prompt
    formatted_prompt = prompt.format(
        calendar_summary=calendar_summary,
        task_summary=task_summary,
        comm_summary=comm_summary,
        health_summary=health_summary,
        mood=mood,
        time_of_day=time_of_day
    )

    # 🧠 Run LLM reasoning
    response = llm.invoke(formatted_prompt)

    try:
        parsed = parser.parse(response.content)
    except Exception as e:
        print("❌ Parsing error:", e)
        print("Raw response:", response.content)
        parsed = CognitiveAssessment(
            cognitive_load="normal", cognitive_load_score=5,
            focus_level="normal",
            stress_level="normal", stress_level_score=4,
            burnout_risk=False,
            energy_level="moderate", energy_level_score=5,
            wellbeing_suggestion="Take a short walk.",
            productivity_suggestion="Review your top 3 tasks."
        )

    # ✅ Update state cognitive model
    state["cognitive_state"] = parsed.model_dump()

    print("\n\n-----------------------------------\n\n")
    print(f"🧠 Cognitive State Assessment: {state['cognitive_state']}")
    print("\n\n-----------------------------------\n\n")

    # Alerts
    alerts = state.get("alerts", [])
    if parsed.detected_stress_signatures and parsed.burnout_risk:
        alerts.append("⚠️ Burnout risk detected: Sustained high stress and low recovery.")
    if parsed.energy_level_score and parsed.energy_level_score <= 3 and parsed.detected_stress_signatures:
        alerts.append("⚠️ Low energy detected: Recommend rest and recovery actions.")
    state["alerts"] = alerts

    # ✅ Recent Activities
    state.setdefault("recent_activities", []).append(
        f"[{datetime.utcnow().isoformat()}] Updated cognitive state: "
        f"Load={parsed.cognitive_load}, Focus={parsed.focus_level}, "
        f"Stress={parsed.stress_level}, BurnoutRisk={parsed.burnout_risk}, "
        f"Energy={parsed.energy_level}, Suggestion=({parsed.wellbeing_suggestion}, {parsed.productivity_suggestion}), "
        f"Reasoning={parsed.reasoning}"
    )

    state["last_cognitive_assessment"] = parsed.model_dump()
    state["last_updated"] = datetime.now().isoformat()
    return state