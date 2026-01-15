"""
Pydantic models for API responses.
"""

from pydantic import BaseModel
from typing import List, Optional


class TimeInterval(BaseModel):
    """Single outage time interval."""
    start: str  # HH:MM format
    end: str    # HH:MM format
    type: str   # "base"


class ScheduleResponse(BaseModel):
    """Response for single queue schedule."""
    queue: str
    date: str
    status: str  # "active" | "no_data"
    intervals: List[TimeInterval]
    operational_message: Optional[str] = None
    last_updated: Optional[str] = None
    total_hours_off: float


class AllSchedulesResponse(BaseModel):
    """Response for all queues on a date."""
    date: str
    last_updated: Optional[str] = None
    operational_message: Optional[str] = None
    queues: dict


class StatusResponse(BaseModel):
    """Health check response."""
    status: str
    last_scrape: Optional[str] = None
    available_dates: List[str]
    total_queues: int = 12
