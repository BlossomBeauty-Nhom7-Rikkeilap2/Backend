import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi import HTTPException

from app.core.database import Base
from app.core.security import verify_password, validate_password_complexity, create_access_token
from app.core.dependencies import get_current_user, RoleGuard
import app.models  # noqa: F401
from app.models.role import Role
from app.models.user import User
from app.models.platform import Platform
from app.models.post import Post
from app.schemas.user import UserCreate, UserUpdate, UserStatusUpdate
from app.services.user_service import UserService

class TestFR03UserManagementRBAC(unittest.TestCase):
    """
    Kiểm thử tự động FR-03: Quản lý tài khoản & phân quyền (Task T06A65F)
    Bao phủ:
    - Tạo mới / chỉnh sửa tài khoản
    - Phân vai Staff / Manager (RBAC)
    - Khóa / Mở khóa tài khoản, ngắt phiên hiện hành, bảo toàn lịch sử bài viết (Post)
    - Mã hóa mật khẩu Bcrypt
    - Kiểm tra Email trùng lặp (ERR-01)
    - Kiểm tra độ phức tạp mật khẩu (ERR-02: >= 8 ký tự, chữ hoa, chữ thường, số)
    """

    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=self.engine)
        SessionTesting = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        self.db = SessionTesting()

        # Seed 2 vai trò chuẩn: MANAGER (1), STAFF (2)
        self.role_manager = Role(role_id=1, role_code="MANAGER", role_name="Marketing Manager")
        self.role_staff = Role(role_id=2, role_code="STAFF", role_name="Marketing Staff")
        self.db.add_all([self.role_manager, self.role_staff])
        self.db.commit()

        # Seed 1 Manager & 1 Staff
        self.manager = UserService.create_user(
            self.db,
            UserCreate(
                username="minhanh",
                email="minhanh@blossom.vn",
                password="Manager@123",
                full_name="Đoàn Thị Minh Anh",
                role_id=1
            )
        )
        self.staff = UserService.create_user(
            self.db,
            UserCreate(
                username="thuhuong",
                email="thuhuong@blossom.vn",
                password="Staff@123",
                full_name="Lê Thu Hương",
                role_id=2
            )
        )

        # Seed Platform & Post của Staff để kiểm tra bảo toàn lịch sử khi khóa tài khoản
        self.platform = Platform(platform_id=1, platform_code="FACEBOOK", platform_name="Facebook Fanpage", is_active=True)
        self.db.add(self.platform)
        self.db.commit()

        self.staff_post = Post(
            post_id=101,
            title="5 bước dưỡng da cho buổi sáng rạng rỡ",
            caption="Chu trình chăm sóc da dịu nhẹ cùng Blossom.",
            platform_id=1,
            author_id=self.staff.user_id,
            status="APPROVED"
        )
        self.db.add(self.staff_post)
        self.db.commit()

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(bind=self.engine)
        self.engine.dispose()

    def test_tc01_create_user_and_bcrypt_password_hashing(self):
        """TC-01: Thêm tài khoản mới thành công, mật khẩu được băm bằng Bcrypt."""
        new_user = UserService.create_user(
            self.db,
            UserCreate(
                email="ngocmai@blossom.vn",
                password="Blossom@2026",
                full_name="Trần Ngọc Mai",
                role_code="MANAGER"
            )
        )
        self.assertIsNotNone(new_user.user_id)
        self.assertEqual(new_user.email, "ngocmai@blossom.vn")
        self.assertEqual(new_user.role_id, 1)
        self.assertNotEqual(new_user.password_hash, "Blossom@2026")
        self.assertTrue(new_user.password_hash.startswith("$2b$"))
        self.assertTrue(verify_password("Blossom@2026", new_user.password_hash))

    def test_tc02_duplicate_email_rejected_err01(self):
        """TC-02 (ERR-01): Báo lỗi khi tạo hoặc cập nhật trùng Email đã tồn tại."""
        with self.assertRaises(HTTPException) as ctx:
            UserService.create_user(
                self.db,
                UserCreate(
                    email="THUHUONG@blossom.vn",
                    password="Staff@123",
                    full_name="Người Dùng Trùng Email",
                    role_id=2
                )
            )
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("Email này đã được sử dụng", ctx.exception.detail)

    def test_tc03_password_complexity_validation_err02(self):
        """TC-03 (ERR-02): Chặn mật khẩu dưới 8 ký tự hoặc thiếu chữ hoa, chữ thường, số."""
        weak_passwords = [
            "Ab1",            # Dưới 8 ký tự
            "alllowercase1",  # Thiếu chữ hoa
            "ALLUPPERCASE1",  # Thiếu chữ thường
            "NoDigitsHere",   # Thiếu chữ số
        ]
        for pwd in weak_passwords:
            ok, _ = validate_password_complexity(pwd)
            self.assertFalse(ok, f"Mật khẩu yếu '{pwd}' phải bị từ chối")
            with self.assertRaises(HTTPException) as ctx:
                UserService.create_user(
                    self.db,
                    UserCreate(
                        email=f"test_{pwd}@blossom.vn",
                        password=pwd,
                        full_name="Test Weak Password",
                        role_id=2
                    )
                )
            self.assertEqual(ctx.exception.status_code, 400)

    def test_tc04_update_user_and_change_role_staff_manager(self):
        """TC-04: Sửa thông tin tài khoản và phân quyền Staff <-> Manager."""
        updated = UserService.update_user(
            self.db,
            self.staff.user_id,
            UserUpdate(
                full_name="Lê Thu Hương (Senior)",
                role_code="MANAGER"
            )
        )
        self.assertEqual(updated.full_name, "Lê Thu Hương (Senior)")
        self.assertEqual(updated.role_id, 1)

    def test_tc05_lock_and_unlock_user_preserves_posts_and_disconnects_session(self):
        """TC-05: Khóa/Mở khóa tài khoản ngắt phiên hiện hành nhưng bảo toàn lịch sử bài viết."""
        token = create_access_token({"sub": str(self.staff.user_id), "username": self.staff.username, "role": "STAFF"})

        # Trước khi khóa: phiên hoạt động bình thường
        active_user = get_current_user(token=token, db=self.db)
        self.assertEqual(active_user.user_id, self.staff.user_id)

        # Khóa tài khoản
        locked = UserService.update_user_status(
            self.db,
            self.staff.user_id,
            UserStatusUpdate(status="LOCKED"),
            current_user=self.manager
        )
        self.assertEqual(locked.status, "LOCKED")

        # Phiên hiện hành bị ngắt ngay lập tức (403 Forbidden)
        with self.assertRaises(HTTPException) as ctx:
            get_current_user(token=token, db=self.db)
        self.assertEqual(ctx.exception.status_code, 403)

        # Bài viết của nhân sự vẫn được bảo toàn
        preserved_post = self.db.query(Post).filter(Post.post_id == 101).first()
        self.assertIsNotNone(preserved_post)
        self.assertEqual(preserved_post.author_id, self.staff.user_id)

        # Mở khóa tài khoản
        unlocked = UserService.update_user_status(
            self.db,
            self.staff.user_id,
            UserStatusUpdate(status="ACTIVE"),
            current_user=self.manager
        )
        self.assertEqual(unlocked.status, "ACTIVE")
        re_authenticated = get_current_user(token=token, db=self.db)
        self.assertEqual(re_authenticated.user_id, self.staff.user_id)

    def test_tc06_rbac_guard_blocks_staff_from_user_management(self):
        """TC-06 (BR-01): Chặn Marketing Staff truy cập chức năng quản lý tài khoản của Manager."""
        guard = RoleGuard(["MANAGER"])
        # Manager được phép
        allowed = guard(current_user=self.manager, db=self.db)
        self.assertEqual(allowed.user_id, self.manager.user_id)

        # Staff bị chặn 403 Forbidden
        with self.assertRaises(HTTPException) as ctx:
            guard(current_user=self.staff, db=self.db)
        self.assertEqual(ctx.exception.status_code, 403)

if __name__ == "__main__":
    unittest.main()
