from pydantic import BaseModel
from typing import List

class TimeInterval(BaseModel):
    start: str
    end: str
    type: str  # 'base', 'extra', 'change'

class QueueSchedule(BaseModel):
    queue: str
    date: str
    intervals: List[TimeInterval]
