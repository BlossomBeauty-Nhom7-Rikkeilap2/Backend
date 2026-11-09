from datetime import datetime
from typing import Dict, Any, List
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.post import Post
from app.models.post_statistic import PostStatistic
from app.models.platform import Platform
from app.models.user import User
from app.schemas.analytics import PostStatisticCreate, DashboardResponse, PlatformSummary

class AnalyticsService:
    @staticmethod
    def record_statistics(db: Session, post_id: int, stat_in: PostStatisticCreate, current_user: User) -> PostStatistic:
        """Cập nhật số liệu bài đăng (FR-14 & BR-08) - Chỉ cho phép khi Post đã PUBLISHED."""
        post = db.query(Post).filter(Post.post_id == post_id, Post.deleted_at.is_(None)).first()
        if not post:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy bài viết")

        if post.status != "PUBLISHED":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Chỉ có thể nhập số liệu thống kê cho bài viết đã đăng (PUBLISHED)"
            )

        new_stat = PostStatistic(
            post_id=post_id,
            reach_count=stat_in.reach_count,
            view_count=stat_in.view_count,
            like_count=stat_in.like_count,
            comment_count=stat_in.comment_count,
            share_count=stat_in.share_count,
            source_type=stat_in.source_type,
            updated_by=current_user.user_id,
            recorded_at=datetime.now()
        )
        db.add(new_stat)
        db.commit()
        db.refresh(new_stat)
        return new_stat

    @staticmethod
    def get_dashboard_summary(db: Session) -> DashboardResponse:
        """Tổng hợp biểu đồ phân tích đa kênh (FR-15 & SDD 3.2.7)."""
        platforms = db.query(Platform).filter(Platform.is_active == True).all()
        platform_summaries: List[PlatformSummary] = []

        grand_posts = 0
        grand_reach = 0
        grand_views = 0
        grand_engagement = 0

        for plat in platforms:
            # Lấy danh sách post đã published của platform này
            posts = db.query(Post).filter(
                Post.platform_id == plat.platform_id,
                Post.status == "PUBLISHED",
                Post.deleted_at.is_(None)
            ).all()

            p_posts = len(posts)
            p_reach = 0
            p_views = 0
            p_likes = 0
            p_comments = 0
            p_shares = 0

            for p in posts:
                # Lấy bản ghi thống kê mới nhất
                latest_stat = (
                    db.query(PostStatistic)
                    .filter(PostStatistic.post_id == p.post_id)
                    .order_by(PostStatistic.recorded_at.desc())
                    .first()
                )
                if latest_stat:
                    p_reach += latest_stat.reach_count
                    p_views += latest_stat.view_count
                    p_likes += latest_stat.like_count
                    p_comments += latest_stat.comment_count
                    p_shares += latest_stat.share_count

            grand_posts += p_posts
            grand_reach += p_reach
            grand_views += p_views
            grand_engagement += (p_likes + p_comments + p_shares)

            platform_summaries.append(
                PlatformSummary(
                    platform_name=plat.platform_name,
                    total_posts=p_posts,
                    total_reach=p_reach,
                    total_views=p_views,
                    total_likes=p_likes,
                    total_comments=p_comments,
                    total_shares=p_shares
                )
            )

        return DashboardResponse(
            total_published_posts=grand_posts,
            total_reach=grand_reach,
            total_views=grand_views,
            total_engagement=grand_engagement,
            platforms=platform_summaries
        )

    @staticmethod
    def export_report_data(db: Session) -> List[Dict[str, Any]]:
        """Xuất dữ liệu thô phục vụ kết xuất báo cáo Excel/PDF (FR-15)."""
        posts = (
            db.query(Post, Platform, User)
            .join(Platform, Post.platform_id == Platform.platform_id)
            .join(User, Post.author_id == User.user_id)
            .filter(Post.status == "PUBLISHED", Post.deleted_at.is_(None))
            .all()
        )

        rows = []
        for post, platform, author in posts:
            latest_stat = (
                db.query(PostStatistic)
                .filter(PostStatistic.post_id == post.post_id)
                .order_by(PostStatistic.recorded_at.desc())
                .first()
            )
            rows.append({
                "post_id": post.post_id,
                "title": post.title,
                "platform": platform.platform_name,
                "author": author.full_name,
                "published_at": post.published_at.isoformat() if post.published_at else "",
                "published_url": post.published_url or "",
                "reach": latest_stat.reach_count if latest_stat else 0,
                "views": latest_stat.view_count if latest_stat else 0,
                "likes": latest_stat.like_count if latest_stat else 0,
                "comments": latest_stat.comment_count if latest_stat else 0,
                "shares": latest_stat.share_count if latest_stat else 0,
            })
        return rows
