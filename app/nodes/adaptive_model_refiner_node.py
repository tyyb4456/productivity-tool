# app/nodes/adaptive_model_refiner_node.py

from state import AgentStateDict
from datetime import datetime
from typing import List, Optional

from langchain.prompts import PromptTemplate
from langchain.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field

from langchain_google_genai import ChatGoogleGenerativeAI
from dotenv import load_dotenv

load_dotenv()

llm = ChatGoogleGenerativeAI(model='gemini-2.0-flash')


# 🌟 Output Schema
class RefinementUpdate(BaseModel):
    parameter: str = Field(..., description="Meta-parameter being adjusted, e.g., 'intervention_aggressiveness', 'notification_filtering_level'")
    new_value: str = Field(..., description="Updated value for the parameter")
    reason: Optional[str] = Field(None, description="Why this change is recommended")


class RefinementResponse(BaseModel):
    updates: List[RefinementUpdate]
    summary: str = Field(..., description="Overall meta-level reflection and refinement summary")


# ✅ Initialize Parser
parser = PydanticOutputParser(pydantic_object=RefinementResponse)


# 🌟 Prompt Template
prompt = PromptTemplate(
    template="""
You are a meta-cognitive agent reflecting on long-term patterns for a user.

Here is the current data:
- Cognitive state patterns: {cognitive_patterns}
- Burnout history: {burnout_history}
- Intervention logs: {intervention_logs}
- Task reprioritization history: {reprioritization_logs}
- User preferences: {user_preferences}
- Last feedback summary: {last_feedback_summary}

Perform a meta-level reflection and determine:
- What meta-parameters of the agent's behavior should be adjusted
- The new value for each
- A reason for the change

Meta-parameters examples:
- intervention_aggressiveness (low, medium, high)
- notification_filtering_level (conservative, balanced, aggressive)
- schedule_rigidity (flexible, semi-flexible, rigid)
- burnout_sensitivity (low, medium, high)

Return a summary of the refinement as well.

{format_instructions}
""",
    input_variables=[
        "cognitive_patterns", "burnout_history", "intervention_logs",
        "reprioritization_logs", "user_preferences", "last_feedback_summary"
    ],
    partial_variables={"format_instructions": parser.get_format_instructions()}
)


# 🎯 Node Function
def adaptive_model_refiner(state: AgentStateDict) -> AgentStateDict:
    print("🧠 Running Adaptive Model Refiner Node...")

    formatted_prompt = prompt.format(
        cognitive_patterns=str(state["cognitive_state"] or "None"),
        burnout_history=str(state["burnout_status"] or "None"),
        intervention_logs=str(state["micro_interventions"] or "None"),
        reprioritization_logs=str(state.get("last_reprioritization", "None")),
        user_preferences=str(state["user_preferences"] or "None"),
        last_feedback_summary=str(state.get("last_feedback_summary", "None"))
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

    # 🔥 Apply refinements
    refinement_log = []
    model_refinement_profile = state.get("model_refinement_profile", {})
    for update in parsed.updates:
        old_value = model_refinement_profile.get(update.parameter, "Not set")
        model_refinement_profile[update.parameter] = update.new_value

        refinement_log.append({
            "parameter": update.parameter,
            "old_value": old_value,
            "new_value": update.new_value,
            "reason": update.reason
        })

        state["recent_activities"].append(
            f"[{datetime.utcnow().isoformat()}] Model refinement: '{update.parameter}' changed from '{old_value}' to '{update.new_value}' (Reason: {update.reason})"
        )

    print("\n\n-----------------------------------\n\n")
    print(f"🔧 Model refinement updates: {refinement_log}")
    print(f"model refinement summary:  {parsed.summary}")
    print("\n\n-----------------------------------\n\n")

    # ✅ Save summary
    state["model_refinement_profile"] = model_refinement_profile
    state["last_model_refinement_summary"] = parsed.summary
    state["last_model_refinement_updates"] = refinement_log
    state["last_updated"] = datetime.utcnow()

    return state
