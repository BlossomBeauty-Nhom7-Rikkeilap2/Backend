import io
from typing import Optional
from datetime import datetime
from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_manager
from app.models.user import User
from app.schemas.analytics import PostStatisticUpdate, AnalyticsDashboardResponse
from app.services.analytics_service import AnalyticsService

router = APIRouter(prefix="/analytics", tags=["MOD-07: Statistics & Reporting"])


@router.put(
    "/posts/{post_id}",
    summary="Cập nhật số liệu tương tác bài viết (FR-14)",
    description="Cập nhật Reach, Views, Likes, Comments, Shares cho bài viết đã Xuất bản (PUBLISHED)."
)
def update_post_statistics(
    post_id: int,
    stat_in: PostStatisticUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    stat = AnalyticsService.update_post_statistics(db, post_id, stat_in, current_user)
    return {
        "message": "Cập nhật số liệu tương tác thành công",
        "stat_id": stat.stat_id,
        "post_id": stat.post_id,
        "recorded_at": stat.recorded_at
    }


@router.get(
    "/dashboard",
    response_model=AnalyticsDashboardResponse,
    summary="Dashboard báo cáo thống kê hiệu quả đa kênh (FR-15 - T06A66D)",
    description="Tổng hợp KPI, so sánh 3 kênh (Facebook, Instagram, Threads), xu hướng 12 tháng và bảng xếp hạng Top bài viết theo bộ lọc thời gian/nền tảng/nhân sự."
)
def get_analytics_dashboard(
    start_date: Optional[datetime] = Query(None, description="Từ ngày (ISO-8601)"),
    end_date: Optional[datetime] = Query(None, description="Đến ngày (ISO-8601)"),
    platform_id: Optional[int] = Query(None, description="ID nền tảng"),
    platform: Optional[str] = Query(None, description="Tên nền tảng (Facebook, Instagram, Threads, ALL)"),
    author_id: Optional[int] = Query(None, description="ID nhân sự/tác giả"),
    author_name: Optional[str] = Query(None, description="Tên nhân sự/tác giả"),
    current_user: User = Depends(require_manager),
    db: Session = Depends(get_db)
):
    return AnalyticsService.get_dashboard_summary(
        db=db,
        start_date=start_date,
        end_date=end_date,
        platform_id=platform_id,
        platform=platform,
        author_id=author_id,
        author_name=author_name,
    )


@router.get(
    "/export",
    summary="Xuất báo cáo thống kê ra file Excel / CSV / PDF < 5 giây (FR-15 - T06A66D)",
    description="Tải xuống báo cáo tổng hợp định dạng CSV, Excel (.xlsx) hoặc PDF (.pdf) trong thời gian dưới 5 giây (NFR-02)."
)
def export_analytics_report(
    format: str = Query("csv", description="Định dạng xuất: csv | excel | xlsx | pdf"),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    platform_id: Optional[int] = Query(None),
    platform: Optional[str] = Query(None),
    author_id: Optional[int] = Query(None),
    author_name: Optional[str] = Query(None),
    current_user: User = Depends(require_manager),
    db: Session = Depends(get_db)
):
    file_bytes, media_type, filename, elapsed_ms = AnalyticsService.export_report(
        db=db,
        export_format=format,
        start_date=start_date,
        end_date=end_date,
        platform_id=platform_id,
        platform=platform,
        author_id=author_id,
        author_name=author_name,
    )
    return StreamingResponse(
        io.BytesIO(file_bytes),
        media_type=media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Export-Time-Ms": str(elapsed_ms),
        }
    )
