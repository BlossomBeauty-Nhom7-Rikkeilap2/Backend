from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, Query, Body, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.models.post import Post
from app.schemas.analytics import PostStatisticCreate, PostStatisticResponse
from app.services.facebook_service import FacebookGraphService
from app.services.analytics_service import AnalyticsService

router = APIRouter(prefix="/social", tags=["Social Media Integration (Facebook & Instagram)"])

@router.get(
    "/facebook/login-url",
    summary="Lấy URL đăng nhập Meta OAuth 2.0 (Facebook & Instagram)",
    description="Tạo đường dẫn xác thực với Meta/Facebook để cấp quyền quản lý Fanpage và tài khoản Instagram Business."
)
def get_facebook_login_url(
    redirect_uri: str = Query("http://localhost:3000/oauth/facebook/callback", description="Địa chỉ callback của Frontend"),
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
    redirect_uri: str = Body("http://localhost:3000/oauth/facebook/callback", embed=True),
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
