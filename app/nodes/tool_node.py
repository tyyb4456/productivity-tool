# app/nodes/tool_node.py

from state import AgentStateDict

from models.event import CalendarEventDict
from models.health import HealthDataDict
from models.note import NoteDict
from models.tesk import TaskDict
from models.communicate import CommunicationInsightDict


from dateutil.parser import parse as parse_datetime
from datetime import datetime, timedelta
from utils.help_func import analyze_sentiment, detect_sentiment_trend, analyze_stress_marker

import logging

logger = logging.getLogger("zenmaster.tool_node")
logger.setLevel(logging.INFO)


from composio import Composio

user_id = "user-k7334"
composio = Composio(api_key="your_composio_key")





def tool_node(state: AgentStateDict) -> AgentStateDict:
    """
    Fetch Google Calendar events, Todoist tasks, Notion notes, Slack messages,
    and Health data, then populate state (TypedDict version).
    """
    logger.info("📅 Fetching 5 days calendar events and availability...")

    start_time = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
    end_time = (datetime.now() + timedelta(days=30)).replace(hour=23, minute=59, second=59, microsecond=999999).isoformat()

    # --- 📅 Calendar Events ---
    try:

  
        ce_result = composio.tools.execute(
        "GOOGLECALENDAR_EVENTS_LIST",
        user_id=user_id,
        arguments={"calendarId": "primary", "timeMin": start_time, "timeMax": end_time}
        )


        events = ce_result.get("data", {}).get("items", [])
        logger.info(f"📥 Fetched {len(events)} raw events.")

        state["calendar_events"] = []

        for event in events:
            start = event.get("start", {}).get("dateTime")
            end = event.get("end", {}).get("dateTime")

            duration = None
            if start and end:
                start_dt = parse_datetime(start)
                end_dt = parse_datetime(end)
                duration = (end_dt - start_dt).total_seconds() / 60  # minutes

            event_data: CalendarEventDict = {
                "id": event.get("id"),
                "title": event.get("summary"),
                "start_time": start,
                "end_time": end,
                "description": event.get("description"),
                "location": event.get("location"),
                "attendees": [
                    attendee.get("email") for attendee in event.get("attendees", [])
                    if attendee.get("email")
                ],
                "is_meeting": bool(event.get("attendees")),
                "duration_minutes": duration,
                "is_recurring": bool(event.get("recurringEventId")),
                "status": "confirmed",
                "last_adjustment_reason": "",
                "source": "GOOGLE_CALENDAR",
            }
            logger.info(f"Processed event: {event_data['title']}")
            state["calendar_events"].append(event_data)

        logger.info("✅ Calendar events updated.")

    except Exception as e:
        logger.error(f"❌ Error fetching calendar data: {e}")

    # --- 🕒 Free/Busy Slots ---
    try:
        fb_result = composio.tools.execute(
        "GOOGLECALENDAR_EVENTS_LIST",
        user_id=user_id,
        arguments={"calendarId": "primary", "timeMin": start_time, "timeMax": end_time, "singleEvents": True, "orderBy": "startTime"}
        )

        fb_events = fb_result.get("data", {}).get("items", [])
        busy_slots = []
        for event in fb_events:
            start = event.get("start", {}).get("dateTime")
            end = event.get("end", {}).get("dateTime")
            if start and end:
                busy_slots.append({
                    "start": start,
                    "end": end
                })
        state["busy_slots"] = busy_slots
        logger.info("✅ Busy slots updated.")

    except Exception as e:
        logger.error(f"❌ Error fetching busy slots: {e}")

    # --- ✅ Tasks (Todoist) ---
    try:
        tt_response = composio.tools.execute(
        "TODOIST_TASKS_LIST",
        user_id=user_id,
        arguments={}
        )

        tasks_data = tt_response.get("data", [])
        priority_map = {1: "low", 2: "medium", 3: "high", 4: "urgent"}


        state["tasks"] = []

        for task in tasks_data:
            due_info = task.get("due", {})
            due_datetime = due_info.get("datetime") or due_info.get("date")

            new_task: TaskDict = {
                "id": task.get("id"),
                "title": task.get("content"),
                "description": task.get("description"),
                "due_date": due_datetime,
                "priority": priority_map.get(task.get("priority"), "normal"),
                "status": "completed" if task.get("is_completed") else "pending",
                "source": "Todoist",
                "tags": task.get("labels", []),
                "estimated_duration_minutes": None,
                "last_adjustment_reason": None,
                "location": None
            }
            state["tasks"].append(new_task)

        logger.info("✅ Tasks updated.")

    except Exception as e:
        logger.error(f"❌ Error fetching tasks: {e}")

    # --- 📝 Notes (Notion) ---
    try:
        note_result = composio.tools.execute(
        "NOTION_PAGES_LIST",
        user_id=user_id,
        arguments={"database_id": "your_notion_database_id"}
        )

        notes = note_result.get("data", {}).get("results", [])

        state["notes"] = []

        for note in notes[:5]:  # Only top 5
            note_data: NoteDict = {
                "id": note["id"],
                "title": note.get("title", "Untitled"),
                "content": None,
                "created_at": note["created_time"],
                "last_modified": note["last_edited_time"],
                "tags": [],
                "source": "Notion"
            }
            state["notes"].append(note_data)

        logger.info("✅ Notes updated.")

    except Exception as e:
        logger.error(f"❌ Error fetching notes: {e}")

    # --- 💬 Communication (Slack) ---
    try:
        slack_result = composio.tools.execute(
        "SLACK_MESSAGES_LIST",
        user_id=user_id,
        arguments={"channel": "your_slack_channel_id", "limit": 100}
        )  
        messages = slack_result.get("data", {}).get("messages", [])

        message_volume = len(messages)
        avg_length = sum(len(m.get("text", "")) for m in messages) / max(message_volume, 1)
        late_night_activity = any(
            parse_datetime(m["timestamp"]).hour >= 22 or parse_datetime(m["timestamp"]).hour < 6
            for m in messages
        )

        sentiments = [analyze_sentiment(m.get("text", "")) for m in messages if m.get("text")]
        avg_sentiment = sum(sentiments) / len(sentiments) if sentiments else None

        state["communication_insight"] = CommunicationInsightDict(
            message_volume=message_volume,
            avg_message_length=int(avg_length),
            late_night_activity=late_night_activity,
            sentiment_score=avg_sentiment,
            sentiment_trend=detect_sentiment_trend(sentiments),
            source="Slack"
        )

        logger.info("✅ Communication insights updated.")

    except Exception as e:
        logger.error(f"❌ Error fetching communication insights: {e}")

    # --- 🩺 Health Data ---
    try:
        healthkit_result = composio.tools.execute(
        "APPLEHEALTHKIT_DATA_GET",
        user_id=user_id,
        arguments={"data_types": ["sleep", "steps", "heart_rate", "mood", "hydration"], "days": 7}
        )
        health_data = healthkit_result.get("data", {})

        state["health_data"] = HealthDataDict(
            sleep_hours=health_data.get("sleep_hours"),
            deep_sleep_hours=health_data.get("deep_sleep_hours"),
            steps_today=health_data.get("steps"),
            active_minutes=health_data.get("active_minutes"),
            sedentary_period=health_data.get("sedentary_period"),
            hrv=health_data.get("heart_rate_variability"),
            resting_heart_rate=health_data.get("resting_hr"),
            mood=health_data.get("mood"),
            mood_score=health_data.get("mood_score"),
            stress_marker=analyze_stress_marker(health_data),
            rem_sleep_hours=health_data.get("remaining_sleep_hours"),
            wake_up_count=health_data.get("wake_up_counts"),
            hydration_level=health_data.get("hydration_level")
        )

        logger.info("✅ Health data updated.")

    except Exception as e:
        logger.error(f"❌ Error fetching health data: {e}")

    return state
