from typing import List, Optional
import re
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func, or_

from app.models.user import User
from app.models.role import Role
from app.schemas.user import UserCreate, UserUpdate, UserStatusUpdate
from app.core.security import hash_password, validate_password_complexity

class UserService:
    @staticmethod
    def _normalize_status(raw_status: Optional[str]) -> str:
        if not raw_status:
            return "ACTIVE"
        s = raw_status.strip().upper()
        if s == "INACTIVE":
            return "LOCKED"
        if s not in ("ACTIVE", "LOCKED", "DEACTIVATED"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Trạng thái không hợp lệ (chỉ chấp nhận ACTIVE, LOCKED, DEACTIVATED)"
            )
        return s

    @staticmethod
    def _resolve_role(db: Session, role_id: Optional[int], role_code: Optional[str]) -> Role:
        if db.query(Role).count() == 0:
            db.add_all([
                Role(role_id=1, role_code="MANAGER", role_name="Marketing Manager"),
                Role(role_id=2, role_code="STAFF", role_name="Marketing Staff"),
            ])
            db.flush()

        role = None
        if role_id is not None:
            role = db.query(Role).filter(Role.role_id == role_id).first()
        elif role_code:
            code = role_code.strip().upper()
            if code in ("ADMIN", "MARKETING MANAGER", "QUẢN LÝ", "QUẢN TRỊ VIÊN"):
                code = "MANAGER"
            elif code in ("MARKETING STAFF", "NHÂN VIÊN"):
                code = "STAFF"
            role = db.query(Role).filter(func.upper(Role.role_code) == code).first()
        else:
            role = db.query(Role).filter(Role.role_code == "STAFF").first()

        if not role:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Vai trò (role) không tồn tại. Chỉ hỗ trợ MANAGER hoặc STAFF."
            )
        return role

    @staticmethod
    def get_all_users(
        db: Session,
        skip: int = 0,
        limit: int = 50,
        search: Optional[str] = None,
        role_code: Optional[str] = None,
        status_filter: Optional[str] = None
    ) -> List[User]:
        query = db.query(User)
        if search:
            kw = f"%{search.strip()}%"
            query = query.filter(
                or_(
                    User.full_name.ilike(kw),
                    User.email.ilike(kw),
                    User.username.ilike(kw)
                )
            )
        if role_code:
            code = role_code.strip().upper()
            query = query.join(Role).filter(func.upper(Role.role_code) == code)
        if status_filter:
            norm = UserService._normalize_status(status_filter)
            if norm == "LOCKED":
                query = query.filter(User.status.in_(["LOCKED", "DEACTIVATED"]))
            else:
                query = query.filter(User.status == norm)

        return query.order_by(User.user_id.asc()).offset(skip).limit(limit).all()

    @staticmethod
    def get_roles(db: Session) -> List[Role]:
        return db.query(Role).order_by(Role.role_id.asc()).all()

    @staticmethod
    def get_user_by_id(db: Session, user_id: int) -> User:
        user = db.query(User).filter(User.user_id == user_id).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Không tìm thấy người dùng"
            )
        return user

    @staticmethod
    def create_user(db: Session, user_in: UserCreate) -> User:
        email_clean = user_in.email.strip().lower()

        # 1. Kiểm tra trùng Email (ERR-01 theo SRS 3.2.3 & DAC_TA 3.3.7)
        if db.query(User).filter(func.lower(User.email) == email_clean).first():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email này đã được sử dụng"
            )

        # 2. Kiểm tra độ phức tạp mật khẩu (ERR-02 theo SRS 3.2.3 & DAC_TA 3.3.7)
        is_valid_pw, pw_msg = validate_password_complexity(user_in.password)
        if not is_valid_pw:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=pw_msg
            )

        # 3. Xử lý username (nếu không truyền thì tự sinh từ tiền tố email)
        if user_in.username and user_in.username.strip():
            username_clean = user_in.username.strip()
            if db.query(User).filter(func.lower(User.username) == username_clean.lower()).first():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Tên đăng nhập đã tồn tại trên hệ thống"
                )
        else:
            base_username = re.sub(r"[^a-zA-Z0-9_]", "", email_clean.split("@")[0]) or "user"
            if len(base_username) < 3:
                base_username = f"{base_username}_ member"
            username_clean = base_username[:40]
            suffix = 1
            while db.query(User).filter(func.lower(User.username) == username_clean.lower()).first():
                username_clean = f"{base_username[:35]}{suffix}"
                suffix += 1

        # 4. Kiểm tra vai trò Staff / Manager hợp lệ
        role = UserService._resolve_role(db, user_in.role_id, user_in.role_code)
        norm_status = UserService._normalize_status(user_in.status)

        new_user = User(
            username=username_clean,
            email=email_clean,
            password_hash=hash_password(user_in.password),
            full_name=user_in.full_name.strip(),
            role_id=role.role_id,
            avatar_url=user_in.avatar_url,
            status=norm_status
        )
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        return new_user

    @staticmethod
    def update_user(db: Session, user_id: int, user_in: UserUpdate) -> User:
        user = UserService.get_user_by_id(db, user_id)

        if user_in.email is not None:
            email_clean = user_in.email.strip().lower()
            existing = db.query(User).filter(
                func.lower(User.email) == email_clean,
                User.user_id != user_id
            ).first()
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Email này đã được sử dụng"
                )
            user.email = email_clean

        if user_in.full_name is not None and user_in.full_name.strip():
            user.full_name = user_in.full_name.strip()

        if user_in.avatar_url is not None:
            user.avatar_url = user_in.avatar_url

        if user_in.role_id is not None or user_in.role_code is not None:
            role = UserService._resolve_role(db, user_in.role_id, user_in.role_code)
            user.role_id = role.role_id

        if user_in.status is not None:
            norm_status = UserService._normalize_status(user_in.status)
            user.status = norm_status
            if norm_status == "ACTIVE":
                user.failed_login_attempts = 0
                user.locked_until = None

        if user_in.password is not None and user_in.password != "":
            is_valid_pw, pw_msg = validate_password_complexity(user_in.password)
            if not is_valid_pw:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=pw_msg
                )
            user.password_hash = hash_password(user_in.password)

        db.commit()
        db.refresh(user)
        return user

    @staticmethod
    def update_user_status(
        db: Session,
        user_id: int,
        status_in: UserStatusUpdate,
        current_user: Optional[User] = None
    ) -> User:
        """
        Khóa / Mở khóa / Vô hiệu hóa tài khoản (FR-03 & SDD 3.2.2):
        - Không thực hiện hard DELETE mà chuyển status sang LOCKED / DEACTIVATED.
        - Bảo toàn nguyên vẹn lịch sử bài viết (Post) và lịch sử phê duyệt (Approval).
        """
        user = UserService.get_user_by_id(db, user_id)
        norm_status = UserService._normalize_status(status_in.status)

        if current_user and user.user_id == current_user.user_id and norm_status != "ACTIVE":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Không thể tự khóa tài khoản Quản lý đang đăng nhập"
            )

        user.status = norm_status
        if norm_status == "ACTIVE":
            user.failed_login_attempts = 0
            user.locked_until = None

        db.commit()
        db.refresh(user)
        return user

    @staticmethod
    def reset_password(db: Session, user_id: int, new_password: str) -> User:
        """Đặt lại mật khẩu cho người dùng kèm kiểm tra độ phức tạp và băm Bcrypt."""
        user = UserService.get_user_by_id(db, user_id)
        is_valid_pw, pw_msg = validate_password_complexity(new_password)
        if not is_valid_pw:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=pw_msg
            )
        user.password_hash = hash_password(new_password)
        user.failed_login_attempts = 0
        user.locked_until = None
        db.commit()
        db.refresh(user)
        return user
