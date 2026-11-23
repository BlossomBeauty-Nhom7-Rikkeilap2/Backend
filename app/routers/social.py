from typing import Dict, Any, Optional
from urllib.parse import urlparse
from fastapi import APIRouter, Depends, Query, Body, HTTPException, status
from sqlalchemy.orm import Session

from app.config import settings
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.models.post import Post
from app.schemas.analytics import PostStatisticCreate, PostStatisticResponse
from app.services.facebook_service import FacebookGraphService, ThreadsGraphService
from app.services.analytics_service import AnalyticsService

router = APIRouter(prefix="/social", tags=["Social Media Integration (Facebook, Instagram & Threads)"])

# ==============================================================================
# FACEBOOK & INSTAGRAM GRAPH API INTEGRATION ENDPOINTS
# ==============================================================================

@router.get(
    "/facebook/login-url",
    summary="Lấy URL đăng nhập Meta OAuth 2.0 (Facebook & Instagram)",
    description="Tạo đường dẫn xác thực với Meta/Facebook để cấp quyền quản lý Fanpage và tài khoản Instagram Business."
)
def get_facebook_login_url(
    redirect_uri: str = Query("http://localhost:5500/oauth/facebook/callback", description="Địa chỉ callback của Frontend"),
    current_user: User = Depends(get_current_user)
):
    url = FacebookGraphService.get_authorization_url(redirect_uri=redirect_uri, state=str(current_user.user_id))
    return {
        "oauth_url": url,
        "redirect_uri": redirect_uri
    }

@router.post(
    "/facebook/exchange-token",
    summary="Đổi mã Code lấy Long-lived Access Token (60 ngày)",
    description="Nhận authorization code từ frontend sau khi người dùng đăng nhập Facebook thành công và đổi lấy Token dài hạn."
)
def exchange_facebook_code(
    code: str = Body(..., embed=True),
    redirect_uri: str = Body("http://localhost:5500/oauth/facebook/callback", embed=True),
    current_user: User = Depends(get_current_user)
):
    token_data = FacebookGraphService.exchange_code_for_token(code, redirect_uri)
    if not token_data.get("success"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Lỗi xác thực với Facebook: {token_data.get('error', 'Unknown error')}"
        )
    return token_data

@router.get(
    "/accounts",
    summary="Lấy danh sách Trang Facebook và tài khoản Instagram Business liên kết",
    description="Truy vấn toàn bộ các Fanpage và Instagram Business Account mà người dùng quản lý cùng Page Access Token."
)
def get_managed_accounts(
    user_access_token: str = Query(..., description="User Access Token lấy được từ bước đăng nhập OAuth"),
    current_user: User = Depends(get_current_user)
):
    pages = FacebookGraphService.get_managed_pages(user_access_token)
    return {"data": pages}

def _extract_id_from_url(published_url: Optional[str]) -> Optional[str]:
    if not published_url:
        return None
    path = urlparse(published_url).path.strip("/")
    if not path:
        return None
    return path.split("/")[-1] or None


