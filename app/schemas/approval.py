from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field

class ApprovalSubmit(BaseModel):
    comment: Optional[str] = None

class ApprovalAction(BaseModel):
    action: str = Field(..., pattern="^(APPROVED|REVISION_REQUESTED|REJECTED)$")
    comment: Optional[str] = None  # Bắt buộc khi REVISION_REQUESTED hoặc REJECTED (sẽ validate trong Service)

class ApprovalResponse(BaseModel):
    approval_id: int
    post_id: int
    actor_id: int
    action: str
    comment: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True
