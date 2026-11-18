from datetime import datetime, timedelta
from typing import List, Dict, Any
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.schedule import Schedule
from app.models.post import Post
from app.models.platform import Platform
from app.models.user import User
from app.schemas.schedule import ScheduleUpdate

class ScheduleService:
    @staticmethod
    def get_calendar(db: Session, start_date: datetime, end_date: datetime) -> List[Dict[str, Any]]:
        """Lấy danh sách sự kiện trên Content Calendar theo Ngày/Tuần/Tháng kèm phát hiện xung đột < 30 phút (FR-11)."""
        schedules = (
            db.query(Schedule, Post, Platform)
            .join(Post, Schedule.post_id == Post.post_id)
            .join(Platform, Post.platform_id == Platform.platform_id)
            .filter(
                Schedule.scheduled_time >= start_date,
                Schedule.scheduled_time <= end_date,
                Schedule.schedule_status == "ACTIVE",
                Post.deleted_at.is_(None)
            )
            .all()
        )

        results: List[Dict[str, Any]] = []
        for sched, post, platform in schedules:
            results.append({
                "schedule_id": sched.schedule_id,
                "post_id": post.post_id,
                "title": post.title,
                "platform_name": platform.platform_name,
                "color_hex": platform.color_hex,
                "scheduled_time": sched.scheduled_time,
                "schedule_status": sched.schedule_status,
                "post_status": post.status,
                "has_conflict": False,
                "conflict_warning": None
            })

        # Phát hiện xung đột < 30 phút cùng nền tảng (ERR-03 / BR-12)
        for i in range(len(results)):
            for j in range(i + 1, len(results)):
                a = results[i]
                b = results[j]
                if a["platform_name"] == b["platform_name"]:
                    diff_min = abs((a["scheduled_time"] - b["scheduled_time"]).total_seconds()) / 60.0
                    if diff_min < 30:
                        msg = f"[ERR-03] Cảnh báo xung đột lịch đăng < 30 phút trên kênh {a['platform_name']} (chênh lệch {int(diff_min)} phút)."
                        a["has_conflict"] = True
                        b["has_conflict"] = True
                        a["conflict_warning"] = msg
                        b["conflict_warning"] = msg

        return results

    @staticmethod
    def update_schedule(db: Session, post_id: int, schedule_in: ScheduleUpdate, current_user: User) -> Schedule:
        """
        Lên lịch hoặc kéo-thả điều chỉnh giờ đăng bài (FR-11).
        Kiểm tra ERR-02 (chặn thời gian quá khứ) và chỉ cho phép khi Post đang ở trạng thái APPROVED hoặc SCHEDULED.
        """
        if schedule_in.scheduled_time < datetime.now() - timedelta(minutes=1):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="[ERR-02] Thời gian đăng bài phải lớn hơn thời điểm hiện tại."
            )

        post = db.query(Post).filter(Post.post_id == post_id, Post.deleted_at.is_(None)).first()
        if not post:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy bài viết")

        if post.status not in ["APPROVED", "SCHEDULED"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Chỉ những bài viết đã được Phê duyệt (APPROVED) mới được phép lên lịch đăng"
            )

        schedule = db.query(Schedule).filter(Schedule.post_id == post_id).first()
        if not schedule:
            schedule = Schedule(
                post_id=post_id,
                scheduled_time=schedule_in.scheduled_time,
                remind_before_minutes=schedule_in.remind_before_minutes,
                scheduled_by=current_user.user_id,
                schedule_status="ACTIVE"
            )
            db.add(schedule)
        else:
            schedule.scheduled_time = schedule_in.scheduled_time
            schedule.remind_before_minutes = schedule_in.remind_before_minutes
            schedule.schedule_status = "ACTIVE"
            schedule.is_reminded_30m = False
            schedule.is_reminded_10m = False
            schedule.is_reminded_ontime = False
            schedule.is_overdue_alerted = False

        post.status = "SCHEDULED"

        db.commit()
        db.refresh(schedule)
        return schedule
