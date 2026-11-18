from typing import Optional
from datetime import datetime
from pydantic import BaseModel, EmailStr, Field

class UserCreate(BaseModel):
    username: Optional[str] = Field(None, min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(..., description="Mật khẩu khởi tạo tối thiểu 8 ký tự, gồm chữ hoa, chữ thường và số")
    full_name: str = Field(..., min_length=1, max_length=100)
    phone: Optional[str] = Field(None, max_length=30)
    role_id: Optional[int] = None
    role_code: Optional[str] = Field(None, description="MANAGER hoặc STAFF")
    status: Optional[str] = Field("ACTIVE", description="ACTIVE, LOCKED hoặc DEACTIVATED")
    avatar_url: Optional[str] = None

class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    full_name: Optional[str] = Field(None, min_length=1, max_length=100)
    phone: Optional[str] = Field(None, max_length=30)
    avatar_url: Optional[str] = None
    role_id: Optional[int] = None
    role_code: Optional[str] = None
    status: Optional[str] = None
    password: Optional[str] = None

class UserStatusUpdate(BaseModel):
    status: str = Field(..., pattern="^(ACTIVE|LOCKED|DEACTIVATED|INACTIVE)$")

class UserPasswordReset(BaseModel):
    new_password: str = Field(..., description="Mật khẩu mới tối thiểu 8 ký tự, gồm chữ hoa, chữ thường và số")

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
