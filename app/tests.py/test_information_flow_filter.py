# tests/test_information_flow_filter.py

import sys
import os
from datetime import datetime
from typing import Dict, Any, List

# Add app directory to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../app")))

from nodes.information_flow_filter_node import information_flow_filter
from state import AgentStateDict



def sample_state() -> AgentStateDict:
    """Create a sample AgentStateDict with pending notifications."""
    return {
        "cognitive_state": {
            "cognitive_load": "high",
            "focus_level": "low",
            "stress_level": "elevated",
            "burnout_risk": "medium",
            "detected_stress_signatures": ["high_heart_rate", "shallow_breathing"],
            "in_focus_mode": True,
            "muted_channels": []
        },
        "pending_notifications": [
            "Slack: Team stand-up in 5 minutes",
            "Email: Project deadline extended",
            "Calendar: Upcoming meeting at 3 PM",
            "WhatsApp: Friend sent a meme"
        ],
        "active_focus_block": True,
        "recent_activities": [],
        "last_updated": None
    }


def test_information_flow_filter(sample_state: AgentStateDict):
    """Test the Information Flow Filter Node."""
    print("\n===== Running test_information_flow_filter =====")
    updated_state = information_flow_filter(sample_state)

    # ✅ Assertions
    assert isinstance(updated_state, dict)
    assert "pending_notifications" in updated_state
    assert "recent_activities" in updated_state
    assert isinstance(updated_state["pending_notifications"], list)
    assert isinstance(updated_state["recent_activities"], list)

    # 🔥 Print outputs
    print("\n--- Filtered Notifications ---")
    for notif in updated_state["pending_notifications"]:
        print(f"✅ Allowed: {notif}")

    print("\n--- Recent Activities Log ---")
    for activity in updated_state["recent_activities"]:
        print(activity)

    print("\n===== test_information_flow_filter PASSED =====")


if __name__ == "__main__":
    test_information_flow_filter(sample_state())
