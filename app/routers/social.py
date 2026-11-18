from typing import Dict, Any, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, Query, Body, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.models.post import Post
from app.schemas.analytics import PostStatisticCreate, PostStatisticResponse
from app.services.facebook_service import FacebookGraphService
from app.services.tiktok_service import TikTokApiService
from app.services.threads_service import ThreadsApiService
from app.services.analytics_service import AnalyticsService

router = APIRouter(prefix="/social", tags=["Social Media Integration (Facebook, Instagram, Threads & TikTok)"])

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

@router.post(
    "/posts/{post_id}/sync-facebook",
    response_model=PostStatisticResponse,
    summary="Tự động đồng bộ số liệu từ Facebook Graph API (FR-14 & BR-08)",
    description="Gọi trực tiếp Graph API để lấy Reach, Views, Likes, Comments, Shares và lưu vào bảng post_statistics với source_type='API'."
)
def sync_facebook_post_statistics(
    post_id: int,
    fb_post_id: str = Body(..., embed=True, description="ID bài đăng trên Facebook (dạng {page_id}_{post_id})"),
    access_token: str = Body(..., embed=True, description="Page Access Token hoặc User Access Token"),
    milestone: Optional[str] = Body(None, embed=True, description="Mốc thời gian (24H, 7D, 30D, CUSTOM)"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    post = db.query(Post).filter(Post.post_id == post_id, Post.deleted_at.is_(None)).first()
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy bài viết")

    metrics = FacebookGraphService.get_facebook_post_insights(fb_post_id, access_token)
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
    ig_media_id: str = Body(..., embed=True, description="ID bài đăng (Media ID) trên Instagram"),
    access_token: str = Body(..., embed=True, description="Page Access Token của Trang liên kết với tài khoản Instagram"),
    milestone: Optional[str] = Body(None, embed=True, description="Mốc thời gian (24H, 7D, 30D, CUSTOM)"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    post = db.query(Post).filter(Post.post_id == post_id, Post.deleted_at.is_(None)).first()
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy bài viết")

    metrics = FacebookGraphService.get_instagram_media_insights(ig_media_id, access_token)
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

# ==============================================================================
# TIKTOK OPEN API V2 INTEGRATION ENDPOINTS
# ==============================================================================

@router.get(
    "/tiktok/login-url",
    summary="Lấy URL đăng nhập TikTok OAuth 2.0 (Login Kit v2)",
    description="Tạo đường dẫn xác thực với TikTok for Developers để cấp quyền đọc video và phân tích chỉ số."
)
def get_tiktok_login_url(
    redirect_uri: str = Query("http://localhost:5500/oauth/tiktok/callback", description="Địa chỉ callback của Frontend"),
    current_user: User = Depends(get_current_user)
):
    url = TikTokApiService.get_authorization_url(redirect_uri=redirect_uri, state=str(current_user.user_id))
    return {
        "oauth_url": url,
        "redirect_uri": redirect_uri
    }

@router.post(
    "/tiktok/exchange-token",
    summary="Đổi mã Code lấy TikTok Access Token & Refresh Token",
    description="Nhận authorization code từ frontend sau khi người dùng đăng nhập TikTok thành công và đổi lấy Token."
)
def exchange_tiktok_code(
    code: str = Body(..., embed=True),
    redirect_uri: str = Body("http://localhost:5500/oauth/tiktok/callback", embed=True),
    current_user: User = Depends(get_current_user)
):
    token_data = TikTokApiService.exchange_code_for_token(code, redirect_uri)
    if not token_data.get("success"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Lỗi xác thực với TikTok: {token_data.get('error', 'Unknown error')}"
        )
    return token_data

@router.post(
    "/posts/{post_id}/sync-tiktok",
    response_model=PostStatisticResponse,
    summary="Tự động đồng bộ số liệu video từ TikTok Open API (FR-14 & BR-08)",
    description="Gọi trực tiếp TikTok API v2 để lấy Lượt xem, Thích, Bình luận, Chia sẻ và lưu vào CSDL với source_type='API'."
)
def sync_tiktok_video_statistics(
    post_id: int,
    video_id: str = Body(..., embed=True, description="ID của Video trên kênh TikTok"),
    access_token: str = Body(..., embed=True, description="User Access Token của tài khoản TikTok liên kết"),
    milestone: Optional[str] = Body(None, embed=True, description="Mốc thời gian (24H, 7D, 30D, CUSTOM)"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    post = db.query(Post).filter(Post.post_id == post_id, Post.deleted_at.is_(None)).first()
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy bài viết")

    metrics = TikTokApiService.get_video_insights(video_id, access_token)
    if not metrics.get("success"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Không thể lấy dữ liệu từ TikTok: {metrics.get('error', 'Unknown error')}"
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

# ==============================================================================
# THREADS API INTEGRATION ENDPOINTS (Meta Threads Graph API v1.0)
# ==============================================================================

@router.get(
    "/threads/login-url",
    summary="Lay URL dang nhap Meta Threads OAuth 2.0",
    description="Tao duong dan xac thuc OAuth voi Threads de cap quyen dang bai va truy van chi so tuong tac."
)
def get_threads_login_url(
    redirect_uri: str = Query("http://localhost:5500/oauth/threads/callback", description="Dia chi callback cua Frontend"),
    current_user: User = Depends(get_current_user)
):
    url = ThreadsApiService.get_authorization_url(redirect_uri=redirect_uri, state=str(current_user.user_id))
    return {
        "oauth_url": url,
        "redirect_uri": redirect_uri
    }

@router.post(
    "/threads/exchange-token",
    summary="Doi ma Code lay Threads Long-lived Access Token (60 ngay)",
    description="Nhan authorization code tu frontend sau khi nguoi dung dang nhap Threads va doi lay Token dai han 60 ngay."
)
def exchange_threads_code(
    code: str = Body(..., embed=True),
    redirect_uri: str = Body("http://localhost:5500/oauth/threads/callback", embed=True),
    current_user: User = Depends(get_current_user)
):
    token_data = ThreadsApiService.exchange_code_for_token(code, redirect_uri)
    if not token_data.get("success"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Loi xac thuc voi Threads API: {token_data.get('error', 'Unknown error')}"
        )
    return token_data

@router.post(
    "/threads/refresh-token",
    summary="Lam moi Threads Long-lived Access Token",
    description="Lam moi Access Token truoc khi het han 60 ngay."
)
def refresh_threads_token(
    access_token: str = Body(..., embed=True),
    current_user: User = Depends(get_current_user)
):
    ref_data = ThreadsApiService.refresh_access_token(access_token)
    if not ref_data.get("success"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Khong the lam moi token Threads: {ref_data.get('error', 'Unknown error')}"
        )
    return ref_data

@router.get(
    "/threads/profile",
    summary="Lay thong tin ho so tai khoan Threads",
    description="Truy van thong tin nguoi dung Threads bao gom ID, ten dang nhap va anh dai dien."
)
def get_threads_profile(
    access_token: str = Query(..., description="Threads Access Token"),
    current_user: User = Depends(get_current_user)
):
    profile_data = ThreadsApiService.get_user_profile(access_token)
    if not profile_data.get("success"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Khong the lay thong tin ho so Threads: {profile_data.get('error', 'Unknown error')}"
        )
    return profile_data

@router.post(
    "/posts/{post_id}/publish-threads",
    summary="Xuat ban bai viet len kenh Threads (FR-13)",
    description="Goi Threads API tao Media Container va dang truc tiep len tai khoan Threads."
)
def publish_to_threads(
    post_id: int,
    user_id: str = Body(..., embed=True, description="Threads User ID cua tai khoan"),
    access_token: str = Body(..., embed=True, description="Threads User Access Token"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    post = db.query(Post).filter(Post.post_id == post_id, Post.deleted_at.is_(None)).first()
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Khong tim thay bai viet")

    caption = (post.caption or post.title or "").strip()
    if post.hashtags:
        caption += f"\n\n{post.hashtags}"

    import json
    media_url = None
    if post.media_files:
        try:
            files = json.loads(post.media_files) if isinstance(post.media_files, str) else post.media_files
            if isinstance(files, list) and len(files) > 0:
                media_url = files[0]
        except Exception:
            media_url = None

    res = ThreadsApiService.publish_threads_post(
        user_id=user_id,
        access_token=access_token,
        text=caption,
        media_url=media_url,
        media_type=post.media_type
    )

    if not res.get("success"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Khong the dang bai len Threads: {res.get('error', 'Unknown error')}"
        )

    # Cap nhat post sang PUBLISHED
    now = datetime.now()
    post.status = "PUBLISHED"
    post.published_at = now
    post.published_url = res.get("permalink") or f"https://www.threads.net/t/{res.get('threads_post_id')}"
    db.commit()

    return {
        "success": True,
        "post_id": post.post_id,
        "threads_post_id": res.get("threads_post_id"),
        "published_url": post.published_url
    }

@router.post(
    "/posts/{post_id}/sync-threads",
    response_model=PostStatisticResponse,
    summary="Tu dong dong bo so lieu tu Threads API (FR-14 & BR-08)",
    description="Goi Threads Insights API de lay luot xem, thich, tra loi, dang lai va luu vao CSDL voi source_type='API'."
)
def sync_threads_statistics(
    post_id: int,
    threads_media_id: str = Body(..., embed=True, description="ID bai dang tren Threads"),
    access_token: str = Body(..., embed=True, description="Threads Access Token"),
    milestone: Optional[str] = Body(None, embed=True, description="Moc thoi gian (24H, 7D, 30D, CUSTOM)"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    post = db.query(Post).filter(Post.post_id == post_id, Post.deleted_at.is_(None)).first()
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Khong tim thay bai viet")

    metrics = ThreadsApiService.get_threads_insights(threads_media_id, access_token)
    if not metrics.get("success"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Khong the lay du lieu tu Threads: {metrics.get('error', 'Unknown error')}"
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
    description="Mô phỏng đồng bộ chỉ số đo lường API cho bài viết Facebook, Instagram, Threads hoặc TikTok mà không cần Token thật."
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
