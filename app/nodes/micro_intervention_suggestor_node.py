from datetime import datetime
from typing import List, Optional, Dict
from state import AgentStateDict

from langchain.prompts import PromptTemplate
from langchain.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field

from langchain_google_genai import ChatGoogleGenerativeAI
from dotenv import load_dotenv

load_dotenv()

llm = ChatGoogleGenerativeAI(model='gemini-2.0-flash')


# 🌟 Output Schema
from typing import Union

class InterventionSuggestion(BaseModel):
    suggestion_id: str = Field(..., description="Unique identifier for this suggestion")
    message: str = Field(..., description="Personalized intervention suggestion")
    type: str = Field(..., description="physical | mental | hydration | mindset | calendar_block")
    urgency: str = Field(..., description="low | medium | high")
    reason: str = Field(..., description="Why this intervention is suggested")
    params: Optional[Dict[str, Union[str, int]]] = Field(
        None, description="Parameters for execution (e.g., duration, app)"
    )
    user_feedback_prompt: str = Field(..., description="Prompt to ask user for feedback on the intervention")



class InterventionResponse(BaseModel):
    interventions: List[InterventionSuggestion]


# ✅ Initialize Parser
parser = PydanticOutputParser(pydantic_object=InterventionResponse)


# 🌟 Prompt Template
prompt = PromptTemplate(
    template="""
You are a proactive wellbeing assistant. Based on user trends and context, suggest empathetic micro-interventions.

📊 **User Context & Trends**
- Cognitive Load (current/trend): {cognitive_load} ({cognitive_load_trend})
- Energy Level (current/trend): {energy_level} ({energy_level_trend})
- Sleep Quality: {sleep_trends}
- Physical Activity: {activity_trends}
- Mood Trend: {mood_trend}
- Sentiment Trend: {sentiment_trend}
- Detected Stress Factors: {stress_factors}
- Burnout Risk Level: {burnout_risk_level}

📍 **Current Situation**
- Current Task: {current_task}
- Location: {location}
- Time of Day: {time_of_day}
- Sedentary Minutes: {sedentary_minutes}

---

🎯 **Your Task**
Analyze these signals and suggest **1–3 micro-interventions**. Types can include:
- Physical: Stretch, walk, posture correction
- Mental: Mindfulness, breathing, calming music
- Hydration/Nutrition: Reminder based on activity/climate
- Mindset Shift: Cognitive reframing for specific tasks
- Calendar Block: For recovery (only suggest, don’t auto-create)

For each:
- message: Friendly suggestion
- type: physical | mental | hydration | mindset | calendar_block
- urgency: low | medium | high
- reason: Why needed
- params: Optional execution params
- user_feedback_prompt: A friendly question like "Shall I schedule this for you?" or "Would you like me to guide you through it?"

{format_instructions}
""",
    input_variables=[
        "cognitive_load", "cognitive_load_trend", "energy_level", "energy_level_trend",
        "sleep_trends", "activity_trends", "mood_trend", "sentiment_trend",
        "stress_factors", "burnout_risk_level", "current_task", "location",
        "time_of_day", "sedentary_minutes"
    ],
    partial_variables={"format_instructions": parser.get_format_instructions()}
)


# 🎯 Node Function
def micro_intervention_suggestor(state: AgentStateDict) -> AgentStateDict:
    print("🧘 Running Micro Intervention Suggestor Node...")

    trends = state["trend_data"]
    burnout = state.get("burnout_status", {})

    formatted_prompt = prompt.format(
        cognitive_load=state["cognitive_state"].get("cognitive_load", "none"),
        cognitive_load_trend=trends.get("cognitive_load", [])[-3:] or "none",
        energy_level=state["cognitive_state"].get("energy_level", "normal"),
        energy_level_trend=trends.get("energy_level", [])[-3:] or "none",
        sleep_trends=(
            f"Deep: {trends.get('deep_sleep_hours', [])[-3:] or 'none'}, "
            f"REM: {trends.get('rem_sleep_hours', [])[-3:] or 'none'}, "
            f"Wake-ups: {trends.get('wake_up_counts', [])[-3:] or 'none'}"
        ),
        activity_trends=(
            f"Steps: {trends.get('steps', [])[-3:] or 'none'}, "
            f"Active Minutes: {trends.get('active_minutes', [])[-3:] or 'none'}"
        ),
        mood_trend=trends.get("mood_entries", [])[-3:] or "none",
        sentiment_trend=trends.get("sentiment_scores", [])[-3:] or "none",
        stress_factors=burnout.get("detected_stress_factors", []) or "none",
        burnout_risk_level=burnout.get("severity", "low"),
        current_task=state.get("current_activity", "none"),
        location=state.get("user_location", "unknown"),
        time_of_day=datetime.utcnow().strftime("%H:%M"),
        sedentary_minutes=state.get("health_data", {}).get("sedentary_period", 0)
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

    # 🔥 Log interventions
    intervention_log = []
    for intervention in parsed.interventions:
        intervention_log.append(intervention.dict())
        state["recent_activities"].append(
            f"[{datetime.utcnow().isoformat()}] Micro Intervention Suggested: {intervention.message} "
            f"(Type: {intervention.type}, Urgency: {intervention.urgency}, Reason: {intervention.reason})"
        )

    # ✅ Save to state
    state["micro_interventions"] = intervention_log
    state["next_action_suggestion"] = parsed.interventions[0].message
    state["next_action_params"] = parsed.interventions[0].params
    state["user_feedback_prompt"] = parsed.interventions[0].user_feedback_prompt
    state["last_updated"] = datetime.utcnow()

    print("\n\n-----------------------------------\n\n")
    print("Micro Interventions:", state["micro_interventions"])
    print("Next Action Suggestion:", state["next_action_suggestion"])
    print("Next Action Params:", state["next_action_params"])
    print("User Feedback Prompt:", state["user_feedback_prompt"])
    print("\n\n-----------------------------------\n\n")

    return state
