from typing import List, Optional, Dict, Any
from datetime import datetime, time
import time as perf_time
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import or_, func

from app.models.post import Post
from app.models.platform import Platform
from app.models.user import User
from app.schemas.post import PostCreate, PostUpdate, PostFilterParams

class PostService:
    @staticmethod
    def _build_filtered_query(db: Session, filter_params: PostFilterParams):
        query = db.query(Post)
        if not filter_params.include_deleted:
            query = query.filter(Post.deleted_at.is_(None))

        if filter_params.platform_id:
            query = query.filter(Post.platform_id == filter_params.platform_id)
        elif filter_params.platform:
            p_code = filter_params.platform.strip().upper()
            query = query.join(Platform).filter(
                or_(
                    func.upper(Platform.platform_code) == p_code,
                    Platform.platform_name.ilike(f"%{filter_params.platform.strip()}%")
                )
            )

        if filter_params.status:
            query = query.filter(func.upper(Post.status) == filter_params.status.strip().upper())

        if filter_params.author_id:
            query = query.filter(Post.author_id == filter_params.author_id)
        elif filter_params.author_name:
            kw_author = f"%{filter_params.author_name.strip()}%"
            query = query.join(User, Post.author_id == User.user_id).filter(
                or_(
                    User.full_name.ilike(kw_author),
                    User.username.ilike(kw_author)
                )
            )

        if filter_params.planned_date:
            start_dt = datetime.combine(filter_params.planned_date, time.min)
            end_dt = datetime.combine(filter_params.planned_date, time.max)
            query = query.filter(
                Post.planned_publish_time >= start_dt,
                Post.planned_publish_time <= end_dt
            )
        else:
            if filter_params.date_from:
                query = query.filter(Post.planned_publish_time >= filter_params.date_from)
            if filter_params.date_to:
                query = query.filter(Post.planned_publish_time <= filter_params.date_to)

        if filter_params.search:
            search_str = f"%{filter_params.search.strip()}%"
            query = query.filter(
                or_(
                    Post.title.ilike(search_str),
                    Post.caption.ilike(search_str),
                    Post.hashtags.ilike(search_str)
                )
            )
        return query

    @staticmethod
    def get_posts(db: Session, filter_params: PostFilterParams, current_user: Optional[User] = None) -> List[Post]:
        """
        Lọc, tìm kiếm và phân trang danh sách bài viết (FR-07 & NFR-01 < 2 giây).
        Mặc định bỏ qua các bài viết đã bị xóa mềm (deleted_at IS NOT NULL).
        """
        query = PostService._build_filtered_query(db, filter_params)
        page = max(1, filter_params.page)
        page_size = max(1, min(100, filter_params.page_size))
        offset = (page - 1) * page_size
        return query.order_by(Post.updated_at.desc(), Post.post_id.desc()).offset(offset).limit(page_size).all()

    @staticmethod
    def get_posts_paginated(db: Session, filter_params: PostFilterParams, current_user: Optional[User] = None) -> Dict[str, Any]:
        """Trả về danh sách bài viết kèm metadata phân trang và thời gian phản hồi (< 2000ms)."""
        t0 = perf_time.perf_counter()
        query = PostService._build_filtered_query(db, filter_params)
        total = query.count()
        page = max(1, filter_params.page)
        page_size = max(1, min(100, filter_params.page_size))
        total_pages = max(1, (total + page_size - 1) // page_size)
        offset = (page - 1) * page_size
        items = query.order_by(Post.updated_at.desc(), Post.post_id.desc()).offset(offset).limit(page_size).all()
        elapsed_ms = round((perf_time.perf_counter() - t0) * 1000.0, 2)
        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
            "response_time_ms": elapsed_ms
        }

    @staticmethod
    def get_post_by_id(db: Session, post_id: int) -> Post:
        post = db.query(Post).filter(Post.post_id == post_id, Post.deleted_at.is_(None)).first()
        if not post:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy bài viết")
        return post

    @staticmethod
    def create_post(db: Session, post_in: PostCreate, author_id: int) -> Post:
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
            status="DRAFT"
        )
        db.add(new_post)
        db.commit()
        db.refresh(new_post)
        return new_post

    @staticmethod
    def update_post(db: Session, post_id: int, post_in: PostUpdate, current_user: User) -> Post:
        post = PostService.get_post_by_id(db, post_id)

        if current_user.role and current_user.role.role_code == "STAFF" and post.author_id != current_user.user_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Bạn chỉ có thể chỉnh sửa bài viết của chính mình")

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
    def delete_post(db: Session, post_id: int, current_user: User) -> Post:
        """
        Xóa mềm bài viết (Soft Delete theo FR-06, BR-06 & SDD 3.2.3):
        - Chỉ áp dụng cho bài viết ở trạng thái DRAFT hoặc REJECTED.
        - Nghiêm cấm xóa bài viết ở trạng thái PENDING_APPROVAL, APPROVED, SCHEDULED hoặc PUBLISHED (ERR-01).
        - Cập nhật trường deleted_at = NOW() thay vì xóa cứng.
        """
        post = PostService.get_post_by_id(db, post_id)

        if current_user.role and current_user.role.role_code == "STAFF" and post.author_id != current_user.user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Bạn chỉ có thể xóa bài viết của chính mình"
            )

        if post.status not in ("DRAFT", "REJECTED"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"[ERR-01] Không thể xóa bài viết đang ở trạng thái {post.status}. Chỉ cho phép xóa mềm bài viết ở trạng thái Nháp (Draft) hoặc Bị từ chối (Rejected)."
            )

        post.deleted_at = datetime.now()
        post.updated_at = datetime.now()
        db.commit()
        db.refresh(post)
        return post
