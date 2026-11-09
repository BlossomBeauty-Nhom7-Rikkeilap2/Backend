from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field

class ScheduleUpdate(BaseModel):
    scheduled_time: datetime
    remind_before_minutes: Optional[int] = Field(30, ge=5, le=120)

class CalendarEventResponse(BaseModel):
    schedule_id: int
    post_id: int
    title: str
    platform_name: str
    color_hex: str
    scheduled_time: datetime
    schedule_status: str

    class Config:
        from_attributes = True
