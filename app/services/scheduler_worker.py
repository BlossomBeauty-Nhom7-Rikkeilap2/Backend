import asyncio
from datetime import datetime, timedelta
from app.core.database import SessionLocal
from app.models.schedule import Schedule
from app.models.post import Post
from app.models.notification import Notification
from app.models.user import User
from app.core.websocket import manager as ws_manager
from app.config import settings

async def system_timer_worker():
    """
    Bộ định thời hệ thống chạy ngầm (System Timer - SDD 2.1 & 3.2.5).
    Quét bảng schedules định kỳ mỗi phút để gửi nhắc lịch và cảnh báo quá hạn.
    """
    while True:
        try:
            db = SessionLocal()
            now = datetime.now()

            # Lấy tất cả lịch đăng đang ACTIVE
            active_schedules = (
                db.query(Schedule, Post)
                .join(Post, Schedule.post_id == Post.post_id)
                .filter(
                    Schedule.schedule_status == "ACTIVE",
                    Post.status.in_(["APPROVED", "SCHEDULED"]),
                    Post.deleted_at.is_(None)
                )
                .all()
            )

            for sched, post in active_schedules:
                diff_seconds = (sched.scheduled_time - now).total_seconds()
                diff_minutes = diff_seconds / 60

                # 1. Nhắc trước 30 phút (SCHEDULE_REMINDER)
                if 0 <= diff_minutes <= 30 and not sched.is_reminded_30m:
                    sched.is_reminded_30m = True
                    notif = Notification(
                        recipient_id=post.author_id,
                        post_id=post.post_id,
                        notification_type="SCHEDULE_REMINDER",
                        title="Nhắc lịch đăng bài (còn 30 phút)",
                        message=f"Bài viết '{post.title}' dự kiến đăng vào lúc {sched.scheduled_time.strftime('%H:%M %d/%m/%Y')}."
                    )
                    db.add(notif)
                    await ws_manager.send_to_user(post.author_id, {
                        "type": "SCHEDULE_REMINDER",
                        "post_id": post.post_id,
                        "title": post.title,
                        "minutes_left": 30
                    })

                # 2. Nhắc trước 10 phút (SCHEDULE_REMINDER)
                if 0 <= diff_minutes <= 10 and not sched.is_reminded_10m:
                    sched.is_reminded_10m = True
                    notif = Notification(
                        recipient_id=post.author_id,
                        post_id=post.post_id,
                        notification_type="SCHEDULE_REMINDER",
                        title="Nhắc lịch đăng bài khẩn (còn 10 phút)",
                        message=f"Chỉ còn 10 phút đến giờ đăng bài '{post.title}'. Vui lòng chuẩn bị đăng lên mạng xã hội!"
                    )
                    db.add(notif)
                    await ws_manager.send_to_user(post.author_id, {
                        "type": "SCHEDULE_REMINDER",
                        "post_id": post.post_id,
                        "title": post.title,
                        "minutes_left": 10
                    })

                # 3. Cảnh báo quá hạn đăng (OVERDUE_ALERT)
                if diff_seconds < 0 and not sched.is_overdue_alerted:
                    sched.is_overdue_alerted = True
                    # Gửi cho tác giả
                    db.add(Notification(
                        recipient_id=post.author_id,
                        post_id=post.post_id,
                        notification_type="OVERDUE_ALERT",
                        title="CẢNH BÁO: Quá hạn đăng bài!",
                        message=f"Bài viết '{post.title}' đã quá giờ đăng ({sched.scheduled_time.strftime('%H:%M %d/%m/%Y')}) nhưng chưa được xác nhận đăng."
                    ))
                    # Gửi cho toàn bộ Marketing Manager
                    managers = db.query(User).join(User.role).filter(User.role.has(role_code="MANAGER")).all()
                    for mgr in managers:
                        db.add(Notification(
                            recipient_id=mgr.user_id,
                            post_id=post.post_id,
                            notification_type="OVERDUE_ALERT",
                            title="Báo cáo quá hạn đăng bài của nhân viên",
                            message=f"Bài viết '{post.title}' của nhân viên đã quá giờ đăng."
                        ))

                    await ws_manager.broadcast_to_role("MANAGER", {
                        "type": "OVERDUE_ALERT",
                        "post_id": post.post_id,
                        "title": post.title
                    })

            db.commit()
            db.close()
        except Exception as e:
            # Ghi log lỗi nếu có nhưng không để background task bị dừng
            pass

        # Chờ đến chu kỳ quét tiếp theo
        await asyncio.sleep(settings.SCHEDULER_INTERVAL_SECONDS)
