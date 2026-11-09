import sys
import os

# Cấu hình UTF-8 cho Windows console tránh lỗi charmap UnicodeEncodeError
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Thêm đường dẫn gốc vào sys.path để import được app
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from app.core.database import engine, SessionLocal, Base
from app.models import Role, User, Platform, Post, Approval, Schedule, Notification, PostStatistic
from app.core.security import hash_password

def initialize_database():
    print("=" * 60)
    print("KHỞI TẠO CƠ SỞ DỮ LIỆU CHUẨN (Nhóm 7 RikkeiLab 2)")
    print("=" * 60)

    # 1. Tạo toàn bộ 8 bảng CSDL theo thiết kế ERD
    print("[1/3] Đang khởi tạo các bảng dữ liệu...")
    Base.metadata.create_all(bind=engine)
    print("  -> Đã tạo thành công 8 bảng: roles, users, platforms, posts, approvals, schedules, notifications, post_statistics.")

    db = SessionLocal()
    try:
        # 2. Khởi tạo dữ liệu hạt giống (Seed Roles & Platforms)
        print("[2/3] Đang tạo dữ liệu vai trò và nền tảng mặc định...")
        
        # 2.1 Roles
        roles_data = [
            {"role_id": 1, "role_code": "MANAGER", "role_name": "Marketing Manager", "permissions": {"all": True, "approve": True}},
            {"role_id": 2, "role_code": "STAFF", "role_name": "Marketing Staff", "permissions": {"create_post": True, "submit": True}},
        ]
        for r_item in roles_data:
            existing_role = db.query(Role).filter(Role.role_code == r_item["role_code"]).first()
            if not existing_role:
                role = Role(
                    role_id=r_item["role_id"],
                    role_code=r_item["role_code"],
                    role_name=r_item["role_name"],
                    permissions=r_item["permissions"]
                )
                db.add(role)
        db.commit()

        # 2.2 Platforms
        platforms_data = [
            {"platform_id": 1, "platform_code": "FACEBOOK", "platform_name": "Facebook Fanpage", "color_hex": "#1877F2", "channel_url": "https://facebook.com/korean_cosmetics"},
            {"platform_id": 2, "platform_code": "INSTAGRAM", "platform_name": "Instagram Business", "color_hex": "#E1306C", "channel_url": "https://instagram.com/korean_cosmetics"},
            {"platform_id": 3, "platform_code": "TIKTOK", "platform_name": "TikTok Official", "color_hex": "#00F2FE", "channel_url": "https://tiktok.com/@korean_cosmetics"},
        ]
        for p_item in platforms_data:
            existing_p = db.query(Platform).filter(Platform.platform_code == p_item["platform_code"]).first()
            if not existing_p:
                p = Platform(
                    platform_id=p_item["platform_id"],
                    platform_code=p_item["platform_code"],
                    platform_name=p_item["platform_name"],
                    color_hex=p_item["color_hex"],
                    channel_url=p_item["channel_url"],
                    is_active=True
                )
                db.add(p)
        db.commit()

        # 3. Tạo tài khoản mẫu kiểm thử
        print("[3/3] Đang tạo tài khoản thử nghiệm mẫu...")
        test_users = [
            {
                "username": "manager",
                "email": "manager@rikkeilab.vn",
                "password": "Manager@123",
                "full_name": "Doãn Thị Minh Anh (Manager)",
                "role_id": 1
            },
            {
                "username": "staff1",
                "email": "staff1@rikkeilab.vn",
                "password": "Staff@123",
                "full_name": "Trịnh Trần Công Huy (Staff)",
                "role_id": 2
            }
        ]

        for u_item in test_users:
            existing_user = db.query(User).filter(User.username == u_item["username"]).first()
            if not existing_user:
                new_u = User(
                    username=u_item["username"],
                    email=u_item["email"],
                    password_hash=hash_password(u_item["password"]),
                    full_name=u_item["full_name"],
                    role_id=u_item["role_id"],
                    status="ACTIVE"
                )
                db.add(new_u)
                print(f"  -> Đã tạo tài khoản: {u_item['username']} ({u_item['email']}) / Mật khẩu: {u_item['password']}")
        db.commit()

        print("=" * 60)
        print("HOÀN TẤT KHỞI TẠO CƠ SỞ DỮ LIỆU THÀNH CÔNG!")
        print("Bạn có thể khởi động server: uvicorn app.main:app --reload")
        print("=" * 60)
    except Exception as e:
        db.rollback()
        print(f"LỖI KHI KHỞI TẠO CSDL: {str(e)}")
    finally:
        db.close()

if __name__ == "__main__":
    initialize_database()
