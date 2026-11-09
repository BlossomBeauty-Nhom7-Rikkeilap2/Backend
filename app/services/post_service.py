from typing import List, Optional
from datetime import datetime
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.models.post import Post
from app.models.platform import Platform
from app.models.user import User
from app.schemas.post import PostCreate, PostUpdate, PostFilterParams

class PostService:
    @staticmethod
    def get_posts(db: Session, filter_params: PostFilterParams, current_user: User) -> List[Post]:
        """Lọc và phân trang bài viết (bỏ qua các bài đã bị xóa mềm)."""
        query = db.query(Post).filter(Post.deleted_at.is_(None))

        # Phân quyền xem: Staff chỉ xem bài của mình hoặc bài đã duyệt (tùy nghiệp vụ)
        if filter_params.platform_id:
            query = query.filter(Post.platform_id == filter_params.platform_id)
        if filter_params.status:
            query = query.filter(Post.status == filter_params.status)
        if filter_params.author_id:
            query = query.filter(Post.author_id == filter_params.author_id)
        if filter_params.search:
            search_str = f"%{filter_params.search}%"
            query = query.filter(
                or_(
                    Post.title.ilike(search_str),
                    Post.caption.ilike(search_str),
                    Post.hashtags.ilike(search_str)
                )
            )

        offset = (filter_params.page - 1) * filter_params.page_size
        return query.order_by(Post.created_at.desc()).offset(offset).limit(filter_params.page_size).all()

    @staticmethod
    def get_post_by_id(db: Session, post_id: int) -> Post:
        post = db.query(Post).filter(Post.post_id == post_id, Post.deleted_at.is_(None)).first()
        if not post:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy bài viết")
        return post

    @staticmethod
    def create_post(db: Session, post_in: PostCreate, author_id: int) -> Post:
        # Kiểm tra nền tảng tồn tại
        platform = db.query(Platform).filter(Platform.platform_id == post_in.platform_id).first()
        if not platform or not platform.is_active:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Nền tảng đăng bài không hợp lệ")

        new_post = Post(
            title=post_in.title,
            caption=post_in.caption,
            hashtags=post_in.hashtags,
            platform_id=post_in.platform_id,
            author_id=author_id,
            media_type=post_in.media_type,
            media_files=post_in.media_files or [],
            total_media_size_bytes=post_in.total_media_size_bytes or 0,
            planned_publish_time=post_in.planned_publish_time,
            status="DRAFT"  # Mặc định khởi tạo ở trạng thái DRAFT theo SDD 3.3
        )
        db.add(new_post)
        db.commit()
        db.refresh(new_post)
        return new_post

    @staticmethod
    def update_post(db: Session, post_id: int, post_in: PostUpdate, current_user: User) -> Post:
        post = PostService.get_post_by_id(db, post_id)

        # Kiểm tra quyền: Chỉ tác giả hoặc Manager được phép sửa
        if current_user.role.role_code == "STAFF" and post.author_id != current_user.user_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Bạn chỉ có thể chỉnh sửa bài viết của chính mình")

        # Quy tắc chỉnh sửa theo BR-04 & SDD 3.2.3:
        # Nếu sửa bài đã APPROVED, hệ thống bắt buộc chuyển lại về PENDING_APPROVAL
        if post.status == "APPROVED":
            post.status = "PENDING_APPROVAL"
        elif post.status not in ["DRAFT", "REVISION_REQUESTED", "REJECTED"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Không thể chỉnh sửa bài viết đang ở trạng thái {post.status}"
            )

        if post_in.title is not None:
            post.title = post_in.title
        if post_in.caption is not None:
            post.caption = post_in.caption
        if post_in.hashtags is not None:
            post.hashtags = post_in.hashtags
        if post_in.platform_id is not None:
            post.platform_id = post_in.platform_id
        if post_in.media_type is not None:
            post.media_type = post_in.media_type
        if post_in.media_files is not None:
            post.media_files = post_in.media_files
        if post_in.total_media_size_bytes is not None:
            post.total_media_size_bytes = post_in.total_media_size_bytes
        if post_in.planned_publish_time is not None:
            post.planned_publish_time = post_in.planned_publish_time

        db.commit()
        db.refresh(post)
        return post

    @staticmethod
    def delete_post(db: Session, post_id: int, current_user: User) -> bool:
        """Xóa mềm (Soft Delete theo FR-06 & SDD 3.2.3) - chỉ áp dụng cho DRAFT hoặc REJECTED."""
        post = PostService.get_post_by_id(db, post_id)

        if current_user.role.role_code == "STAFF" and post.author_id != current_user.user_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Bạn chỉ có thể xóa bài viết của chính mình")

        if post.status not in ["DRAFT", "REJECTED"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Chỉ cho phép xóa bài viết ở trạng thái Nháp (Draft) hoặc Bị từ chối (Rejected)"
            )

        post.deleted_at = datetime.now()
        db.commit()
        return True
