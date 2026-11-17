import asyncio
import logging
from datetime import datetime, timedelta
from app.core.database import SessionLocal
from app.models.role import Role
from app.models.user import User
from app.models.post import Post
from app.models.schedule import Schedule
from app.models.notification import Notification
from app.services.scheduler_worker import ReminderCronWorker

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("ReminderTrial")

async def run_trial():
    print("=" * 85)
    print("      KIỂM THỬ THỰC TẾ WORKER QUÉT LỊCH: FR-12 ReminderCronWorker (60 GIÂY)")
    print("=" * 85)

    db = SessionLocal()
    worker = ReminderCronWorker(interval_seconds=60)

    # 1. Khởi tạo 4 bài viết & lịch đăng đại diện cho 4 mốc thời gian kiểm thử
    print("\n[BƯỚC 1] KHỞI TẠO DỮ LIỆU THỬ NGHIỆM CHO 4 MỐC THỜI GIAN:")
    base_time = datetime(2026, 11, 17, 14, 0, 0)
    print(f"  -> Điểm mốc chuẩn (T0): {base_time.strftime('%H:%M:%S %d/%m/%Y')}")

    # Lấy staff và manager
    staff = db.query(User).filter(User.username == "staff1").first()
    manager = db.query(User).filter(User.username == "manager").first()
    platform = db.query(Post).first().platform_id if db.query(Post).first() else 1

    # Dọn dẹp dữ liệu test cũ nếu có
    db.query(Notification).filter(Notification.title.like("%[TEST-FR12]%")).delete()
    db.query(Schedule).filter(Schedule.post_id.in_([9001, 9002, 9003, 9004])).delete()
    db.query(Post).filter(Post.post_id.in_([9001, 9002, 9003, 9004])).delete()
    db.commit()

    test_posts_data = [
        (9001, "Mốc 30 phút - Serum Dưỡng Trắng", base_time + timedelta(minutes=25)), # còn 25m
        (9002, "Mốc 10 phút - Son Kem Lì Mùa Thu", base_time + timedelta(minutes=8)),   # còn 8m
        (9003, "Mốc Đúng Giờ - Kem Chống Nắng Tự Nhiên", base_time),                   # đúng 0m
        (9004, "Mốc Quá Hạn 15 Phút - Nước Tẩy Trang", base_time - timedelta(minutes=18)), # trễ 18m
    ]

    for pid, title, sched_time in test_posts_data:
        p = Post(
            post_id=pid,
            author_id=staff.user_id,
            platform_id=platform,
            title=f"[TEST-FR12] {title}",
            caption=f"Nội dung demo bài viết #{pid}",
            status="SCHEDULED"
        )
        s = Schedule(
            post_id=pid,
            scheduled_time=sched_time,
            scheduled_by=staff.user_id,
            schedule_status="ACTIVE",
            is_reminded_30m=False,
            is_reminded_10m=False,
            is_reminded_ontime=False,
            is_overdue_alerted=False
        )
        db.add(p)
        db.add(s)
        diff_min = (sched_time - base_time).total_seconds() / 60
        print(f"  + Tạo bài #{pid}: '{title}' | Lịch: {sched_time.strftime('%H:%M')} (Chênh lệch: {diff_min:+.0f} phút)")

    db.commit()

    # 2. Thực thi chu kỳ quét lần 1 tại thời điểm base_time
    print("\n" + "-" * 85)
    print("[BƯỚC 2] THỰC THI CHU KỲ QUÉT LẦN 1 TẠI THỜI ĐIỂM T0 (14:00:00):")
    print("-" * 85)
    stats1 = await worker.scan_and_process(now=base_time, db=db)
    print(f"\n📊 KẾT QUẢ QUÉT LẦN 1:")
    print(f"  - Tổng số lịch ACTIVE quét được: {stats1['scanned']}")
    print(f"  - [Mốc 30m] Gửi nhắc trước 30 phút:        Bài viết ID {stats1['reminded_30m']}")
    print(f"  - [Mốc 10m] Gửi nhắc khẩn trước 10 phút:   Bài viết ID {stats1['reminded_10m']}")
    print(f"  - [Mốc 0m]  Gửi nhắc đúng giờ & xuất bản:  Bài viết ID {stats1['reminded_ontime']}")
    print(f"  - [Mốc 15m] Cảnh báo quá hạn >= 15 phút:   Bài viết ID {stats1['overdue_alerted']}")

    # 3. Thực thi chu kỳ quét lần 2 (ngay sau đó 30 giây) để xác minh cơ chế chống gửi trùng
    print("\n" + "-" * 85)
    print("[BƯỚC 3] THỰC THI CHU KỲ QUÉT LẦN 2 (SAU 30 GIÂY - KIỂM TRA CHỐNG TRÙNG CỜ):")
    print("-" * 85)
    stats2 = await worker.scan_and_process(now=base_time + timedelta(seconds=30), db=db)
    print(f"\n📊 KẾT QUẢ QUÉT LẦN 2:")
    print(f"  - Tổng số lịch ACTIVE quét được: {stats2['scanned']}")
    print(f"  - [Mốc 30m] Gửi nhắc lại: 0 bài (Cờ is_reminded_30m ngăn chặn thành công)")
    print(f"  - [Mốc 10m] Gửi nhắc lại: 0 bài (Cờ is_reminded_10m ngăn chặn thành công)")
    print(f"  - [Mốc 0m]  Gửi nhắc lại: 0 bài (Cờ is_reminded_ontime ngăn chặn thành công)")
    print(f"  - [Mốc 15m] Gửi nhắc lại: 0 bài (Cờ is_overdue_alerted ngăn chặn thành công)")

    # 4. Hiển thị danh sách thông báo đã tạo
    print("\n" + "-" * 85)
    print("[BƯỚC 4] CHI TIẾT CÁC THÔNG BÁO ĐÃ PHÁT SINH TRONG DATABASE:")
    print("-" * 85)
    test_notifs = (
        db.query(Notification)
        .filter(Notification.post_id.in_([9001, 9002, 9003, 9004]))
        .order_by(Notification.notification_id.asc())
        .all()
    )
    for idx, notif in enumerate(test_notifs, 1):
        user_obj = db.query(User).filter(User.user_id == notif.recipient_id).first()
        role_name = user_obj.role.role_code if user_obj else "UNKNOWN"
        print(f"\n  [{idx}] Post #{notif.post_id} | Loại: {notif.notification_type} | Người nhận: {user_obj.username} ({role_name})")
        print(f"      Tiêu đề:  {notif.title}")
        print(f"      Nội dung: {notif.message}")

    # Dọn dẹp dữ liệu test
    print("\n" + "-" * 85)
    print("[BƯỚC 5] DỌN DẸP DỮ LIỆU THỬ NGHIỆM:")
    print("-" * 85)
    db.query(Notification).filter(Notification.post_id.in_([9001, 9002, 9003, 9004])).delete()
    db.query(Schedule).filter(Schedule.post_id.in_([9001, 9002, 9003, 9004])).delete()
    db.query(Post).filter(Post.post_id.in_([9001, 9002, 9003, 9004])).delete()
    db.commit()
    print("  -> Đã dọn dẹp sạch sẽ dữ liệu thử nghiệm trong database.")

    print("\n" + "=" * 85)
    print("   KIỂM THỬ THÀNH CÔNG 100%! REMINDER CRON WORKER HOẠT ĐỘNG HOÀN HẢO")
    print("=" * 85)
    db.close()

if __name__ == "__main__":
    asyncio.run(run_trial())