@router.post(
    "/posts/{post_id}/sync-facebook",
    response_model=PostStatisticResponse,
    summary="Tự động đồng bộ số liệu từ Facebook Graph API (FR-14 & BR-08)",
    description="Gọi trực tiếp Graph API để lấy Reach, Views, Likes, Comments, Shares và lưu vào bảng post_statistics với source_type='API'."
)
def sync_facebook_post_statistics(
    post_id: int,
    fb_post_id: Optional[str] = Body(None, embed=True, description="ID bài đăng trên Facebook (mặc định trích từ published_url)"),
    access_token: Optional[str] = Body(None, embed=True, description="Page Access Token (mặc định dùng cấu hình .env)"),
    milestone: Optional[str] = Body(None, embed=True, description="Mốc thời gian (24H, 7D, 30D, CUSTOM)"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    post = db.query(Post).filter(Post.post_id == post_id, Post.deleted_at.is_(None)).first()
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy bài viết")

    resolved_id = (fb_post_id or _extract_id_from_url(post.published_url) or "").strip()
    resolved_token = (access_token or settings.FB_PAGE_ACCESS_TOKEN or "").strip()
    if not resolved_id or not resolved_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Thiếu fb_post_id hoặc FB_PAGE_ACCESS_TOKEN để đồng bộ dữ liệu Facebook"
        )

    metrics = FacebookGraphService.get_facebook_post_insights(resolved_id, resolved_token)
    if not metrics.get("success"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Không thể lấy dữ liệu từ Facebook: {metrics.get('error', 'Unknown error')}"
        )

    stat_in = PostStatisticCreate(
        reach_count=metrics["reach_count"],
        view_count=metrics["view_count"],
        like_count=metrics["like_count"],
        comment_count=metrics["comment_count"],
        share_count=metrics["share_count"],
        source_type="API",
        milestone=milestone
    )
    return AnalyticsService.record_statistics(db, post_id, stat_in, current_user)

@router.post(
    "/posts/{post_id}/sync-instagram",
    response_model=PostStatisticResponse,
    summary="Tự động đồng bộ số liệu từ Instagram Graph API (FR-14 & BR-08)",
    description="Gọi trực tiếp Instagram Graph API để lấy Reach, Impressions, Likes, Comments và lưu vào bảng post_statistics với source_type='API'."
)
def sync_instagram_post_statistics(
    post_id: int,
    ig_media_id: Optional[str] = Body(None, embed=True, description="ID bài đăng (Media ID) trên Instagram"),
    access_token: Optional[str] = Body(None, embed=True, description="Access Token (mặc định dùng cấu hình .env)"),
    milestone: Optional[str] = Body(None, embed=True, description="Mốc thời gian (24H, 7D, 30D, CUSTOM)"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    post = db.query(Post).filter(Post.post_id == post_id, Post.deleted_at.is_(None)).first()
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy bài viết")

    resolved_id = (ig_media_id or _extract_id_from_url(post.published_url) or "").strip()
    resolved_token = (access_token or settings.IG_ACCESS_TOKEN or "").strip()
    if not resolved_id or not resolved_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Thiếu ig_media_id hoặc IG_ACCESS_TOKEN để đồng bộ dữ liệu Instagram"
        )

    metrics = FacebookGraphService.get_instagram_media_insights(resolved_id, resolved_token)
    if not metrics.get("success"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Không thể lấy dữ liệu từ Instagram: {metrics.get('error', 'Unknown error')}"
        )

    stat_in = PostStatisticCreate(
        reach_count=metrics["reach_count"],
        view_count=metrics["view_count"],
        like_count=metrics["like_count"],
        comment_count=metrics["comment_count"],
        share_count=metrics["share_count"],
        source_type="API",
        milestone=milestone
    )
    return AnalyticsService.record_statistics(db, post_id, stat_in, current_user)

@router.post(
    "/posts/{post_id}/sync-threads",
    response_model=PostStatisticResponse,
    summary="Tự động đồng bộ số liệu từ Threads Graph API (FR-14 & BR-08)",
    description="Gọi trực tiếp Threads Graph API để lấy Views, Likes, Replies, Reposts và lưu vào bảng post_statistics với source_type='API'."
)
def sync_threads_post_statistics(
    post_id: int,
    threads_media_id: Optional[str] = Body(None, embed=True, description="ID bài đăng trên Threads"),
    access_token: Optional[str] = Body(None, embed=True, description="Threads User Access Token (mặc định dùng cấu hình .env)"),
    milestone: Optional[str] = Body(None, embed=True, description="Mốc thời gian (24H, 7D, 30D, CUSTOM)"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    post = db.query(Post).filter(Post.post_id == post_id, Post.deleted_at.is_(None)).first()
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy bài viết")

    resolved_id = (threads_media_id or _extract_id_from_url(post.published_url) or "").strip()
    resolved_token = (access_token or settings.THREADS_ACCESS_TOKEN or "").strip()
    if not resolved_id or not resolved_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Thiếu threads_media_id hoặc THREADS_ACCESS_TOKEN để đồng bộ dữ liệu Threads"
        )

    metrics = ThreadsGraphService.get_threads_insights(resolved_id, resolved_token)
    if not metrics.get("success"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Không thể lấy dữ liệu từ Threads: {metrics.get('error', 'Unknown error')}"
        )

    stat_in = PostStatisticCreate(
        reach_count=metrics["reach_count"],
        view_count=metrics["view_count"],
        like_count=metrics["like_count"],
        comment_count=metrics["comment_count"],
        share_count=metrics["share_count"],
        source_type="API",
        milestone=milestone
    )
    return AnalyticsService.record_statistics(db, post_id, stat_in, current_user)

@router.post(
    "/posts/{post_id}/sync-mock",
    response_model=PostStatisticResponse,
    summary="Đồng bộ số liệu mô phỏng qua Mock API (FR-14 & Gợi ý thưởng +1)",
    description="Mô phỏng đồng bộ chỉ số đo lường API cho bài viết Facebook, Instagram hoặc Threads mà không cần Token thật."
)
def sync_social_mock_statistics(
    post_id: int,
    milestone: Optional[str] = Body(None, embed=True, description="Mốc thời gian (24H, 7D, 30D, CUSTOM)"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    from app.schemas.analytics import MockSyncRequest
    mock_req = MockSyncRequest(milestone=milestone) if milestone else None
    return AnalyticsService.sync_mock_statistics(db, post_id, current_user, mock_req)
