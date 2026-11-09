from fastapi import APIRouter, Depends, Body
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.schemas.post import PostResponse
from app.services.tracking_service import TrackingService

router = APIRouter(prefix="/posts", tags=["MOD-06: Progress Tracking"])

@router.patch(
    "/{post_id}/publish",
    response_model=PostResponse,
    summary="Xác nhận đã đăng bài thủ công (FR-13 & BR-06)",
    description="Nhân viên xác nhận bài viết đã được đăng lên mạng xã hội, cung cấp URL thực tế để kiểm tra tên miền."
)
def confirm_publish(
    post_id: int,
    published_url: str = Body(..., embed=True),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return TrackingService.confirm_published(db, post_id, published_url, current_user)
