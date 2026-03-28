# models/communication.py

from typing import TypedDict


class CommunicationInsightDict(TypedDict):
    message_volume: int  # Total number of messages analyzed
    avg_message_length: int  # Average length of messages
    late_night_activity: bool  # True if user was active late at night
    sentiment_score: float  # Sentiment score from -1.0 (negative) to 1.0 (positive)
    sentiment_trend: str  # improving | declining | stable
    source: str  # e.g., Slack, WhatsApp, Email
