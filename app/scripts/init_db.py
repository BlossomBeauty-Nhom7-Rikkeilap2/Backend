import sys
import os
from datetime import datetime, timedelta

# Cấu hình UTF-8 cho console tránh lỗi UnicodeEncodeError
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

def initialize_database(reset: bool = False):
    print("=" * 65)
    print("KHỞI TẠO CƠ SỞ DỮ LIỆU & SEED DỮ LIỆU MẪU (Task: T06A65C)")
    print("=" * 65)

    if reset:
        print("[0/3] Đang đặt lại toàn bộ bảng CSDL (+1 điểm thưởng)...")
        Base.metadata.drop_all(bind=engine)
        print("  -> Đã xóa sạch các bảng cũ thành công.")

    # 1. Tạo toàn bộ 8 bảng CSDL theo thiết kế ERD
    print("[1/3] Đang khởi tạo cấu trúc 8 bảng...")
    Base.metadata.create_all(bind=engine)
    print("  -> Đã tạo thành công 8 bảng: roles, users, platforms, posts, approvals, schedules, notifications, post_statistics.")

    db = SessionLocal()
    try:
        # 2. Khởi tạo dữ liệu vai trò & nền tảng
        print("[2/3] Đang tạo dữ liệu vai trò và 3 nền tảng...")
        
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

        # 2.2 Platforms (3 Nền tảng)
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

        # 3. Tạo 1 Manager & 4 Staff theo đúng yêu cầu Task T06A65C
        print("[3/3] Đang tạo tài khoản 1 Manager & 4 Staff...")
        test_users = [
            {
                "username": "minhanh_mgr",
                "email": "minhanh.manager@kbeauty.vn",
                "password": "Password@123",
                "full_name": "Doãn Thị Minh Anh (Manager)",
                "role_id": 1
            },
            {
                "username": "conghuy_staff",
                "email": "conghuy.staff@kbeauty.vn",
                "password": "Password@123",
                "full_name": "Trịnh Trần Công Huy (Staff)",
                "role_id": 2
            },
            {
                "username": "phatdat_staff",
                "email": "phatdat.staff@kbeauty.vn",
                "password": "Password@123",
                "full_name": "Nguyễn Phát Đạt (Staff)",
                "role_id": 2
            },
            {
                "username": "hoangson_staff",
                "email": "hoangson.staff@kbeauty.vn",
                "password": "Password@123",
                "full_name": "Phan Hoàng Sơn (Staff)",
                "role_id": 2
            },
            {
                "username": "phuongthao_staff",
                "email": "phuongthao.staff@kbeauty.vn",
                "password": "Password@123",
                "full_name": "Lê Phương Thảo (Staff)",
                "role_id": 2
            }
        ]

        user_map = {}
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
                db.flush()
                user_map[u_item["username"]] = new_u.user_id
                print(f"  -> Đã tạo tài khoản: {u_item['username']} ({u_item['email']}) / Mật khẩu: {u_item['password']}")
            else:
                user_map[u_item["username"]] = existing_user.user_id
        db.commit()

        # 4. Seed các bài viết mẫu (Sample Posts)
        posts_count = db.query(Post).count()
        if posts_count == 0:
            print("  -> Đang tạo các bài viết mẫu đa dạng trạng thái...")
            now = datetime.now()
            sample_posts = [
                Post(
                    title="Ra mắt Serum Vitamin C Hàn Quốc sáng da mờ thâm",
                    caption="Bí quyết cho làn da căng bóng chuẩn Hàn! Tinh chất Vitamin C 15% giúp mờ thâm sau 14 ngày.",
                    hashtags="#KBeauty #SerumVitaminC #SkincareHanQuoc",
                    platform_id=1,
                    author_id=user_map.get("conghuy_staff", 2),
                    media_type="IMAGE",
                    media_files=[{"url": "https://cdn.kbeauty.vn/media/serum-vitc.jpg", "size_bytes": 2450000}],
                    total_media_size_bytes=2450000,
                    planned_publish_time=now - timedelta(days=3),
                    status="PUBLISHED",
                    published_url="https://www.facebook.com/KBeautyCosmeticsVN/posts/1010101",
                    published_at=now - timedelta(days=3)
                ),
                Post(
                    title="Review Kem chống nắng nâng tông kiềm dầu 12h",
                    caption="Test độ kiềm dầu dưới nắng 38 độ! Không bết dính, nâng tông tự nhiên.",
                    hashtags="#KemChongNang #TikTokBeauty #ReviewLamDep",
                    platform_id=3,
                    author_id=user_map.get("phatdat_staff", 3),
                    media_type="VIDEO",
                    media_files=[{"url": "https://cdn.kbeauty.vn/media/sunscreen-test.mp4", "size_bytes": 18500000}],
                    total_media_size_bytes=18500000,
                    planned_publish_time=now - timedelta(days=1),
                    status="PUBLISHED",
                    published_url="https://www.tiktok.com/@kbeauty.vietnam/video/72938475610",
                    published_at=now - timedelta(days=1)
                ),
                Post(
                    title="Tips dưỡng ẩm phục hồi ban đêm cho da treatment",
                    caption="Cách phục hồi hàng rào bảo vệ da với kem dưỡng ẩm B5 rau má lên men.",
                    hashtags="#PhucHoiDa #B5RauMa #TreatmentSkincare",
                    platform_id=2,
                    author_id=user_map.get("hoangson_staff", 4),
                    media_type="IMAGE",
                    media_files=[{"url": "https://cdn.kbeauty.vn/media/b5-night-care.jpg", "size_bytes": 3200000}],
                    total_media_size_bytes=3200000,
                    planned_publish_time=now + timedelta(days=1),
                    status="SCHEDULED"
                ),
                Post(
                    title="Minigame: Đoán đúng thành phần - Nhận ngay quà khủng",
                    caption="Cơ hội nhận trọn bộ kit dưỡng ẩm du lịch trị giá 500K khi comment đúng tên thành phần!",
                    hashtags="#Minigame #Giveaway #MyPhamHanQuoc",
                    platform_id=1,
                    author_id=user_map.get("phuongthao_staff", 5),
                    media_type="IMAGE",
                    media_files=[{"url": "https://cdn.kbeauty.vn/media/minigame-banner.jpg", "size_bytes": 4100000}],
                    total_media_size_bytes=4100000,
                    planned_publish_time=now + timedelta(days=2),
                    status="APPROVED"
                ),
                Post(
                    title="Top 5 màu son MLBB hot nhất mùa lễ hội cuối năm",
                    caption="Tone màu tự nhiên tôn da, chất son kem lì mịn mượt như nhung.",
                    hashtags="#SonMoi #MLBB #SonKemLi #MakeupTrends",
                    platform_id=3,
                    author_id=user_map.get("conghuy_staff", 2),
                    media_type="VIDEO",
                    media_files=[{"url": "https://cdn.kbeauty.vn/media/lipstick-swatch.mp4", "size_bytes": 35000000}],
                    total_media_size_bytes=35000000,
                    planned_publish_time=now + timedelta(days=3),
                    status="PENDING_APPROVAL"
                ),
                Post(
                    title="Bản thảo chiến dịch Sale Black Friday giảm giá tới 50%",
                    caption="Chương trình ưu đãi lớn nhất năm giảm tới 50% toàn bộ sản phẩm dưỡng ẩm mùa đông.",
                    hashtags="#BlackFriday #Sale50 #KBeautySale",
                    platform_id=2,
                    author_id=user_map.get("phatdat_staff", 3),
                    media_type="IMAGE",
                    media_files=[{"url": "https://cdn.kbeauty.vn/media/draft-bf-sale.jpg", "size_bytes": 1500000}],
                    total_media_size_bytes=1500000,
                    status="DRAFT"
                )
            ]
            db.add_all(sample_posts)
            db.commit()
            print("  -> Đã tạo 6 bài viết mẫu thành công.")

        print("=" * 65)
        print("HOÀN TẤT KHỞI TẠO CƠ SỞ DỮ LIỆU & SEED THÀNH CÔNG!")
        print("=" * 65)
    except Exception as e:
        db.rollback()
        print(f"LỖI KHI KHỞI TẠO CSDL: {str(e)}")
    finally:
        db.close()

if __name__ == "__main__":
    reset_flag = "--reset" in sys.argv
    initialize_database(reset=reset_flag)
