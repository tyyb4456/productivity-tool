# app/nodes/feedback_loop_node.py

from state import AgentStateDict
from datetime import datetime
from typing import List, Optional, Dict, Any

from langchain.prompts import PromptTemplate
from langchain.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field

from langchain_google_genai import ChatGoogleGenerativeAI
from dotenv import load_dotenv

load_dotenv()

llm = ChatGoogleGenerativeAI(model='gemini-2.0-flash')


# 🌟 Output Schema
class PreferenceUpdate(BaseModel):
    preference: str = Field(..., description="The area being adjusted e.g. task_management, reminder_style, break_frequency")
    new_value: str = Field(..., description="The updated preference value")
    reason: Optional[str] = Field(None, description="Reason for this update")


class FeedbackResponse(BaseModel):
    updates: List[PreferenceUpdate]
    summary: str = Field(..., description="High-level summary of how feedback is interpreted")


# ✅ Initialize Parser
parser = PydanticOutputParser(pydantic_object=FeedbackResponse)


# 🌟 Prompt Template
prompt = PromptTemplate(
    template="""
You are an AI assistant helping personalize a user's productivity and wellbeing experience.

---

📝 **User Feedback:**
{feedback_text}

📋 **Current Preferences:**
{current_preferences}

---

🎯 **Your Task:**
Analyze the feedback and suggest adjustments to:
- Task prioritization style
- Reminder frequency/tone
- Break recommendations
- Notification filtering
- Any other relevant settings

For each adjustment specify:
- preference: (e.g., reminder_style, task_management)
- new_value: (what it should be updated to)
- reason: (why this change helps)

Also provide a brief summary of your interpretation.

---

{format_instructions}
""",
    input_variables=["feedback_text", "current_preferences"],
    partial_variables={"format_instructions": parser.get_format_instructions()}
)


# 🎯 Node Function
def feedback_loop_node(state: AgentStateDict) -> AgentStateDict:
    print("🔄 Running Feedback Loop Node...")

    if not state["recent_feedback"]:
        print("ℹ️ No new feedback to process.")
        return state

    # 📝 Combine feedback into a single string
    feedback_text = "\n".join(state["recent_feedback"])

    # 📋 Format current preferences
    preferences_text = "\n".join([
        f"- {k}: {v}" for k, v in state["user_preferences"].items()
    ]) or "None"

    # 🧠 Prepare prompt
    formatted_prompt = prompt.format(
        feedback_text=feedback_text,
        current_preferences=preferences_text
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

    # 🔥 Apply preference updates
    update_log: List[Dict[str, Any]] = []
    for update in parsed.updates:
        old_value = state["user_preferences"].get(update.preference, "Not set")
        state["user_preferences"][update.preference] = update.new_value

        update_log.append({
            "preference": update.preference,
            "old_value": old_value,
            "new_value": update.new_value,
            "reason": update.reason
        })

        state["recent_activities"].append(
            f"[{datetime.utcnow().isoformat()}] Preference '{update.preference}' changed from '{old_value}' "
            f"to '{update.new_value}' (Reason: {update.reason})"
        )

    # ✅ Save summary and updates
    state["last_feedback_summary"] = parsed.summary
    state["last_feedback_updates"] = update_log
    state["last_updated"] = datetime.utcnow()

    print("\n\n-----------------------------------\n\n")
    print('last_feedback_summary:', state["last_feedback_summary"])
    print('last_feedback_updates:', state["last_feedback_updates"])
    print("\n\n-----------------------------------\n\n")

    # 🚮 Clear processed feedback
    state["recent_feedback"] = []

    return state
