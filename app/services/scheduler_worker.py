import asyncio
import logging
from datetime import datetime
from typing import Optional, Dict, Any, List

from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.models.schedule import Schedule
from app.models.post import Post
from app.models.notification import Notification
from app.models.user import User
from app.models.role import Role
from app.core.websocket import manager as ws_manager
from app.services.auto_publish_service import AutoPublishService
from app.config import settings

logger = logging.getLogger("ReminderCronWorker")

class ReminderCronWorker:
    """
    FR-12 & SDD 2.1 / 3.2.5: Worker chạy nền quét định kỳ mỗi 60 giây.
    - Nhắc trước 30 phút và 10 phút đến hạn đăng cho Staff (tác giả).
    - Thông báo đúng giờ (0 phút) và kích hoạt tự động xuất bản qua API.
    - Cảnh báo quá hạn 15 phút gửi cho cả Staff (tác giả) và tất cả Manager.
    - Tránh gửi trùng bằng các cờ trạng thái (is_reminded_30m, is_reminded_10m, is_reminded_ontime, is_overdue_alerted).
    """

    def __init__(self, interval_seconds: int = settings.SCHEDULER_INTERVAL_SECONDS):
        self.interval_seconds = interval_seconds
        self.is_running = False

    async def scan_and_process(
        self,
        now: Optional[datetime] = None,
        db: Optional[Session] = None
    ) -> Dict[str, Any]:
        """
        Quét và xử lý tất cả các lịch đăng ACTIVE tại mốc thời gian `now`.
        Có thể nhận `now` và `db` truyền vào để phục vụ kiểm thử (unit / integration test).
        """
        if now is None:
            now = datetime.now()

        close_db_after = False
        if db is None:
            db = SessionLocal()
            close_db_after = True

        stats: Dict[str, Any] = {
            "scanned": 0,
            "reminded_30m": [],
            "reminded_10m": [],
            "reminded_ontime": [],
            "overdue_alerted": [],
            "published": []
        }

        try:
            # Lấy tất cả lịch đăng đang ACTIVE của các bài viết chưa bị xóa
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

            stats["scanned"] = len(active_schedules)

            for sched, post in active_schedules:
                diff_seconds = (sched.scheduled_time - now).total_seconds()
                diff_minutes = diff_seconds / 60.0

                # -------------------------------------------------------------
                # 1. Nhắc trước 30 phút (SCHEDULE_REMINDER)
                # Điều kiện: Còn trong khoảng (10, 30] phút và chưa gửi cờ 30m
                # -------------------------------------------------------------
                if 10 < diff_minutes <= 30 and not sched.is_reminded_30m:
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
                        "minutes_left": 30,
                        "scheduled_time": sched.scheduled_time.isoformat()
                    })
                    stats["reminded_30m"].append(post.post_id)
                    logger.info(f"[30m Reminder] Gửi nhắc lịch 30 phút bài viết #{post.post_id} tới Staff #{post.author_id}")

                # -------------------------------------------------------------
                # 2. Nhắc trước 10 phút (SCHEDULE_REMINDER)
                # Điều kiện: Còn <= 10 phút (và > 0 phút) và chưa gửi cờ 10m
                # -------------------------------------------------------------
                if 0 < diff_minutes <= 10 and not sched.is_reminded_10m:
                    sched.is_reminded_10m = True
                    if not sched.is_reminded_30m:
                        sched.is_reminded_30m = True

                    notif = Notification(
                        recipient_id=post.author_id,
                        post_id=post.post_id,
                        notification_type="SCHEDULE_REMINDER",
                        title="Nhắc lịch đăng bài khẩn (còn 10 phút)",
                        message=f"Chỉ còn 10 phút đến giờ hệ thống tự động xuất bản bài viết '{post.title}' ({sched.scheduled_time.strftime('%H:%M %d/%m/%Y')})!"
                    )
                    db.add(notif)
                    await ws_manager.send_to_user(post.author_id, {
                        "type": "SCHEDULE_REMINDER",
                        "post_id": post.post_id,
                        "title": post.title,
                        "minutes_left": 10,
                        "scheduled_time": sched.scheduled_time.isoformat()
                    })
                    stats["reminded_10m"].append(post.post_id)
                    logger.info(f"[10m Reminder] Gửi nhắc lịch khẩn 10 phút bài viết #{post.post_id} tới Staff #{post.author_id}")

                # -------------------------------------------------------------
                # 3. Đúng giờ (0 phút / Đến giờ đăng bài)
                # Điều kiện: diff_seconds <= 0 và chưa gửi cờ đúng giờ
                # -------------------------------------------------------------
                if diff_seconds <= 0 and not sched.is_reminded_ontime:
                    sched.is_reminded_ontime = True
                    sched.is_reminded_30m = True
                    sched.is_reminded_10m = True

                    notif = Notification(
                        recipient_id=post.author_id,
                        post_id=post.post_id,
                        notification_type="SCHEDULE_REMINDER",
                        title="Đến giờ đăng bài! ⏰",
                        message=f"Đã đến thời gian đăng bài viết '{post.title}' ({sched.scheduled_time.strftime('%H:%M %d/%m/%Y')})."
                    )
                    db.add(notif)
                    await ws_manager.send_to_user(post.author_id, {
                        "type": "SCHEDULE_REMINDER",
                        "post_id": post.post_id,
                        "title": post.title,
                        "minutes_left": 0,
                        "scheduled_time": sched.scheduled_time.isoformat()
                    })
                    stats["reminded_ontime"].append(post.post_id)
                    logger.info(f"[On-Time] Đã đến giờ đăng bài #{post.post_id}. Kích hoạt tự động xuất bản.")

                    # Thử tự động xuất bản qua API mạng xã hội
                    try:
                        pub_res = await AutoPublishService.execute_auto_publish(db, post, sched, now)
                        if pub_res.get("success"):
                            stats["published"].append(post.post_id)
                            logger.info(f"[AutoPublish] Tự động xuất bản thành công bài #{post.post_id}")
                    except Exception as pub_err:
                        logger.error(f"[AutoPublish Error] Lỗi khi tự động xuất bản bài #{post.post_id}: {pub_err}")

                # -------------------------------------------------------------
                # 4. Cảnh báo quá hạn 15 phút (OVERDUE_ALERT)
                # Điều kiện: Đã quá giờ đăng >= 15 phút (diff_minutes <= -15),
                # bài viết chưa hoàn thành/published, và chưa gửi cờ cảnh báo quá hạn.
                # Gửi cho CẢ Staff (tác giả) và tất cả Manager!
                # -------------------------------------------------------------
                if diff_minutes <= -15 and post.status != "PUBLISHED" and not sched.is_overdue_alerted:
                    sched.is_overdue_alerted = True
                    sched.is_reminded_30m = True
                    sched.is_reminded_10m = True
                    sched.is_reminded_ontime = True

                    # 4.1. Gửi thông báo cho Staff (tác giả bài viết)
                    staff_notif = Notification(
                        recipient_id=post.author_id,
                        post_id=post.post_id,
                        notification_type="OVERDUE_ALERT",
                        title="CẢNH BÁO: Quá hạn đăng bài 15 phút!",
                        message=f"Bài viết '{post.title}' đã quá giờ đăng 15 phút ({sched.scheduled_time.strftime('%H:%M %d/%m/%Y')}) nhưng chưa được xuất bản. Vui lòng kiểm tra và xử lý ngay!"
                    )
                    db.add(staff_notif)
                    await ws_manager.send_to_user(post.author_id, {
                        "type": "OVERDUE_ALERT",
                        "post_id": post.post_id,
                        "title": post.title,
                        "minutes_overdue": 15,
                        "scheduled_time": sched.scheduled_time.isoformat()
                    })

                    # 4.2. Gửi thông báo cho toàn bộ Marketing Manager
                    managers = (
                        db.query(User)
                        .join(Role, User.role_id == Role.role_id)
                        .filter(Role.role_code == "MANAGER")
                        .all()
                    )

                    for mgr in managers:
                        if mgr.user_id != post.author_id:
                            mgr_notif = Notification(
                                recipient_id=mgr.user_id,
                                post_id=post.post_id,
                                notification_type="OVERDUE_ALERT",
                                title=f"Cảnh báo quá hạn đăng bài #{post.post_id} (15 phút)",
                                message=f"Bài viết '{post.title}' của nhân viên (Mã tác giả: {post.author_id}) đã quá hạn đăng 15 phút ({sched.scheduled_time.strftime('%H:%M %d/%m/%Y')}) nhưng chưa xuất bản."
                            )
                            db.add(mgr_notif)

                    # Realtime broadcast tới toàn bộ Manager đang online
                    await ws_manager.broadcast_to_role("MANAGER", {
                        "type": "OVERDUE_ALERT",
                        "post_id": post.post_id,
                        "title": post.title,
                        "author_id": post.author_id,
                        "minutes_overdue": 15,
                        "scheduled_time": sched.scheduled_time.isoformat()
                    })

                    stats["overdue_alerted"].append(post.post_id)
                    logger.warning(
                        f"[Overdue 15m] Đã gửi cảnh báo quá hạn 15 phút cho bài #{post.post_id} "
                        f"tới Staff #{post.author_id} và {len(managers)} Managers."
                    )

            db.commit()
            return stats

        except Exception as e:
            if db:
                db.rollback()
            logger.error(f"[ReminderCronWorker Error] Lỗi trong chu kỳ quét: {e}", exc_info=True)
            return stats
        finally:
            if close_db_after and db:
                db.close()

    async def run(self):
        """
        Vòng lặp chạy ngầm định kỳ mỗi interval_seconds (mặc định 60 giây).
        """
        self.is_running = True
        logger.info(f"🚀 [FR-12] ReminderCronWorker đã khởi động. Chu kỳ quét: {self.interval_seconds} giây.")
        while self.is_running:
            try:
                await self.scan_and_process()
            except asyncio.CancelledError:
                logger.info("🛑 ReminderCronWorker đã nhận tín hiệu dừng.")
                self.is_running = False
                break
            except Exception as e:
                logger.error(f"Lỗi không mong muốn trong ReminderCronWorker: {e}", exc_info=True)

            try:
                await asyncio.sleep(self.interval_seconds)
            except asyncio.CancelledError:
                logger.info("🛑 ReminderCronWorker đã bị hủy trong lúc sleep.")
                self.is_running = False
                break

# Singleton instance & alias functions để tích hợp vào FastAPI lifespan
reminder_worker = ReminderCronWorker()
reminder_cron_worker = reminder_worker.run
system_timer_worker = reminder_worker.run
