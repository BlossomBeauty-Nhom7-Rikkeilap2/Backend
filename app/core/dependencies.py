from typing import Optional, List
from datetime import datetime
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import decode_access_token
from app.models.user import User
from app.models.role import Role

# Khởi tạo Bearer Token extractor cho Swagger UI
security_bearer = HTTPBearer(auto_error=False)

def get_token_from_request(
    request: Request,
    auth_credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_bearer)
) -> Optional[str]:
    """
    Cơ chế Hybrid: Lấy JWT Token từ Header 'Authorization: Bearer <token>' 
    hoặc dự phòng từ HttpOnly Cookie 'access_token'.
    """
    # 1. Ưu tiên lấy từ Authorization Bearer Header (cho Swagger UI, Postman, localStorage)
    if auth_credentials and auth_credentials.credentials:
        return auth_credentials.credentials

    # 2. Dự phòng lấy từ HttpOnly Cookie (cho trình duyệt Web Frontend)
    cookie_token = request.cookies.get("access_token")
    if cookie_token:
        return cookie_token

    return None

def get_current_user(
    token: Optional[str] = Depends(get_token_from_request),
    db: Session = Depends(get_db)
) -> User:
    """
    Xác thực phiên làm việc người dùng (AuthMiddleware - theo SDD 2.1 & 3.2.1).
    Kiểm tra trạng thái tài khoản: DEACTIVATED hoặc LOCKED.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Phiên đăng nhập không hợp lệ hoặc đã hết hạn",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if not token:
        raise credentials_exception

    payload = decode_access_token(token)
    if not payload:
        raise credentials_exception

    sub = payload.get("sub")
    if sub is None:
        raise credentials_exception

    try:
        user_id = int(sub)
    except (ValueError, TypeError):
        raise credentials_exception

    user = db.query(User).filter(User.user_id == user_id).first()
    if user is None:
        raise credentials_exception

    # Kiểm tra trạng thái tài khoản theo FR-01 & Mục 8.2 SRS
    if user.status == "DEACTIVATED":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tài khoản đã bị vô hiệu hóa. Vui lòng liên hệ Quản lý."
        )

    if user.locked_until and user.locked_until > datetime.now():
        wait_seconds = int((user.locked_until - datetime.now()).total_seconds())
        wait_minutes = max(1, (wait_seconds + 59) // 60)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Tài khoản đang bị tạm khóa do nhập sai mật khẩu nhiều lần. Vui lòng thử lại sau {wait_minutes} phút."
        )

    return user

class RoleGuard:
    """
    Kiểm soát phân quyền theo vai trò (RBAC - theo SDD 3.2.2 & BR-01).
    Ví dụ sử dụng: Depends(RoleGuard(["MANAGER"]))
    """
    def __init__(self, allowed_roles: List[str]):
        self.allowed_roles = allowed_roles

    def __call__(self, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> User:
        role = db.query(Role).filter(Role.role_id == current_user.role_id).first()
        if not role or role.role_code not in self.allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Quyền truy cập bị từ chối. Chỉ vai trò {', '.join(self.allowed_roles)} mới được phép thực hiện."
            )
        return current_user
