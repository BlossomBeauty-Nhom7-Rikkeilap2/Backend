from typing import List, Optional
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.schemas.schedule import ScheduleUpdate, CalendarEventResponse
from app.services.schedule_service import ScheduleService

router = APIRouter(prefix="/schedules", tags=["MOD-05: Scheduling & Calendar"])

@router.get(
    "/calendar",
    response_model=List[CalendarEventResponse],
    summary="Xem dữ liệu Content Calendar đa kênh (FR-11)",
    description="Lấy danh sách các bài viết đã duyệt và lên lịch theo Ngày/Tuần/Tháng."
)
def get_calendar(
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Mặc định lấy trong vòng 30 ngày tới nếu không truyền tham số
    start = start_date or (datetime.now() - timedelta(days=7))
    end = end_date or (datetime.now() + timedelta(days=30))
    return ScheduleService.get_calendar(db, start, end)

@router.put(
    "/{post_id}",
    summary="Lên lịch hoặc dời khung giờ đăng (FR-11 & SDD 3.3)",
    description="Chỉ áp dụng cho bài viết đã được duyệt (APPROVED). Chuyển trạng thái sang SCHEDULED."
)
def update_schedule(
    post_id: int,
    schedule_in: ScheduleUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    sched = ScheduleService.update_schedule(db, post_id, schedule_in, current_user)
    return {
        "message": "Cập nhật lịch đăng thành công",
        "schedule_id": sched.schedule_id,
        "post_id": sched.post_id,
        "scheduled_time": sched.scheduled_time
    }
