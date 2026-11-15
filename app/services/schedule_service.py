from datetime import datetime
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
        """Lấy danh sách sự kiện trên Content Calendar theo khoảng thời gian (FR-11)."""
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

        results = []
        for sched, post, platform in schedules:
            results.append({
                "schedule_id": sched.schedule_id,
                "post_id": post.post_id,
                "title": post.title,
                "platform_name": platform.platform_name,
                "color_hex": platform.color_hex,
                "scheduled_time": sched.scheduled_time,
                "schedule_status": sched.schedule_status,
                "post_status": post.status
            })
        return results

    @staticmethod
    def update_schedule(db: Session, post_id: int, schedule_in: ScheduleUpdate, current_user: User) -> Schedule:
        """
        Lên lịch hoặc điều chỉnh giờ đăng bài (FR-11 Task T06A665).
        - Chỉ cho phép khi Post đang ở trạng thái APPROVED hoặc SCHEDULED.
        - Chặn giờ quá khứ (ERR-02).
        - Cảnh báo xung đột < 30 phút cùng nền tảng (ERR-03).
        - Reset cờ nhắc nhở khi dời giờ (is_reminded_30m, is_reminded_10m, is_overdue_alerted).
        """
        post = db.query(Post).filter(Post.post_id == post_id, Post.deleted_at.is_(None)).first()
        if not post:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy bài viết")

        # 1. Chặn lên lịch cho bài viết chưa được duyệt (FR-11 & SDD 3.3)
        if post.status not in ["APPROVED", "SCHEDULED"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="[ERR-01] Chỉ những bài viết đã được Phê duyệt (APPROVED) mới được phép lên lịch đăng"
            )

        # 2. Chặn thời gian lên lịch trong quá khứ (FR-11)
        if schedule_in.scheduled_time <= datetime.now():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="[ERR-02] Thời gian dự kiến đăng bài phải lớn hơn thời điểm hiện tại (nằm trong tương lai)"
            )

        # 3. Quét kiểm tra xung đột thời gian < 30 phút trên cùng một nền tảng (FR-11)
        existing_schedules = (
            db.query(Schedule, Post)
            .join(Post, Schedule.post_id == Post.post_id)
            .filter(
                Post.platform_id == post.platform_id,
                Schedule.post_id != post_id,
                Schedule.schedule_status == "ACTIVE",
                Post.deleted_at.is_(None)
            )
            .all()
        )

        for existing_sched, existing_post in existing_schedules:
            diff_minutes = abs((existing_sched.scheduled_time - schedule_in.scheduled_time).total_seconds()) / 60
            if diff_minutes < 30:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        f"[ERR-03] Xung đột lịch đăng: Đã có bài viết '{existing_post.title}' được lên lịch lúc "
                        f"{existing_sched.scheduled_time.strftime('%Y-%m-%d %H:%M:%S')} trên cùng nền tảng. "
                        f"Khoảng cách tối thiểu giữa 2 bài đăng phải là 30 phút (khoảng cách hiện tại: {int(diff_minutes)} phút)."
                    )
                )

        schedule = db.query(Schedule).filter(Schedule.post_id == post_id).first()
        if not schedule:
            schedule = Schedule(
                post_id=post_id,
                scheduled_time=schedule_in.scheduled_time,
                remind_before_minutes=schedule_in.remind_before_minutes,
                scheduled_by=current_user.user_id,
                schedule_status="ACTIVE",
                is_reminded_30m=False,
                is_reminded_10m=False,
                is_overdue_alerted=False
            )
            db.add(schedule)
        else:
            schedule.scheduled_time = schedule_in.scheduled_time
            schedule.remind_before_minutes = schedule_in.remind_before_minutes
            schedule.schedule_status = "ACTIVE"
            # 4. Reset lại cờ nhắc nhở khi dời giờ (FR-11)
            schedule.is_reminded_30m = False
            schedule.is_reminded_10m = False
            schedule.is_overdue_alerted = False

        # Chuyển trạng thái Post sang SCHEDULED theo Post State Machine (SDD 3.3)
        post.status = "SCHEDULED"

        db.commit()
        db.refresh(schedule)
        return schedule
