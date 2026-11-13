from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, Query, Body, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.models.post import Post
from app.models.platform import Platform
from app.schemas.analytics import PostStatisticCreate, PostStatisticResponse
from app.services.facebook_service import FacebookGraphService
from app.services.tiktok_service import TikTokApiService
from app.services.analytics_service import AnalyticsService
from app.config import settings

router = APIRouter(prefix="/social", tags=["Social Media Integration (Facebook, Instagram & TikTok)"])

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
        source_type="API"
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
        source_type="API"
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
        source_type="API"
    )
    return AnalyticsService.record_statistics(db, post_id, stat_in, current_user)

# ==============================================================================
# TỰ ĐỘNG HÓA ĐỒNG BỘ CHỈ SỐ MẠNG XÃ HỘI (UNIFIED SYNC API)
# ==============================================================================

@router.post(
    "/posts/{post_id}/sync",
    response_model=PostStatisticResponse,
    summary="Tự động đồng bộ số liệu mạng xã hội cho bài viết (Facebook, Instagram, TikTok)",
    description="Tự động nhận diện nền tảng bài viết, sử dụng external_post_id và token đã cấu hình để đồng bộ chỉ số thật qua API."
)
def sync_post_statistics_auto(
    post_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    post = db.query(Post).filter(Post.post_id == post_id, Post.deleted_at.is_(None)).first()
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy bài viết")

    platform = db.query(Platform).filter(Platform.platform_id == post.platform_id).first()
    platform_code = (platform.platform_code if platform else "FACEBOOK").upper()

    external_id = post.external_post_id
    if not external_id and post.published_url:
        parts = [p for p in post.published_url.split('/') if p]
        if parts:
            external_id = parts[-1]

    if not external_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Bài viết #{post_id} chưa có mã định danh bài đăng bên ngoài (external_post_id). Vui lòng xuất bản bài viết qua hệ thống trước khi đồng bộ."
        )

    # 1. FACEBOOK
    if "FACEBOOK" in platform_code:
        page_id = settings.FB_PAGE_ID
        access_token = settings.FB_PAGE_ACCESS_TOKEN
        if platform and platform.oauth_config and isinstance(platform.oauth_config, dict):
            page_id = platform.oauth_config.get("page_id") or page_id
            access_token = platform.oauth_config.get("page_access_token") or access_token

        if not access_token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Chưa cấu hình Facebook Page Access Token để đồng bộ chỉ số."
            )

        metrics = FacebookGraphService.get_facebook_post_insights(external_id, access_token)
        if not metrics.get("success"):
            err_msg = metrics.get("error", {})
            err_detail = err_msg.get("message", "Lỗi Facebook Graph API") if isinstance(err_msg, dict) else str(err_msg)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Không thể lấy dữ liệu từ Facebook Graph API: {err_detail}"
            )

    # 2. INSTAGRAM
    elif "INSTAGRAM" in platform_code:
        access_token = settings.IG_ACCESS_TOKEN or settings.FB_PAGE_ACCESS_TOKEN
        if platform and platform.oauth_config and isinstance(platform.oauth_config, dict):
            access_token = platform.oauth_config.get("access_token") or access_token

        if not access_token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Chưa cấu hình Instagram Access Token để đồng bộ chỉ số."
            )

        metrics = FacebookGraphService.get_instagram_media_insights(external_id, access_token)
        if not metrics.get("success"):
            err_msg = metrics.get("error", {})
            err_detail = err_msg.get("message", "Lỗi Instagram Graph API") if isinstance(err_msg, dict) else str(err_msg)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Không thể lấy dữ liệu từ Instagram Graph API: {err_detail}"
            )

    # 3. TIKTOK
    elif "TIKTOK" in platform_code:
        access_token = None
        if platform and platform.oauth_config and isinstance(platform.oauth_config, dict):
            access_token = platform.oauth_config.get("access_token")

        if not access_token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Chưa có TikTok Access Token (tài khoản TikTok chưa kết nối OAuth) để đồng bộ chỉ số."
            )

        # Nếu external_id là publish_id (bắt đầu bằng v_pub_), thử tra cứu status để lấy video_id thật
        video_id = external_id
        if external_id.startswith("v_pub_"):
            try:
                st_res = TikTokApiService.get_publish_status(external_id, access_token)
                data_b = st_res.get("data", {})
                p_ids = data_b.get("publicaly_available_post_id") or data_b.get("post_ids") or data_b.get("post_id")
                if p_ids:
                    resolved_id = str(p_ids[0]) if isinstance(p_ids, list) and len(p_ids) > 0 else str(p_ids)
                    video_id = resolved_id
                    post.external_post_id = resolved_id
                    db.commit()
            except Exception:
                pass

        metrics = TikTokApiService.get_video_insights(video_id, access_token)
        if not metrics.get("success"):
            err_msg = metrics.get("error", "Lỗi TikTok Open API")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Không thể lấy dữ liệu từ TikTok Open API: {err_msg}"
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Nền tảng '{platform_code}' không hỗ trợ đồng bộ chỉ số tự động."
        )

    stat_in = PostStatisticCreate(
        reach_count=metrics.get("reach_count", 0),
        view_count=metrics.get("view_count", 0),
        like_count=metrics.get("like_count", 0),
        comment_count=metrics.get("comment_count", 0),
        share_count=metrics.get("share_count", 0),
        source_type="API"
    )
    return AnalyticsService.record_statistics(db, post_id, stat_in, current_user)
