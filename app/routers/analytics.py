from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, Query, Body, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user, RoleGuard
from app.models.user import User
from app.schemas.analytics import (
    PostStatisticCreate,
    MockSyncRequest,
    PostStatisticResponse,
    PostStatisticHistoryResponse,
    DashboardResponse,
)
from app.services.analytics_service import AnalyticsService

router = APIRouter(prefix="", tags=["MOD-07: Analytics & Reporting"])

@router.post(
    "/posts/{post_id}/statistics",
    response_model=PostStatisticResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Nhap thu cong chi so bai dang (FR-14 & BR-08)",
    description="Nhap thu cong chi so do luong Reach, Views, Likes, Comments, Shares cho bai viet da xuat ban (PUBLISHED). Kiem tra so nguyen >= 0 va luu nguon MANUAL."
)
def record_post_statistics(
    post_id: int,
    stat_in: PostStatisticCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Dam bao luon luu nguon MANUAL khi goi endpoint nhap tay
    if not stat_in.source_type:
        stat_in.source_type = "MANUAL"
    return AnalyticsService.record_statistics(db, post_id, stat_in, current_user)

@router.post(
    "/posts/{post_id}/statistics/sync-mock",
    response_model=PostStatisticResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Dong bo chi so qua Mock API (Goi y thuong +1 - FR-14)",
    description="Tu dong mo phong dong bo chi so bai dang qua Mock API. Tu dong sinh chi so hop ly theo nen tang va moc thoi gian, luu nguon API."
)
def sync_mock_statistics(
    post_id: int,
    mock_req: Optional[MockSyncRequest] = Body(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return AnalyticsService.sync_mock_statistics(db, post_id, current_user, mock_req)

@router.post(
    "/posts/{post_id}/statistics/simulate-milestones",
    response_model=List[PostStatisticResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Tao du lieu mau 3 moc 24h, 7 ngay, 30 ngay (FR-14)",
    description="Tu dong khoi tao tron bo 3 ban ghi chuan cac moc 24H, 7D, 30D cho bai viet da PUBLISHED de ho tro kiem thu va quay video demo ngan."
)
def simulate_milestones(
    post_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return AnalyticsService.simulate_milestones(db, post_id, current_user)

@router.get(
    "/posts/{post_id}/statistics/history",
    response_model=PostStatisticHistoryResponse,
    summary="Truy van lich su so lieu va cac moc 24h/7d/30d (FR-14)",
    description="Truy van toan bo lich su do luong cua bai viet, ho tro loc theo timeframe (24h/7d/30d/all), milestone (24H/7D/30D/CUSTOM), nguon (MANUAL/API). Tra ve bang tong hop cac moc va ty le tang truong."
)
def get_post_statistics_history(
    post_id: int,
    timeframe: Optional[str] = Query(None, description="Khoang thoi gian gan day: 24h, 7d, 30d, all"),
    milestone: Optional[str] = Query(None, description="Moc thoi gian: 24H, 7D, 30D, CUSTOM"),
    source_type: Optional[str] = Query(None, description="Nguon cap nhat: MANUAL, API"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return AnalyticsService.get_post_statistics_history(db, post_id, timeframe, milestone, source_type, current_user=current_user)

@router.get(
    "/posts/{post_id}/statistics/latest",
    response_model=PostStatisticResponse,
    summary="Lay chi so do luong moi nhat cua bai viet (FR-14)",
    description="Tra ve ban ghi chi so thong ke gan day nhat cua bai viet."
)
def get_latest_post_statistic(
    post_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return AnalyticsService.get_latest_post_statistic(db, post_id, current_user=current_user)

@router.get(
    "/analytics/dashboard",
    response_model=DashboardResponse,
    summary="Xem bao cao tong hop hieu qua da kenh (FR-15)",
    description="Chi Marketing Manager co quyen truy cap tong quan bao cao va bieu do so sanh."
)
def get_dashboard(
    current_user: User = Depends(RoleGuard(["MANAGER"])),
    db: Session = Depends(get_db)
):
    return AnalyticsService.get_dashboard_summary(db)

@router.get(
    "/analytics/export",
    summary="Xuat bao cao so lieu (FR-15 & NFR-01)",
    description="Tra ve toan bo du lieu thong ke de ket xuat ra dinh dang Excel hoac PDF trong duoi 5 giay."
)
def export_analytics(
    current_user: User = Depends(RoleGuard(["MANAGER"])),
    db: Session = Depends(get_db)
):
    return AnalyticsService.export_report_data(db)
