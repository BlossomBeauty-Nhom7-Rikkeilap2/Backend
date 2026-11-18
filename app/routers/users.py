from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import RoleGuard
from app.models.user import User
from app.schemas.user import (
    UserCreate,
    UserUpdate,
    UserStatusUpdate,
    UserPasswordReset,
    UserResponse,
    RoleInfo,
)
from app.services.user_service import UserService

router = APIRouter(prefix="/users", tags=["MOD-02: User & RBAC Management"])

@router.get(
    "/roles",
    response_model=List[RoleInfo],
    summary="Lấy danh sách vai trò phân quyền (FR-03)",
    description="Trả về danh sách các vai trò hệ thống (MANAGER, STAFF)."
)
def get_roles(
    current_user: User = Depends(RoleGuard(["MANAGER"])),
    db: Session = Depends(get_db)
):
    return UserService.get_roles(db)

@router.get(
    "",
    response_model=List[UserResponse],
    summary="Lấy danh sách người dùng (FR-03)",
    description="Chỉ Marketing Manager có quyền truy cập danh sách toàn bộ người dùng, hỗ trợ tìm kiếm và lọc theo vai trò/trạng thái."
)
def get_users(
    skip: int = 0,
    limit: int = 50,
    search: Optional[str] = Query(None, description="Tìm theo họ tên, email hoặc username"),
    role: Optional[str] = Query(None, description="Lọc theo mã vai trò MANAGER hoặc STAFF"),
    status_filter: Optional[str] = Query(None, alias="status", description="Lọc theo trạng thái ACTIVE, LOCKED, DEACTIVATED"),
    current_user: User = Depends(RoleGuard(["MANAGER"])),
    db: Session = Depends(get_db)
):
    return UserService.get_all_users(db, skip, limit, search=search, role_code=role, status_filter=status_filter)

@router.get(
    "/{user_id}",
    response_model=UserResponse,
    summary="Lấy chi tiết tài khoản người dùng (FR-03)"
)
def get_user_detail(
    user_id: int,
    current_user: User = Depends(RoleGuard(["MANAGER"])),
    db: Session = Depends(get_db)
):
    return UserService.get_user_by_id(db, user_id)

@router.post(
    "",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Tạo tài khoản người dùng mới (FR-03)",
    description="Marketing Manager tạo tài khoản mới, kiểm tra trùng Email (ERR-01), độ phức tạp mật khẩu (ERR-02), mã hóa Bcrypt và phân quyền Staff/Manager."
)
def create_user(
    user_in: UserCreate,
    current_user: User = Depends(RoleGuard(["MANAGER"])),
    db: Session = Depends(get_db)
):
    return UserService.create_user(db, user_in)

@router.put(
    "/{user_id}",
    response_model=UserResponse,
    summary="Cập nhật thông tin & phân quyền người dùng (FR-03)"
)
def update_user(
    user_id: int,
    user_in: UserUpdate,
    current_user: User = Depends(RoleGuard(["MANAGER"])),
    db: Session = Depends(get_db)
):
    return UserService.update_user(db, user_id, user_in)

@router.patch(
    "/{user_id}/status",
    response_model=UserResponse,
    summary="Khóa / Mở khóa / Vô hiệu hóa tài khoản (FR-03 & SDD 3.2.2)",
    description="Cập nhật trạng thái người dùng (ACTIVE, LOCKED, DEACTIVATED). Bảo toàn bài viết và lịch sử phê duyệt."
)
def update_user_status(
    user_id: int,
    status_in: UserStatusUpdate,
    current_user: User = Depends(RoleGuard(["MANAGER"])),
    db: Session = Depends(get_db)
):
    return UserService.update_user_status(db, user_id, status_in, current_user=current_user)

@router.patch(
    "/{user_id}/reset-password",
    response_model=UserResponse,
    summary="Đặt lại mật khẩu tài khoản (FR-03)",
    description="Kiểm tra độ phức tạp mật khẩu mới (≥ 8 ký tự, chữ hoa, chữ thường, số) và băm bằng Bcrypt."
)
def reset_user_password(
    user_id: int,
    payload: UserPasswordReset,
    current_user: User = Depends(RoleGuard(["MANAGER"])),
    db: Session = Depends(get_db)
):
    return UserService.reset_password(db, user_id, payload.new_password)
