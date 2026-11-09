from datetime import datetime
from urllib.parse import urlparse
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.post import Post
from app.models.schedule import Schedule
from app.models.platform import Platform
from app.models.user import User

class TrackingService:
    PLATFORM_DOMAINS = {
        "FACEBOOK": ["facebook.com", "fb.com", "fb.watch"],
        "INSTAGRAM": ["instagram.com"],
        "TIKTOK": ["tiktok.com"]
    }

    @classmethod
    def confirm_published(cls, db: Session, post_id: int, published_url: str, current_user: User) -> Post:
        """
        Xác nhận đã đăng bài thủ công (BR-06 & SDD 3.2.6).
        Kiểm tra published_url hợp lệ với nền tảng đích.
        """
        post = db.query(Post).filter(Post.post_id == post_id, Post.deleted_at.is_(None)).first()
        if not post:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy bài viết")

        if post.status not in ["APPROVED", "SCHEDULED"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Chỉ có thể xác nhận đã đăng đối với bài viết ở trạng thái APPROVED hoặc SCHEDULED (hiện tại: {post.status})"
            )

        if not published_url or not published_url.strip():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Vui lòng cung cấp đường dẫn bài đăng thực tế (published_url)")

        # Kiểm tra tên miền khớp với nền tảng
        platform = db.query(Platform).filter(Platform.platform_id == post.platform_id).first()
        parsed_url = urlparse(published_url)
        hostname = parsed_url.hostname or ""

        expected_domains = cls.PLATFORM_DOMAINS.get(platform.platform_code, [])
        if not any(domain in hostname.lower() for domain in expected_domains):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Đường dẫn bài đăng không thuộc nền tảng {platform.platform_name} ({', '.join(expected_domains)})"
            )

        # Cập nhật trạng thái
        post.status = "PUBLISHED"
        post.published_url = published_url.strip()
        post.published_at = datetime.now()

        # Đánh dấu hoàn tất lịch đăng
        schedule = db.query(Schedule).filter(Schedule.post_id == post_id).first()
        if schedule:
            schedule.schedule_status = "COMPLETED"

        db.commit()
        db.refresh(post)
        return post
