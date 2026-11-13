from typing import Optional
from pydantic import BaseModel, EmailStr, field_validator

class LoginRequest(BaseModel):
    username_or_email: str
    password: str

    @field_validator("username_or_email", mode="before")
    @classmethod
    def strip_username_or_email(cls, v: str) -> str:
        if isinstance(v, str):
            return v.strip()
        return v

class UserInfoResponse(BaseModel):
    user_id: int
    username: str
    email: EmailStr
    full_name: str
    role_code: str
    role_name: str
    status: str
    avatar_url: Optional[str] = None

    class Config:
        from_attributes = True

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in_minutes: int
    user: UserInfoResponse
