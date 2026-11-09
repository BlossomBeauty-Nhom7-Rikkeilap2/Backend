from typing import List, Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.role import Role
from app.schemas.user import UserCreate, UserUpdate, UserStatusUpdate
from app.core.security import hash_password

class UserService:
    @staticmethod
    def get_all_users(db: Session, skip: int = 0, limit: int = 50) -> List[User]:
        return db.query(User).offset(skip).limit(limit).all()

    @staticmethod
    def get_user_by_id(db: Session, user_id: int) -> Optional[User]:
        user = db.query(User).filter(User.user_id == user_id).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Không tìm thấy người dùng"
            )
        return user

    @staticmethod
    def create_user(db: Session, user_in: UserCreate) -> User:
        # Kiểm tra username và email đã tồn tại chưa
        if db.query(User).filter(User.username == user_in.username).first():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Tên đăng nhập đã tồn tại trên hệ thống"
            )
        if db.query(User).filter(User.email == user_in.email).first():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email đã được đăng ký trên hệ thống"
            )

        # Kiểm tra role_id hợp lệ
        role = db.query(Role).filter(Role.role_id == user_in.role_id).first()
        if not role:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Vai trò (role_id) không tồn tại"
            )

        new_user = User(
            username=user_in.username,
            email=user_in.email,
            password_hash=hash_password(user_in.password),
            full_name=user_in.full_name,
            role_id=user_in.role_id,
            avatar_url=user_in.avatar_url,
            status="ACTIVE"
        )
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        return new_user

    @staticmethod
    def update_user(db: Session, user_id: int, user_in: UserUpdate) -> User:
        user = UserService.get_user_by_id(db, user_id)
        if user_in.email:
            existing = db.query(User).filter(User.email == user_in.email, User.user_id != user_id).first()
            if existing:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email đã được sử dụng")
            user.email = user_in.email

        if user_in.full_name:
            user.full_name = user_in.full_name
        if user_in.avatar_url is not None:
            user.avatar_url = user_in.avatar_url
        if user_in.role_id:
            role = db.query(Role).filter(Role.role_id == user_in.role_id).first()
            if not role:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Vai trò không tồn tại")
            user.role_id = user_in.role_id

        db.commit()
        db.refresh(user)
        return user

    @staticmethod
    def update_user_status(db: Session, user_id: int, status_in: UserStatusUpdate) -> User:
        """
        Bảo toàn dữ liệu khi ngưng kích hoạt: Không thực hiện hard DELETE 
        mà chuyển status = 'DEACTIVATED' (theo SDD 3.2.2 & Mục 8.2 SRS).
        """
        user = UserService.get_user_by_id(db, user_id)
        user.status = status_in.status
        if status_in.status == "ACTIVE":
            user.failed_login_attempts = 0
            user.locked_until = None

        db.commit()
        db.refresh(user)
        return user
