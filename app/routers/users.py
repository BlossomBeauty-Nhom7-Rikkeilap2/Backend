from typing import List
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import RoleGuard
from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate, UserStatusUpdate, UserResponse
from app.services.user_service import UserService

router = APIRouter(prefix="/users", tags=["MOD-02: User & RBAC Management"])

@router.get(
    "",
    response_model=List[UserResponse],
    summary="Lấy danh sách người dùng (FR-03)",
    description="Chỉ Marketing Manager có quyền truy cập danh sách toàn bộ người dùng."
)
def get_users(
    skip: int = 0,
    limit: int = 50,
    current_user: User = Depends(RoleGuard(["MANAGER"])),
    db: Session = Depends(get_db)
):
    return UserService.get_all_users(db, skip, limit)

@router.post(
    "",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Tạo tài khoản người dùng mới (FR-03)",
    description="Marketing Manager tạo tài khoản Marketing Staff mới và phân quyền vai trò."
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
    summary="Cập nhật thông tin người dùng (FR-03)"
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
    return UserService.update_user_status(db, user_id, status_in)
