# app/main.py

import schedule
import time
from datetime import datetime

from state import AgentStateDict
from graph_builder import build_agent_graph


graph = build_agent_graph()
state = AgentStateDict()  # Initial empty state


def run_morning_routine():
    print("🌅 Running Morning Routine...")
    state = graph.invoke(state, entry_point="ToolNode", until="CalendarBlockingNode")


def run_workday_loop():
    print("🔁 Running Workday Loop...")
    state = graph.invoke(state, entry_point="DynamicReprioritizer", until="MicroInterventionSuggestor")


def run_evening_routine():
    print("🌇 Running Evening Routine...")
    state = graph.invoke(state, entry_point="FeedbackLoop", until="UserPreferencesLearner")


def run_weekly_meta_refinement():
    print("📆 Running Weekly Meta-Refinement...")
    state = graph.invoke(state, entry_point="AdaptiveModelRefiner")


# ⏱ Schedule Tasks
schedule.every().day.at("07:00").do(run_morning_routine)
schedule.every().hour.at(":00").do(run_workday_loop)  # Every hour
schedule.every().day.at("19:00").do(run_evening_routine)
schedule.every().sunday.at("20:00").do(run_weekly_meta_refinement)


# ⚡ Event-Driven Triggers
def on_new_task_added(task):
    print("📥 New task detected. Triggering DynamicReprioritizer...")
    state["tasks"].append(task)
    state = graph.invoke(state, entry_point="DynamicReprioritizer", until="MicroInterventionSuggestor")


def on_user_feedback_received(feedback):
    print("💬 User feedback received. Triggering Feedback Loop...")
    state["recent_feedback"].append(feedback)
    state = graph.invoke(state, entry_point="FeedbackLoop", until="UserPreferencesLearner")


def on_burnout_sign_detected():
    print("🔥 Burnout signal detected. Triggering BurnoutRiskDetector...")
    state = graph.invoke(state, entry_point="BurnoutRiskDetector", until="MicroInterventionSuggestor")



# ⏳ Main Loop
if __name__ == "__main__":
    print("🚀 ZenMaster is running...")
    while True:
        schedule.run_pending()
        time.sleep(1)
