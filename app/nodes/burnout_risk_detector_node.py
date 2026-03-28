# app/nodes/burnout_risk_detector_node.py

from state import AgentStateDict
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict

from utils.help_func import get_trend
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import PromptTemplate
from langchain.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field
from dotenv import load_dotenv

load_dotenv()

llm = ChatGoogleGenerativeAI(model='gemini-2.0-flash')

# 🌟 Output Schema
class BurnoutAssessment(BaseModel):
    burnout_risk: bool = Field(..., description="True if burnout risk detected")
    severity: str = Field(..., description="low | moderate | high | critical")
    reason: str = Field(..., description="Explanation for the risk assessment")
    detected_stress_factors: List[str] = Field(
        ..., description="Specific factors contributing to burnout risk"
    )
    recommended_action: Optional[str] = Field(
        None, description="Suggested action: take a break | block calendar | defer tasks | mindfulness | sleep early"
    )

parser = PydanticOutputParser(pydantic_object=BurnoutAssessment)

# 🌟 Prompt Template
prompt = PromptTemplate(
    template="""
You are a wellbeing analyst AI. Assess the user's burnout risk by analyzing multi-day trends and patterns.

📊 Trends (last 3-7 days):
- Cognitive Load Scores: {cognitive_load_trend}
- Energy Level Scores: {energy_level_trend}
- Sleep Quality: {sleep_trend} (total_hours, deep_sleep_hours, rem_sleep_hours, wake_up_count)
- Physical Activity: {activity_trend} (steps, active_minutes)
- Communication Patterns: {late_night_activity} (late-night messages), {sentiment_trend} (sentiment trends)
- Mood Entries: {mood_trend}
- Detected Stress Signatures: {stress_signatures}

📝 For assessment:
1. Look for sustained high cognitive load without recovery.
2. Check for consistent late-night work or communication activity.
3. Identify declining sleep quality (less deep/REM, more wake-ups).
4. Detect reduced physical activity compared to baseline.
5. Note increased negative sentiment/mood trends.
6. Weigh multiple moderate stress factors more heavily than one severe one.

Determine:
- If burnout risk exists (True/False)
- Severity: low, moderate, high, critical
- Reasons (as a list of stress factors)
- Recommended action

{format_instructions}
""",
    input_variables=[
        "cognitive_load_trend", "energy_level_trend", "sleep_trend",
        "activity_trend", "late_night_activity", "sentiment_trend",
        "mood_trend", "stress_signatures"
    ],
    partial_variables={"format_instructions": parser.get_format_instructions()}
)


def burnout_risk_detector(state: AgentStateDict) -> AgentStateDict:
    print("🔥 Running Burnout Risk Detector Node...")

    trend = state["trend_data"]

    # --- Multi-day trends ---
    cognitive_load_trend = get_trend(trend["cognitive_load"], "CL")
    energy_level_trend = get_trend(trend["energy_level"], "EL")
    sleep_trend = (
        f"Total: {trend['sleep_hours']}, "
        f"Deep: {trend['deep_sleep_hours']}, "
        f"REM: {trend['rem_sleep_hours']}, "
        f"Wake-ups: {trend['wake_up_counts']}"
    )
    activity_trend = (
        f"Steps: {trend['steps']}, Active Minutes: {trend['active_minutes']}"
    )
    mood_trend = ", ".join(trend["mood_entries"]) or "No mood data"
    sentiment_trend = ", ".join(trend["sentiment_scores"]) or "No sentiment data"

    # --- Late-night activity detection ---
    late_night_activity = "No recent communication data"
    recent_msgs = state.get("recent_communication_messages", [])
    if recent_msgs:
        five_days_ago = datetime.now(timezone.utc) - timedelta(days=5)
        late_night_msgs = [
            msg for msg in recent_msgs
            if datetime.fromisoformat(msg["timestamp"]).hour >= 22
            or datetime.fromisoformat(msg["timestamp"]).hour < 7
        ]
        late_night_activity = f"{len(late_night_msgs)} late-night messages in last 5 days"

    stress_signatures = ", ".join(trend["detected_stress_signatures"]) or "None"

    # 🔥 Fill Prompt
    formatted_prompt = prompt.format(
        cognitive_load_trend=cognitive_load_trend,
        energy_level_trend=energy_level_trend,
        sleep_trend=sleep_trend,
        activity_trend=activity_trend,
        late_night_activity=late_night_activity,
        sentiment_trend=sentiment_trend,
        mood_trend=mood_trend,
        stress_signatures=stress_signatures
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

    # 🔥 Apply burnout assessment to state
    state["burnout_status"] = {
        "burnout_risk": parsed.burnout_risk,
        "severity": parsed.severity,
        "reason": parsed.reason,
        "detected_stress_factors": parsed.detected_stress_factors,
        "recommended_action": parsed.recommended_action
    }

    print("\n\n-----------------------------------\n\n")
    print(f"🔥 Burnout Risk Assessment: {state['burnout_status']}")
    print("\n\n-----------------------------------\n\n")

    # ✅ Log activity
    now_iso = datetime.now(timezone.utc).isoformat()
    state["recent_activities"].append(
        f"[{now_iso}] Burnout Risk Assessment: "
        f"Risk={parsed.burnout_risk}, Severity={parsed.severity}, "
        f"Factors={parsed.detected_stress_factors}, Action='{parsed.recommended_action}'"
    )

    # 📅 Proactive Coordination
    if parsed.burnout_risk:
        if parsed.recommended_action in ["block calendar", "defer tasks"]:
            state["schedule_adjustment_required"] = True
        if parsed.recommended_action in ["take a break", "mindfulness", "sleep early"]:
            state["wellbeing_reminder_required"] = True

    state["last_updated"] = now_iso
    return state
