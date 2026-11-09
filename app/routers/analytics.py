from typing import List, Dict, Any
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user, RoleGuard
from app.models.user import User
from app.schemas.analytics import PostStatisticCreate, PostStatisticResponse, DashboardResponse
from app.services.analytics_service import AnalyticsService

router = APIRouter(prefix="", tags=["MOD-07: Analytics & Reporting"])

@router.post(
    "/posts/{post_id}/statistics",
    response_model=PostStatisticResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Cập nhật chỉ số bài đăng (FR-14 & BR-08)",
    description="Nhập thủ công hoặc đồng bộ API chỉ số Reach, Views, Likes, Comments, Shares cho bài đã đăng."
)
def record_post_statistics(
    post_id: int,
    stat_in: PostStatisticCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return AnalyticsService.record_statistics(db, post_id, stat_in, current_user)

@router.get(
    "/analytics/dashboard",
    response_model=DashboardResponse,
    summary="Xem báo cáo tổng hợp hiệu quả đa kênh (FR-15)",
    description="Chỉ Marketing Manager có quyền truy cập tổng quan báo cáo và biểu đồ so sánh."
)
def get_dashboard(
    current_user: User = Depends(RoleGuard(["MANAGER"])),
    db: Session = Depends(get_db)
):
    return AnalyticsService.get_dashboard_summary(db)

@router.get(
    "/analytics/export",
    summary="Xuất báo cáo số liệu (FR-15 & NFR-01)",
    description="Trả về toàn bộ dữ liệu thống kê để kết xuất ra định dạng Excel hoặc PDF trong dưới 5 giây."
)
def export_analytics(
    current_user: User = Depends(RoleGuard(["MANAGER"])),
    db: Session = Depends(get_db)
):
    return AnalyticsService.export_report_data(db)
