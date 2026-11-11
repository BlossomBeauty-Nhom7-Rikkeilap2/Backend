from typing import List, Optional
from fastapi import APIRouter, Depends, UploadFile, File, Query, status, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.schemas.post import PostCreate, PostUpdate, PostResponse, PostFilterParams
from app.services.post_service import PostService
from app.services.media_service import MediaUploadService

router = APIRouter(prefix="/posts", tags=["MOD-03: Content & Media Management"])

@router.get(
    "",
    response_model=List[PostResponse],
    summary="Lấy danh sách bài viết (FR-07)",
    description="Hỗ trợ lọc theo nền tảng, trạng thái, tác giả và tìm kiếm từ khóa."
)
def get_posts(
    platform_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    author_id: Optional[int] = Query(None),
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    filter_params = PostFilterParams(
        platform_id=platform_id,
        status=status,
        author_id=author_id,
        search=search,
        page=page,
        page_size=page_size
    )
    return PostService.get_posts(db, filter_params, current_user)

@router.get(
    "/{post_id}",
    response_model=PostResponse,
    summary="Xem chi tiết bài viết (FR-07)"
)
def get_post(
    post_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return PostService.get_post_by_id(db, post_id)

@router.post(
    "",
    response_model=PostResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Tạo bài viết mới (FR-04)",
    description="Khởi tạo bài viết ở trạng thái Nháp (DRAFT) kèm tệp media."
)
def create_post(
    post_in: PostCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return PostService.create_post(db, post_in, current_user.user_id)

@router.put(
    "/{post_id}",
    response_model=PostResponse,
    summary="Chỉnh sửa nội dung bài viết (FR-05 & BR-04)",
    description="Nếu bài viết đã ở trạng thái APPROVED, hệ thống sẽ tự động chuyển về PENDING_APPROVAL để duyệt lại."
)
def update_post(
    post_id: int,
    post_in: PostUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return PostService.update_post(db, post_id, post_in, current_user)

@router.delete(
    "/{post_id}",
    status_code=status.HTTP_200_OK,
    summary="Xóa mềm bài viết (FR-06)",
    description="Chỉ cho phép xóa bài viết ở trạng thái DRAFT hoặc REJECTED."
)
def delete_post(
    post_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    PostService.delete_post(db, post_id, current_user)
    return {"message": "Đã xóa bài viết thành công", "status": "success"}

@router.post(
    "/upload-media",
    summary="Tải lên tệp Media ảnh hoặc video (SDD 3.2.3)",
    description="Kiểm tra giới hạn kích thước (Ảnh ≤ 10MB, Video ≤ 50MB) và lưu trữ tệp."
)
async def upload_media(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user)
):
    file_url, file_size, media_type = await MediaUploadService.validate_and_save(file)
    return {
        "file_url": file_url,
        "file_size_bytes": file_size,
        "media_type": media_type,
        "filename": file.filename
    }

@router.post(
    "/{post_id}/auto-publish",
    summary="Tự động xuất bản bài viết ngay lập tức qua API (100% tự động)",
    description="Gọi trực tiếp API Facebook/Instagram để đăng bài tự động, chuyển trạng thái sang PUBLISHED."
)
async def auto_publish_post(
    post_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    from app.services.auto_publish_service import AutoPublishService
    result = await AutoPublishService.publish_post_now(db, post_id, current_user)
    if not result.get("success"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.get("error", "Không thể tự động xuất bản")
        )
    return result
