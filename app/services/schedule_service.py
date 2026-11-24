from datetime import datetime
from typing import List, Dict, Any, Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.schedule import Schedule
from app.models.post import Post
from app.models.platform import Platform
from app.models.user import User
from app.schemas.schedule import ScheduleUpdate

class ScheduleService:
    @staticmethod
    def get_calendar(
        db: Session,
        start_date: datetime,
        end_date: datetime,
        current_user: Optional[User] = None
    ) -> List[Dict[str, Any]]:
        """Lấy danh sách sự kiện trên Content Calendar theo khoảng thời gian (FR-11)."""
        query = (
            db.query(Schedule, Post, Platform, User)
            .join(Post, Schedule.post_id == Post.post_id)
            .join(Platform, Post.platform_id == Platform.platform_id)
            .join(User, Post.author_id == User.user_id)
            .filter(
                Schedule.scheduled_time >= start_date,
                Schedule.scheduled_time <= end_date,
                Schedule.schedule_status.in_(["ACTIVE", "COMPLETED"]),
                Post.deleted_at.is_(None)
            )
        )

        # Staff chỉ xem lịch đăng của bài viết do mình phụ trách
        if current_user and current_user.role and current_user.role.role_code == "STAFF":
            query = query.filter(Post.author_id == current_user.user_id)

        schedules = query.order_by(Schedule.scheduled_time.asc()).all()

        results = []
        for sched, post, platform, author in schedules:
            results.append({
                "schedule_id": sched.schedule_id,
                "post_id": post.post_id,
                "title": post.title,
                "platform_name": platform.platform_name,
                "color_hex": platform.color_hex,
                "scheduled_time": sched.scheduled_time,
                "schedule_status": sched.schedule_status,
                "post_status": post.status,
                "author_name": author.full_name,
                "author_username": author.username
            })
        return results

    @staticmethod
    def update_schedule(db: Session, post_id: int, schedule_in: ScheduleUpdate, current_user: User) -> Schedule:
        """
        Lên lịch hoặc điều chỉnh giờ đăng bài (FR-11).
        Chỉ cho phép khi Post đang ở trạng thái APPROVED hoặc SCHEDULED.
        """
        post = db.query(Post).filter(Post.post_id == post_id, Post.deleted_at.is_(None)).first()
        if not post:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy bài viết")

        if current_user.role and current_user.role.role_code == "STAFF" and post.author_id != current_user.user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Bạn chỉ có thể điều chỉnh lịch đăng cho bài viết của chính mình"
            )

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
            # Reset lại cờ nhắc nhở khi dời giờ
            schedule.is_reminded_30m = False
            schedule.is_reminded_10m = False
            schedule.is_reminded_ontime = False
            schedule.is_overdue_alerted = False

        # Chuyển trạng thái Post sang SCHEDULED và đồng bộ planned_publish_time (SDD 3.3)
        post.status = "SCHEDULED"
        post.planned_publish_time = schedule_in.scheduled_time

        db.commit()
        db.refresh(schedule)
        return schedule
