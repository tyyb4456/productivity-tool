# app/graph_builder.py

from langgraph.graph import StateGraph
from state import AgentStateDict

from nodes.tool_node import tool_node
from nodes.user_context_builder_node import user_context_builder
from nodes.update_trend_node import update_trend
from nodes.user_preferences_learner_node import user_preferences_learner
from nodes.burnout_risk_detector_node import burnout_risk_detector
from nodes.dynamic_reprioritizer_node import dynamic_reprioritizer
from nodes.dynamic_schedule_adjustor_node import dynamic_schedule_adjustor
from nodes.intelligent_reminder_generator_node import intelligent_reminder_generator
from nodes.micro_intervention_suggestor_node import micro_intervention_suggestor
from nodes.information_flow_filter_node import information_flow_filter
from nodes.feedback_loop_node import feedback_loop_node
from nodes.adaptive_model_refiner_node import adaptive_model_refiner
from nodes.calendar_blocking_node import calendar_blocking_node


def build_agent_graph():
    graph = StateGraph(AgentStateDict)

    # 🌅 Morning Setup
    graph.add_node("ToolNode", tool_node)
    graph.add_node("UserContextBuilder", user_context_builder)
    graph.add_node("BurnoutRiskDetector", burnout_risk_detector)
    graph.add_node("TrendingDataNode", update_trend)
    graph.add_node("DynamicScheduleAdjustor", dynamic_schedule_adjustor)
    graph.add_node("CalendarBlockingNode", calendar_blocking_node)

    graph.add_edge("ToolNode", "UserContextBuilder")
    graph.add_edge("UserContextBuilder", "BurnoutRiskDetector")
    graph.add_edge("BurnoutRiskDetector", "TrendingDataNode")
    graph.add_edge("TrendingDataNode", "DynamicScheduleAdjustor")
    graph.add_edge("DynamicScheduleAdjustor", "CalendarBlockingNode")

    # 🔁 Workday Loop
    graph.add_node("DynamicReprioritizer", dynamic_reprioritizer)
    graph.add_node("InformationFlowFilter", information_flow_filter)
    graph.add_node("IntelligentReminderGenerator", intelligent_reminder_generator)
    graph.add_node("MicroInterventionSuggestor", micro_intervention_suggestor)

    graph.add_edge("CalendarBlockingNode", "DynamicReprioritizer")
    graph.add_edge("DynamicReprioritizer", "InformationFlowFilter")
    graph.add_edge("InformationFlowFilter", "IntelligentReminderGenerator")
    graph.add_edge("IntelligentReminderGenerator", "MicroInterventionSuggestor")

    # 🌇 End-of-Day Routine
    graph.add_node("FeedbackLoop", feedback_loop_node)
    graph.add_node("UserPreferencesLearner", user_preferences_learner)

    graph.add_edge("MicroInterventionSuggestor", "FeedbackLoop")
    graph.add_edge("FeedbackLoop", "UserPreferencesLearner")

    # 📆 Weekly Meta-Refinement
    graph.add_node("AdaptiveModelRefiner", adaptive_model_refiner)
    graph.add_edge("UserPreferencesLearner", "AdaptiveModelRefiner")

    graph.set_entry_point("ToolNode")

    return graph.compile()
