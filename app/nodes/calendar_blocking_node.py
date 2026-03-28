from datetime import datetime, timedelta
from state import AgentStateDict

def calendar_blocking_node(state: AgentStateDict) -> AgentStateDict:
    print("📅 [CalendarBlockingNode] Generating time blocks for tasks and wellbeing...")

    # --- Configurable parameters ---
    work_day_start = state.get("user_preferences", {}).get("preferred_work_hours", {}).get("start", "09:00")
    work_day_end = state.get("user_preferences", {}).get("preferred_work_hours", {}).get("end", "17:00")
    deep_work_duration = state.get("user_preferences", {}).get("preferred_deep_work_duration", 90)  # minutes
    break_interval = state.get("user_preferences", {}).get("preferred_break_interval", 60)  # minutes
    break_duration = 15  # minutes

    today = datetime.utcnow().date()
    work_start_time = datetime.strptime(f"{today}T{work_day_start}", "%Y-%m-%dT%H:%M")
    work_end_time = datetime.strptime(f"{today}T{work_day_end}", "%Y-%m-%dT%H:%M")

    # --- Existing events (to avoid conflicts) ---
    existing_events = [
        (datetime.fromisoformat(event["start_time"]), datetime.fromisoformat(event["end_time"]))
        for event in state.get("calendar_events", [])
        if datetime.fromisoformat(event["start_time"]).date() == today
    ]

    def is_time_slot_free(start: datetime, end: datetime) -> bool:
        for ev_start, ev_end in existing_events:
            if start < ev_end and end > ev_start:
                return False  # Conflict detected
        return True

    # --- Start blocking ---
    new_blocks = []
    current_time = work_start_time

    pending_tasks = sorted(
        [t for t in state.get("tasks", []) if t["status"] != "completed"],
        key=lambda t: t.get("priority", "normal"),
        reverse=True
    )

    while current_time + timedelta(minutes=deep_work_duration) <= work_end_time and pending_tasks:
        block_end = current_time + timedelta(minutes=deep_work_duration)

        if is_time_slot_free(current_time, block_end):
            task = pending_tasks.pop(0)
            new_blocks.append({
                "title": f"Focus Block: {task['title']}",
                "start_time": current_time.isoformat(),
                "end_time": block_end.isoformat()
            })
            print(f"✅ Scheduled Focus Block: {task['title']} from {current_time.time()} to {block_end.time()}")
            current_time = block_end
        else:
            current_time += timedelta(minutes=15)  # Skip ahead to find free slot

        # Insert a break after each focus block
        if current_time + timedelta(minutes=break_duration) <= work_end_time and is_time_slot_free(current_time, current_time + timedelta(minutes=break_duration)):
            new_blocks.append({
                "title": "Break: Stretch & Hydrate",
                "start_time": current_time.isoformat(),
                "end_time": (current_time + timedelta(minutes=break_duration)).isoformat()
            })
            print(f"☕ Scheduled Break at {current_time.time()} for {break_duration} mins")
            current_time += timedelta(minutes=break_duration)

    # --- Add wellbeing block in evening if burnout risk detected ---
    burnout_risk = state.get("cognitive_state", {}).get("burnout_risk", False)
    if burnout_risk:
        wind_down_start = work_end_time - timedelta(minutes=30)
        if is_time_slot_free(wind_down_start, work_end_time):
            new_blocks.append({
                "title": "Wind-down: Mindfulness / Journaling",
                "start_time": wind_down_start.isoformat(),
                "end_time": work_end_time.isoformat()
            })
            print(f"🧘 Added Wind-down block at {wind_down_start.time()}")

    # --- Merge new blocks into calendar ---
    state.setdefault("calendar_events", []).extend(new_blocks)
    state.setdefault("recent_activities", []).append(
        f"[{datetime.utcnow().isoformat()}] Calendar blocked {len(new_blocks)} new events."
    )
    state["last_updated"] = datetime.utcnow().isoformat()

    print("\n\n-----------------------------------\n\n")
    print(f"📅 New calendar blocks created: {new_blocks}")
    print("\n\n-----------------------------------\n\n")
    return state
