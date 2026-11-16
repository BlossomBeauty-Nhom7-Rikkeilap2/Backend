import sys
import os
from datetime import datetime, timedelta

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

def seed_database(db):
    """Nạp dữ liệu hạt giống (Seed Data) chuẩn mực theo Task T06A65C:
    - 2 Vai trò (Roles: MANAGER, STAFF)
    - 3 Nền tảng (Platforms: FACEBOOK, INSTAGRAM, THREADS)
    - 5 Tài khoản người dùng (1 Manager + 4 Staff)
    - 5 Bài viết mẫu đầy đủ các trạng thái (DRAFT, PENDING_APPROVAL, APPROVED, PUBLISHED)
    - Dữ liệu phê duyệt (Approvals), lịch đăng (Schedules), thông báo (Notifications), thống kê (PostStatistics)
    """
    print("\n--- BẮT ĐẦU NẠP DỮ LIỆU HẠT GIỐNG (SEED DATA) ---")

    # 1. Seed Roles
    print("[1/5] Khởi tạo các vai trò người dùng (Roles)...")
    roles_data = [
        {"role_id": 1, "role_code": "MANAGER", "role_name": "Marketing Manager", "permissions": {"all": True, "approve": True, "manage_user": True}},
        {"role_id": 2, "role_code": "STAFF", "role_name": "Marketing Staff", "permissions": {"create_post": True, "submit": True, "edit_draft": True}},
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

    # 2. Seed Platforms (Facebook, Instagram, Threads theo quyết định của nhóm)
    print("[2/5] Khởi tạo 3 nền tảng truyền thông (Platforms: Facebook, Instagram, Threads)...")
    platforms_data = [
        {"platform_id": 1, "platform_code": "FACEBOOK", "platform_name": "Facebook Fanpage", "color_hex": "#1877F2", "channel_url": "https://facebook.com/korean_cosmetics"},
        {"platform_id": 2, "platform_code": "INSTAGRAM", "platform_name": "Instagram Business", "color_hex": "#E1306C", "channel_url": "https://instagram.com/korean_cosmetics"},
        {"platform_id": 3, "platform_code": "THREADS", "platform_name": "Threads Official", "color_hex": "#000000", "channel_url": "https://www.threads.net/@korean_cosmetics"},
    ]
    for p_item in platforms_data:
        existing_p = db.query(Platform).filter(Platform.platform_id == p_item["platform_id"]).first()
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
        else:
            # Cập nhật thông tin nền tảng (ví dụ chuyển từ TIKTOK sang THREADS)
            existing_p.platform_code = p_item["platform_code"]
            existing_p.platform_name = p_item["platform_name"]
            existing_p.color_hex = p_item["color_hex"]
            existing_p.channel_url = p_item["channel_url"]
            existing_p.is_active = True
    db.commit()

    # 3. Seed Users (1 Manager, 4 Staff theo đúng yêu cầu Task T06A65C)
    print("[3/5] Khởi tạo 1 Manager và 4 Marketing Staff...")
    test_users = [
        {
            "user_id": 1,
            "username": "manager",
            "email": "manager@rikkeilab.vn",
            "password": "Manager@123",
            "full_name": "Doãn Thị Minh Anh (Manager)",
            "role_id": 1
        },
        {
            "user_id": 2,
            "username": "staff1",
            "email": "staff1@rikkeilab.vn",
            "password": "Staff@123",
            "full_name": "Trịnh Trần Công Huy (Staff)",
            "role_id": 2
        },
        {
            "user_id": 3,
            "username": "staff2",
            "email": "staff2@rikkeilab.vn",
            "password": "Staff@123",
            "full_name": "Nguyễn Văn Đạt (Staff)",
            "role_id": 2
        },
        {
            "user_id": 4,
            "username": "staff3",
            "email": "staff3@rikkeilab.vn",
            "password": "Staff@123",
            "full_name": "Phan Hoàng Sơn (Staff)",
            "role_id": 2
        },
        {
            "user_id": 5,
            "username": "staff4",
            "email": "staff4@rikkeilab.vn",
            "password": "Staff@123",
            "full_name": "Lê Thị Thu Thảo (Staff)",
            "role_id": 2
        }
    ]

    for u_item in test_users:
        existing_user = db.query(User).filter(User.username == u_item["username"]).first()
        if not existing_user:
            new_u = User(
                user_id=u_item["user_id"],
                username=u_item["username"],
                email=u_item["email"],
                password_hash=hash_password(u_item["password"]),
                full_name=u_item["full_name"],
                role_id=u_item["role_id"],
                status="ACTIVE"
            )
            db.add(new_u)
            print(f"  + Tạo tài khoản: {u_item['username']} ({u_item['email']}) / Mật khẩu: {u_item['password']}")
        else:
            existing_user.full_name = u_item["full_name"]
            existing_user.role_id = u_item["role_id"]
    db.commit()

    # 4. Seed Sample Posts (Các bài viết mẫu đa dạng trạng thái)
    print("[4/5] Khởi tạo các bài viết mẫu (Posts & Approvals)...")
    now = datetime.now()
    sample_posts = [
        {
            "post_id": 1,
            "title": "Bộ sưu tập Son Dưỡng Thu Đông 2026 - Hương Đào Tự Nhiên",
            "caption": "Khám phá dòng son dưỡng thuần chay chiết xuất từ hoa quả tươi hữu cơ, cấp ẩm sâu 24h.",
            "hashtags": "#SonDuong #BlossomBeauty #VeganCosmetics #LipCare",
            "platform_id": 1, # Facebook
            "author_id": 2, # staff1
            "status": "DRAFT",
            "media_type": "IMAGE",
            "total_media_size_bytes": 1024 * 350
        },
        {
            "post_id": 2,
            "title": "Top 5 Serum Dưỡng Trắng & Mờ Thâm Được Yêu Thích Nhất",
            "caption": "Review chân thực 5 dòng serum quốc dân phục hồi hàng rào bảo vệ da và làm đều màu da.",
            "hashtags": "#Skincare #Serum #BeautyTips #Whitening",
            "platform_id": 2, # Instagram
            "author_id": 3, # staff2
            "status": "PENDING_APPROVAL",
            "media_type": "IMAGE",
            "total_media_size_bytes": 1024 * 512
        },
        {
            "post_id": 3,
            "title": "Tips Chăm Sóc Da Dầu Mụn Cho Gen Z Trong Mùa Hè",
            "caption": "Bỏ túi ngay 3 thói quen đơn giản giúp kiềm dầu cả ngày và ngăn ngừa mụn ẩn hiệu quả.",
            "hashtags": "#Threads #TipsChamsocda #AcneCare #BlossomGenZ",
            "platform_id": 3, # Threads
            "author_id": 4, # staff3
            "status": "APPROVED",
            "media_type": "IMAGE",
            "total_media_size_bytes": 1024 * 600
        },
        {
            "post_id": 4,
            "title": "Đại Tiệc Sale Cuối Tuần - Giảm 50% Toàn Bộ Cửa Hàng",
            "caption": "Duy nhất cuối tuần này tại hệ thống showroom Blossom Beauty trên toàn quốc. Đừng bỏ lỡ!",
            "hashtags": "#SaleCuoiTuan #KhuyenMai #BlossomBeauty #BigSale",
            "platform_id": 1, # Facebook
            "author_id": 2, # staff1
            "status": "PUBLISHED",
            "media_type": "IMAGE",
            "published_url": "https://facebook.com/korean_cosmetics/posts/1015948302",
            "published_at": now - timedelta(days=3),
            "total_media_size_bytes": 1024 * 800
        },
        {
            "post_id": 5,
            "title": "Threads Hot: Liệu Có Cần Dùng Kem Chống Nắng Trong Nhà?",
            "caption": "Tia UVA vẫn xuyên qua kính cửa sổ và ánh sáng xanh từ màn hình máy tính có thực sự gây hại?",
            "hashtags": "#Threads #Sunscreen #SkincareScience #FactCheck",
            "platform_id": 3, # Threads
            "author_id": 5, # staff4
            "status": "PUBLISHED",
            "media_type": "IMAGE",
            "published_url": "https://threads.net/@korean_cosmetics/post/839482710",
            "published_at": now - timedelta(days=1),
            "total_media_size_bytes": 1024 * 420
        }
    ]

    for p_data in sample_posts:
        existing_post = db.query(Post).filter(Post.post_id == p_data["post_id"]).first()
        if not existing_post:
            post = Post(**p_data)
            db.add(post)
    db.commit()

    # Thêm dữ liệu Approvals và Schedules cho bài mẫu
    if not db.query(Approval).filter(Approval.post_id == 2).first():
        db.add(Approval(
            post_id=2,
            actor_id=3,
            action="SUBMITTED",
            comment="Em vừa hoàn thiện bài viết và hình ảnh, kính nhờ sếp duyệt giúp em ạ!"
        ))

    if not db.query(Approval).filter(Approval.post_id == 3).first():
        db.add(Approval(
            post_id=3,
            actor_id=1,
            action="APPROVED",
            comment="Nội dung rất hay, hình ảnh bắt mắt. Đã duyệt đăng theo lịch!"
        ))

    if not db.query(Schedule).filter(Schedule.post_id == 3).first():
        db.add(Schedule(
            post_id=3,
            scheduled_time=now + timedelta(days=2),
            scheduled_by=1,
            schedule_status="ACTIVE"
        ))

    # 5. Seed Post Statistics & Notifications
    print("[5/5] Khởi tạo số liệu thống kê (Statistics) & Thông báo (Notifications)...")
    if not db.query(PostStatistic).filter(PostStatistic.post_id == 4).first():
        db.add(PostStatistic(
            post_id=4,
            reach_count=15800,
            view_count=11200,
            like_count=850,
            comment_count=120,
            share_count=54,
            source_type="API",
            updated_by=2
        ))

    if not db.query(PostStatistic).filter(PostStatistic.post_id == 5).first():
        db.add(PostStatistic(
            post_id=5,
            reach_count=6200,
            view_count=4900,
            like_count=410,
            comment_count=45,
            share_count=22,
            source_type="MANUAL",
            updated_by=5
        ))

    # Notifications mẫu
    sample_notifs = [
        {
            "recipient_id": 1,
            "post_id": 2,
            "notification_type": "APPROVAL_REQUEST",
            "title": "Yêu cầu phê duyệt bài viết mới",
            "message": "Nhân viên Nguyễn Văn Đạt đã gửi duyệt bài: 'Top 5 Serum Dưỡng Trắng & Mờ Thâm Được Yêu Thích Nhất'",
            "is_read": False
        },
        {
            "recipient_id": 4,
            "post_id": 3,
            "notification_type": "POST_APPROVED",
            "title": "Bài viết đã được phê duyệt",
            "message": "Quản lý Doãn Thị Minh Anh đã phê duyệt bài viết: 'Tips Chăm Sóc Da Dầu Mụn Cho Gen Z Trong Mùa Hè'",
            "is_read": True
        }
    ]
    for notif_item in sample_notifs:
        existing_n = db.query(Notification).filter(
            Notification.recipient_id == notif_item["recipient_id"],
            Notification.post_id == notif_item["post_id"]
        ).first()
        if not existing_n:
            db.add(Notification(**notif_item))

    db.commit()
    print("--- HOÀN TẤT NẠP DỮ LIỆU HẠT GIỐNG THÀNH CÔNG! ---\n")

def initialize_database():
    print("=" * 65)
    print("KHỞI TẠO CƠ SỞ DỮ LIỆU CHUẨN (Task T06A65C - Nhóm 7 RikkeiLab 2)")
    print("=" * 65)

    # 1. Tạo toàn bộ 8 bảng CSDL theo thiết kế ERD
    print("Đang khởi tạo 8 bảng dữ liệu theo chuẩn ERD...")
    Base.metadata.create_all(bind=engine)
    print("  -> Đã tạo thành công 8 bảng: roles, users, platforms, posts, approvals, schedules, notifications, post_statistics.")

    db = SessionLocal()
    try:
        seed_database(db)
        print("=" * 65)
        print("KHỞI TẠO CƠ SỞ DỮ LIỆU THÀNH CÔNG VÀ SẴN SÀNG SỬ DỤNG!")
        print("=" * 65)
    except Exception as e:
        db.rollback()
        print(f"LỖI KHI NẠP SEED DATA: {str(e)}")
        raise e
    finally:
        db.close()

if __name__ == "__main__":
    initialize_database()
