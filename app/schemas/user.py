from typing import Optional
from datetime import datetime
from pydantic import BaseModel, EmailStr, Field

class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=8)
    full_name: str = Field(..., min_length=1, max_length=100)
    role_id: int
    avatar_url: Optional[str] = None

class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None
    role_id: Optional[int] = None

class UserStatusUpdate(BaseModel):
    status: str = Field(..., pattern="^(ACTIVE|LOCKED|DEACTIVATED)$")

class RoleInfo(BaseModel):
    role_id: int
    role_code: str
    role_name: str

    class Config:
        from_attributes = True

class UserResponse(BaseModel):
    user_id: int
    username: str
    email: EmailStr
    full_name: str
    role_id: int
    role: Optional[RoleInfo] = None
    status: str
    avatar_url: Optional[str] = None
    last_login_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True
