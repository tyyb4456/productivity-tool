from state import create_default_state
from nodes.update_trend_node import updateTrend
from datetime import datetime, timezone

# Create mock state
state = create_default_state("user_001")
state["cognitive_state"]["cognitive_load_score"] = 0.8
state["cognitive_state"]["energy_level_score"] = 0.6
state["health_data"]["sleep_hours"] = 5.5
state["health_data"]["deep_sleep_hours"] = 1.0
state["health_data"]["steps_today"] = 3500
state["health_data"]["mood"] = "stressed"
state["recent_communication_messages"] = [
    {"timestamp": datetime.now(timezone.utc), "sentiment": "negative"},
    {"timestamp": datetime.now(timezone.utc), "sentiment": "neutral"}
]

# Run
updated_state = updateTrend(state)
print(updated_state["trend_data"])
