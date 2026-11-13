from datetime import datetime, timedelta
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.models.user import User
from app.models.role import Role
from app.schemas.auth import LoginRequest, TokenResponse, UserInfoResponse
from app.core.security import verify_password, create_access_token
from app.config import settings

class AuthService:
    @staticmethod
    def login(db: Session, login_data: LoginRequest) -> TokenResponse:
        # 1. Tìm user theo email hoặc username (SDD 3.2.1) - đảm bảo cắt khoảng trắng 2 đầu
        identifier = login_data.username_or_email.strip() if login_data.username_or_email else ""
        user = db.query(User).filter(
            or_(
                User.username == identifier,
                User.email == identifier
            )
        ).first()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Thông tin đăng nhập không chính xác"
            )

        # 2. Kiểm tra tài khoản bị vô hiệu hóa
        if user.status == "DEACTIVATED":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Tài khoản đã bị vô hiệu hóa. Vui lòng liên hệ Quản trị viên."
            )

        # 3. Kiểm tra khóa tạm thời do brute-force (locked_until)
        if user.locked_until and user.locked_until > datetime.now():
            wait_seconds = int((user.locked_until - datetime.now()).total_seconds())
            wait_minutes = max(1, (wait_seconds + 59) // 60)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Tài khoản bị tạm khóa do nhập sai mật khẩu 5 lần. Vui lòng thử lại sau {wait_minutes} phút."
            )

        # 4. Đối chiếu mật khẩu bằng bcrypt
        if not verify_password(login_data.password, user.password_hash):
            user.failed_login_attempts += 1
            if user.failed_login_attempts >= 5:
                # Khóa tài khoản 15 phút theo SDD 3.2.1
                user.locked_until = datetime.now() + timedelta(minutes=15)
                db.commit()
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Bạn đã nhập sai mật khẩu 5 lần liên tiếp. Tài khoản đã bị tạm khóa 15 phút để bảo mật."
                )
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Mật khẩu không chính xác. Bạn còn {5 - user.failed_login_attempts} lần thử trước khi tài khoản bị khóa."
            )

        # 5. Đăng nhập thành công: reset bộ đếm, cập nhật last_login_at
        user.failed_login_attempts = 0
        user.locked_until = None
        user.last_login_at = datetime.now()
        db.commit()
        db.refresh(user)

        # Lấy thông tin Role
        role = db.query(Role).filter(Role.role_id == user.role_id).first()
        role_code = role.role_code if role else "STAFF"
        role_name = role.role_name if role else "Staff"

        # Sinh JWT Token
        token_payload = {
            "sub": str(user.user_id),
            "username": user.username,
            "role": role_code
        }
        access_token = create_access_token(token_payload)

        return TokenResponse(
            access_token=access_token,
            token_type="bearer",
            expires_in_minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES,
            user=UserInfoResponse(
                user_id=user.user_id,
                username=user.username,
                email=user.email,
                full_name=user.full_name,
                role_code=role_code,
                role_name=role_name,
                status=user.status,
                avatar_url=user.avatar_url
            )
        )
