from datetime import datetime
from fastapi import APIRouter, Depends, Response, status, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.security import verify_password, hash_password
from app.models.user import User
from app.schemas.auth import LoginRequest, TokenResponse, UserInfoResponse, ChangePasswordRequest
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

@router.post(
    "/change-password",
    status_code=status.HTTP_200_OK,
    summary="Đổi mật khẩu tài khoản (FR-01)",
    description="Xác thực mật khẩu cũ và cập nhật mật khẩu mới băm Bcrypt."
)
def change_password(
    req: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not verify_password(req.current_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Mật khẩu hiện tại không chính xác."
        )
    if len(req.new_password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Mật khẩu mới phải có tối thiểu 8 ký tự."
        )
    current_user.password_hash = hash_password(req.new_password)
    current_user.updated_at = datetime.now()
    db.commit()
    return {"message": "Đổi mật khẩu thành công", "status": "success"}
