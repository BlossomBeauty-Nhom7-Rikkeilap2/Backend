from typing import Optional
from datetime import datetime
from pydantic import BaseModel

class NotificationResponse(BaseModel):
    notification_id: int
    recipient_id: int
    post_id: Optional[int] = None
    notification_type: str
    title: str
    message: str
    is_read: bool
    read_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True
