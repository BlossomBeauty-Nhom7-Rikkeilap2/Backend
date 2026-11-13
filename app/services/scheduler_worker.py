import asyncio
import logging
from datetime import datetime, timedelta
from typing import Tuple
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.schedule import Schedule
from app.models.post import Post
from app.models.notification import Notification
from app.models.user import User
from app.core.websocket import manager as ws_manager
from app.services.auto_publish_service import AutoPublishService
from app.config import settings

logger = logging.getLogger("SchedulerWorker")

async def process_active_schedules(db: Session, now: datetime) -> int:
    """
    Quét và xử lý các lịch đăng đang ACTIVE:
    - Nhắc lịch 30m / 10m
    - Xuất bản tự động khi đến giờ
    - Xử lý retry an toàn, dừng sau 3 lần và chuyển sang CANCELLED/FAILED
    Trả về số lượng bài viết đã xử lý xuất bản.
    """
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

    published_count = 0
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
            try:
                await ws_manager.send_to_user(post.author_id, {
                    "type": "SCHEDULE_REMINDER",
                    "post_id": post.post_id,
                    "title": post.title,
                    "minutes_left": 30
                })
            except Exception:
                pass

        # 2. Nhắc trước 10 phút (SCHEDULE_REMINDER)
        if 0 <= diff_minutes <= 10 and not sched.is_reminded_10m:
            sched.is_reminded_10m = True
            notif = Notification(
                recipient_id=post.author_id,
                post_id=post.post_id,
                notification_type="SCHEDULE_REMINDER",
                title="Nhắc lịch đăng bài khẩn (còn 10 phút)",
                message=f"Chỉ còn 10 phút đến giờ hệ thống tự động xuất bản bài viết '{post.title}'!"
            )
            db.add(notif)
            try:
                await ws_manager.send_to_user(post.author_id, {
                    "type": "SCHEDULE_REMINDER",
                    "post_id": post.post_id,
                    "title": post.title,
                    "minutes_left": 10
                })
            except Exception:
                pass

        # 3. ĐẾN GIỜ ĐĂNG BÀI: TỰ ĐỘNG XUẤT BẢN 100% QUA API
        if diff_seconds <= 0:
            published_count += 1
            # Chuyển trạng thái sang PUBLISHING trước khi gọi API
            post.status = "PUBLISHING"
            db.commit()

            pub_res = await AutoPublishService.execute_auto_publish(db, post, sched, now)
            if not pub_res.get("success"):
                err_text = pub_res.get("error", "Lỗi xuất bản không xác định")
                sched.retry_count = (sched.retry_count or 0) + 1
                post.retry_count = sched.retry_count
                post.error_message = err_text

                logger.warning(
                    f"[SchedulerWorker] Đăng bài #{post.post_id} thất bại (Lần {sched.retry_count}/3): {err_text}"
                )

                # Nếu thất bại >= 3 lần: hủy lịch đăng, chuyển bài sang FAILED, phát cảnh báo khẩn
                if sched.retry_count >= 3:
                    sched.schedule_status = "CANCELLED"
                    post.status = "FAILED"

                    # Gửi cảnh báo WebSocket PUBLISH_FAILED tới Tác giả và toàn bộ Quản lý
                    ws_payload = {
                        "type": "PUBLISH_FAILED",
                        "post_id": post.post_id,
                        "title": post.title,
                        "error": err_text,
                        "retry_count": sched.retry_count
                    }
                    try:
                        await ws_manager.send_to_user(post.author_id, ws_payload)
                        await ws_manager.broadcast_to_role("MANAGER", ws_payload)
                    except Exception:
                        pass

                    # Tạo Notification lưu DB
                    notif = Notification(
                        recipient_id=post.author_id,
                        post_id=post.post_id,
                        notification_type="SCHEDULE_REMINDER",
                        title="Xuất bản thất bại ❌",
                        message=f"Bài viết '{post.title}' không thể xuất bản sau {sched.retry_count} lần thử. Lỗi: {err_text}"
                    )
                    db.add(notif)
                else:
                    # Nếu retry < 3, đặt lại trạng thái SCHEDULED để chu kỳ sau tiếp tục thử
                    post.status = "SCHEDULED"

            db.commit()

    return published_count

async def system_timer_worker():
    """
    Bộ định thời hệ thống chạy ngầm (System Timer - SDD 2.1 & 3.2.5).
    Quét bảng schedules định kỳ mỗi phút để gửi nhắc lịch và tự động xuất bản.
    Xử lý retry an toàn, ngăn chặn vòng lặp vô tận khi API lỗi.
    """
    while True:
        db = None
        try:
            db = SessionLocal()
            now = datetime.now()
            await process_active_schedules(db, now)
        except Exception as e:
            if db:
                db.rollback()
            logger.error(f"[SchedulerWorker] Lỗi trong vòng lặp scheduler: {e}")
        finally:
            if db:
                db.close()

        # Chờ đến chu kỳ quét tiếp theo
        await asyncio.sleep(settings.SCHEDULER_INTERVAL_SECONDS)
