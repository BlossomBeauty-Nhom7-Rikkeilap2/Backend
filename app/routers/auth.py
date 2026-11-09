from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.schemas.auth import LoginRequest, TokenResponse, UserInfoResponse
from app.services.auth_service import AuthService
from app.config import settings

router = APIRouter(prefix="/auth", tags=["MOD-01: Authentication & Session"])

@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Đăng nhập tài khoản (FR-01)",
    description="Xác thực thông tin, kiểm tra khóa tài khoản do brute force và cấp phát JWT Token."
)
def login(login_data: LoginRequest, response: Response, db: Session = Depends(get_db)):
    token_resp = AuthService.login(db, login_data)

    # Đặt đồng thời HttpOnly Cookie cho trình duyệt (chuẩn an toàn chống XSS theo SDD)
    response.set_cookie(
        key="access_token",
        value=token_resp.access_token,
        httponly=True,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        samesite="lax",
        secure=settings.APP_ENV == "production",
        path="/"
    )
    return token_resp

@router.post(
    "/logout",
    status_code=status.HTTP_200_OK,
    summary="Đăng xuất tài khoản (FR-02)",
    description="Thu hồi phiên làm việc và xóa bỏ HttpOnly Cookie trên trình duyệt."
)
def logout(response: Response, current_user: User = Depends(get_current_user)):
    response.delete_cookie(key="access_token", path="/")
    return {"message": "Đăng xuất thành công", "status": "success"}

@router.get(
    "/me",
    response_model=UserInfoResponse,
    summary="Lấy thông tin người dùng hiện tại (FR-02)",
    description="Trả về thông tin hồ sơ và vai trò của tài khoản đang đăng nhập."
)
def get_me(current_user: User = Depends(get_current_user)):
    role_code = current_user.role.role_code if current_user.role else "STAFF"
    role_name = current_user.role.role_name if current_user.role else "Staff"
    return UserInfoResponse(
        user_id=current_user.user_id,
        username=current_user.username,
        email=current_user.email,
        full_name=current_user.full_name,
        role_code=role_code,
        role_name=role_name,
        status=current_user.status,
        avatar_url=current_user.avatar_url
    )
