# models/trend.py

from typing import TypedDict, List

class TrendDataDict(TypedDict):
    cognitive_load: List[int]
    focus_level: List[str] 
    energy_level: List[float]
    sleep_hours: List[float]
    deep_sleep_hours: List[float]
    rem_sleep_hours: List[float]
    wake_up_counts: List[int]
    steps: List[int]
    active_minutes: List[int]
    mood_entries: List[str]
    sentiment_scores: List[str]
    detected_stress_signatures: List[str]
    burnout_risk: List[bool]  # Burnout risk trend over time (True/False)
    detected_stress_factors: List[str]
    resting_heart_rate: List[int]  
    hrv: List[float]               
    hydration_level: List[str]     
    late_night_activity_count: List[int]  
    productive_hours_ratio: List[float]  



def create_default_trend_data() -> TrendDataDict:
    return TrendDataDict(
        cognitive_load=[],
        energy_level=[],
        sleep_hours=[],
        deep_sleep_hours=[],
        rem_sleep_hours=[],
        wake_up_counts=[],
        steps=[],
        active_minutes=[],
        mood_entries=[],
        sentiment_scores=[],
        detected_stress_signatures=[],
        burnout_risk=[],
        detected_stress_factors=[],
        resting_heart_rate=[],
        hrv=[],
        hydration_level=[],
        late_night_activity_count=[],
        productive_hours_ratio=[]
    )
