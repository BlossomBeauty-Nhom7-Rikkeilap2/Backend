from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import random
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.post import Post
from app.models.post_statistic import PostStatistic
from app.models.platform import Platform
from app.models.user import User
from app.schemas.analytics import (
    PostStatisticCreate,
    MockSyncRequest,
    PostStatisticResponse,
    PostStatisticHistoryItem,
    PostStatisticHistoryResponse,
    MilestonesSummary,
    GrowthRateSummary,
    DashboardResponse,
    PlatformSummary,
)

class AnalyticsService:
    @staticmethod
    def _validate_integer_metrics(reach: int, views: int, likes: int, comments: int, shares: int):
        """Kiem tra cac chi so phai la so nguyen khong am (>= 0)."""
        metrics = {
            "reach_count": reach,
            "view_count": views,
            "like_count": likes,
            "comment_count": comments,
            "share_count": shares,
        }
        for name, value in metrics.items():
            if not isinstance(value, int) or value < 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Chi so {name} phai la so nguyen khong am (>= 0). Gia tri nhan duoc: {value}"
                )

    @staticmethod
    def _infer_milestone(post: Post, recorded_at: datetime) -> str:
        """Tu dong xac dinh moc thoi gian (24H, 7D, 30D, CUSTOM) dua vao thoi diem xuat ban."""
        if not post.published_at:
            return "24H"

        diff_seconds = (recorded_at - post.published_at).total_seconds()
        diff_hours = max(0.0, diff_seconds / 3600.0)

        if diff_hours <= 24.0:
            return "24H"
        elif diff_hours <= 24.0 * 7.0:
            return "7D"
        elif diff_hours <= 24.0 * 30.0:
            return "30D"
        else:
            return "CUSTOM"

    @classmethod
    def record_statistics(
        cls,
        db: Session,
        post_id: int,
        stat_in: PostStatisticCreate,
        current_user: User
    ) -> PostStatistic:
        """Cap nhat so lieu bai dang thu cong (FR-14 & BR-08) - Chi cho phep khi Post da PUBLISHED."""
        post = db.query(Post).filter(Post.post_id == post_id, Post.deleted_at.is_(None)).first()
        if not post:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Khong tim thay bai viet")

        if post.status != "PUBLISHED":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Chi co the nhap so lieu thong ke cho bai viet da dang (PUBLISHED)"
            )

        # Kiem tra so nguyen >= 0
        cls._validate_integer_metrics(
            stat_in.reach_count,
            stat_in.view_count,
            stat_in.like_count,
            stat_in.comment_count,
            stat_in.share_count
        )

        now = datetime.now()
        milestone = stat_in.milestone or cls._infer_milestone(post, now)

        new_stat = PostStatistic(
            post_id=post_id,
            reach_count=stat_in.reach_count,
            view_count=stat_in.view_count,
            like_count=stat_in.like_count,
            comment_count=stat_in.comment_count,
            share_count=stat_in.share_count,
            source_type=stat_in.source_type,
            milestone=milestone,
            updated_by=current_user.user_id,
            recorded_at=now
        )
        db.add(new_stat)
        db.commit()
        db.refresh(new_stat)
        return new_stat

    @classmethod
    def sync_mock_statistics(
        cls,
        db: Session,
        post_id: int,
        current_user: User,
        mock_req: Optional[MockSyncRequest] = None
    ) -> PostStatistic:
        """Dong bo so lieu gia lap qua Mock API (Goi y thuong +1 - FR-14 & SDD 3.2.7).
        Tu dong sinh so lieu logic theo nen tang hoac nhan du lieu tu request.
        """
        post = db.query(Post).filter(Post.post_id == post_id, Post.deleted_at.is_(None)).first()
        if not post:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Khong tim thay bai viet")

        if post.status != "PUBLISHED":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Chi co the dong bo so lieu thong ke cho bai viet da dang (PUBLISHED)"
            )

        now = datetime.now()
        target_milestone = (mock_req.milestone if mock_req else None) or cls._infer_milestone(post, now)

        # Ty le nhan so lieu tang truong theo moc thoi gian
        scale_map = {
            "24H": 1.0,
            "7D": 3.2,
            "30D": 7.8,
            "CUSTOM": 2.0
        }
        scale = scale_map.get(target_milestone, 1.0)

        # Baseline theo nen tang
        base_views = random.randint(1800, 3600)
        base_reach = int(base_views * random.uniform(1.2, 1.5))
        base_likes = int(base_views * random.uniform(0.05, 0.09))
        base_comments = int(base_likes * random.uniform(0.12, 0.25))
        base_shares = int(base_likes * random.uniform(0.06, 0.18))

        reach = mock_req.reach_count if (mock_req and mock_req.reach_count is not None) else int(base_reach * scale)
        views = mock_req.view_count if (mock_req and mock_req.view_count is not None) else int(base_views * scale)
        likes = mock_req.like_count if (mock_req and mock_req.like_count is not None) else int(base_likes * scale)
        comments = mock_req.comment_count if (mock_req and mock_req.comment_count is not None) else int(base_comments * scale)
        shares = mock_req.share_count if (mock_req and mock_req.share_count is not None) else int(base_shares * scale)

        # Kiem tra so nguyen >= 0
        cls._validate_integer_metrics(reach, views, likes, comments, shares)

        new_stat = PostStatistic(
            post_id=post_id,
            reach_count=reach,
            view_count=views,
            like_count=likes,
            comment_count=comments,
            share_count=shares,
            source_type="API",
            milestone=target_milestone,
            updated_by=current_user.user_id,
            recorded_at=now
        )
        db.add(new_stat)
        db.commit()
        db.refresh(new_stat)
        return new_stat

    @classmethod
    def simulate_milestones(
        cls,
        db: Session,
        post_id: int,
        current_user: User
    ) -> List[PostStatistic]:
        """Tao bo 3 moc lich su (24h, 7 ngay, 30 ngay) chuan cho bai viet da PUBLISHED de demo va test."""
        post = db.query(Post).filter(Post.post_id == post_id, Post.deleted_at.is_(None)).first()
        if not post:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Khong tim thay bai viet")

        if post.status != "PUBLISHED":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Chi co the tao moc thong ke cho bai viet da dang (PUBLISHED)"
            )

        pub_time = post.published_at or (datetime.now() - timedelta(days=31))
        milestone_configs = [
            {
                "milestone": "24H",
                "recorded_at": pub_time + timedelta(hours=24),
                "reach": 3500,
                "views": 2800,
                "likes": 210,
                "comments": 35,
                "shares": 18,
                "source_type": "API"
            },
            {
                "milestone": "7D",
                "recorded_at": pub_time + timedelta(days=7),
                "reach": 11200,
                "views": 9400,
                "likes": 740,
                "comments": 115,
                "shares": 62,
                "source_type": "API"
            },
            {
                "milestone": "30D",
                "recorded_at": pub_time + timedelta(days=30),
                "reach": 26800,
                "views": 22500,
                "likes": 1850,
                "comments": 290,
                "shares": 145,
                "source_type": "API"
            }
        ]

        created_stats = []
        for cfg in milestone_configs:
            stat = PostStatistic(
                post_id=post_id,
                reach_count=cfg["reach"],
                view_count=cfg["views"],
                like_count=cfg["likes"],
                comment_count=cfg["comments"],
                share_count=cfg["shares"],
                source_type=cfg["source_type"],
                milestone=cfg["milestone"],
                updated_by=current_user.user_id,
                recorded_at=cfg["recorded_at"]
            )
            db.add(stat)
            created_stats.append(stat)

        db.commit()
        for s in created_stats:
            db.refresh(s)
        return created_stats

    @classmethod
    def get_post_statistics_history(
        cls,
        db: Session,
        post_id: int,
        timeframe: Optional[str] = None,
        milestone: Optional[str] = None,
        source_type: Optional[str] = None
    ) -> PostStatisticHistoryResponse:
        """Truy van lich su chi so do luong bai viet theo cac moc 24h/7d/30d va nguon MANUAL/API (FR-14)."""
        post = (
            db.query(Post)
            .filter(Post.post_id == post_id, Post.deleted_at.is_(None))
            .first()
        )
        if not post:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Khong tim thay bai viet")

        query = db.query(PostStatistic).filter(PostStatistic.post_id == post_id)

        # Loc theo nguon MANUAL / API
        if source_type:
            st = source_type.upper()
            if st in ["MANUAL", "API"]:
                query = query.filter(PostStatistic.source_type == st)

        # Loc theo moc thoi gian (24H, 7D, 30D, CUSTOM)
        if milestone:
            ms = milestone.upper()
            if ms in ["24H", "7D", "30D", "CUSTOM"]:
                query = query.filter(PostStatistic.milestone == ms)

        # Loc theo timeframe gan day
        now = datetime.now()
        if timeframe:
            tf = timeframe.lower()
            if tf == "24h":
                query = query.filter(PostStatistic.recorded_at >= now - timedelta(hours=24))
            elif tf == "7d":
                query = query.filter(PostStatistic.recorded_at >= now - timedelta(days=7))
            elif tf == "30d":
                query = query.filter(PostStatistic.recorded_at >= now - timedelta(days=30))

        records = query.order_by(PostStatistic.recorded_at.asc()).all()

        history_items: List[PostStatisticHistoryItem] = []
        for r in records:
            total_eng = r.like_count + r.comment_count + r.share_count
            eng_rate = round((total_eng / r.reach_count * 100), 2) if r.reach_count > 0 else 0.0
            hours_diff = None
            if post.published_at:
                hours_diff = round((r.recorded_at - post.published_at).total_seconds() / 3600.0, 1)

            history_items.append(
                PostStatisticHistoryItem(
                    stat_id=r.stat_id,
                    post_id=r.post_id,
                    reach_count=r.reach_count,
                    view_count=r.view_count,
                    like_count=r.like_count,
                    comment_count=r.comment_count,
                    share_count=r.share_count,
                    total_engagement=total_eng,
                    engagement_rate=eng_rate,
                    source_type=r.source_type,
                    milestone=r.milestone,
                    recorded_at=r.recorded_at,
                    updated_by=r.updated_by,
                    updater_name=r.updater.full_name if r.updater else None,
                    hours_since_published=hours_diff
                )
            )

        # Tinh toan moc tom tat: 24h, 7d, 30d va latest
        m24h_item: Optional[PostStatisticHistoryItem] = None
        m7d_item: Optional[PostStatisticHistoryItem] = None
        m30d_item: Optional[PostStatisticHistoryItem] = None
        latest_item: Optional[PostStatisticHistoryItem] = None

        for item in history_items:
            if item.milestone == "24H":
                m24h_item = item
            elif item.milestone == "7D":
                m7d_item = item
            elif item.milestone == "30D":
                m30d_item = item
        if history_items:
            latest_item = history_items[-1]

        # Tinh toan ty le tang truong (% growth)
        growth_rate = GrowthRateSummary()
        if m24h_item and m7d_item:
            r_g = round(((m7d_item.reach_count - m24h_item.reach_count) / max(1, m24h_item.reach_count)) * 100, 2)
            v_g = round(((m7d_item.view_count - m24h_item.view_count) / max(1, m24h_item.view_count)) * 100, 2)
            e_g = round(((m7d_item.total_engagement - m24h_item.total_engagement) / max(1, m24h_item.total_engagement)) * 100, 2)
            growth_rate.m24h_to_m7d = {
                "reach_growth_pct": r_g,
                "views_growth_pct": v_g,
                "engagement_growth_pct": e_g
            }

        if m7d_item and m30d_item:
            r_g2 = round(((m30d_item.reach_count - m7d_item.reach_count) / max(1, m7d_item.reach_count)) * 100, 2)
            v_g2 = round(((m30d_item.view_count - m7d_item.view_count) / max(1, m7d_item.view_count)) * 100, 2)
            e_g2 = round(((m30d_item.total_engagement - m7d_item.total_engagement) / max(1, m7d_item.total_engagement)) * 100, 2)
            growth_rate.m7d_to_m30d = {
                "reach_growth_pct": r_g2,
                "views_growth_pct": v_g2,
                "engagement_growth_pct": e_g2
            }

        return PostStatisticHistoryResponse(
            post_id=post.post_id,
            title=post.title,
            platform_name=post.platform.platform_name if post.platform else "Unknown",
            published_at=post.published_at,
            total_records=len(history_items),
            history=history_items,
            milestones=MilestonesSummary(
                m24h=m24h_item,
                m7d=m7d_item,
                m30d=m30d_item,
                latest=latest_item
            ),
            growth_rate=growth_rate
        )

    @staticmethod
    def get_latest_post_statistic(db: Session, post_id: int) -> PostStatistic:
        """Lay ban ghi so lieu do luong moi nhat cua bai viet."""
        post = db.query(Post).filter(Post.post_id == post_id, Post.deleted_at.is_(None)).first()
        if not post:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Khong tim thay bai viet")

        stat = (
            db.query(PostStatistic)
            .filter(PostStatistic.post_id == post_id)
            .order_by(PostStatistic.recorded_at.desc())
            .first()
        )
        if not stat:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Chua co so lieu thong ke nao cho bai viet nay"
            )
        return stat

    @staticmethod
    def _get_latest_stats_map(db: Session, post_ids: List[int]) -> Dict[int, PostStatistic]:
        """Lay ban ghi thong ke moi nhat cho danh sach post_id trong 1 truy van duy nhat (tranh N+1)."""
        if not post_ids:
            return {}

        # Subquery tim recorded_at lon nhat theo tung post_id
        latest_time_subq = (
            db.query(
                PostStatistic.post_id,
                func.max(PostStatistic.recorded_at).label("max_recorded_at")
            )
            .filter(PostStatistic.post_id.in_(post_ids))
            .group_by(PostStatistic.post_id)
            .subquery()
        )

        rows = (
            db.query(PostStatistic)
            .join(
                latest_time_subq,
                (PostStatistic.post_id == latest_time_subq.c.post_id)
                & (PostStatistic.recorded_at == latest_time_subq.c.max_recorded_at)
            )
            .order_by(PostStatistic.stat_id.asc())
            .all()
        )

        # Neu co 2 ban ghi cung recorded_at, giu ban ghi co stat_id lon nhat
        return {r.post_id: r for r in rows}

    @classmethod
    def get_dashboard_summary(cls, db: Session) -> DashboardResponse:
        """Tong hop bieu do phan tich da kenh (FR-15 & SDD 3.2.7)."""
        platforms = db.query(Platform).filter(Platform.is_active == True).all()
        published_posts = db.query(Post).filter(
            Post.status == "PUBLISHED",
            Post.deleted_at.is_(None)
        ).all()

        latest_stats_map = cls._get_latest_stats_map(db, [p.post_id for p in published_posts])
        posts_by_platform: Dict[int, List[Post]] = {}
        for p in published_posts:
            posts_by_platform.setdefault(p.platform_id, []).append(p)

        platform_summaries: List[PlatformSummary] = []
        grand_posts = 0
        grand_reach = 0
        grand_views = 0
        grand_engagement = 0

        for plat in platforms:
            posts = posts_by_platform.get(plat.platform_id, [])
            p_posts = len(posts)
            p_reach = 0
            p_views = 0
            p_likes = 0
            p_comments = 0
            p_shares = 0

            for p in posts:
                latest_stat = latest_stats_map.get(p.post_id)
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

    @classmethod
    def export_report_data(cls, db: Session) -> List[Dict[str, Any]]:
        """Xuat du lieu tho phuc vu ket xuat bao cao Excel/PDF (FR-15)."""
        posts = (
            db.query(Post, Platform, User)
            .join(Platform, Post.platform_id == Platform.platform_id)
            .join(User, Post.author_id == User.user_id)
            .filter(Post.status == "PUBLISHED", Post.deleted_at.is_(None))
            .all()
        )

        latest_stats_map = cls._get_latest_stats_map(db, [post.post_id for post, _, _ in posts])

        rows = []
        for post, platform, author in posts:
            latest_stat = latest_stats_map.get(post.post_id)
            rows.append({
                "post_id": post.post_id,
                "title": post.title,
                "platform": platform.platform_name,
                "author": author.full_name,
                "published_at": post.published_at.isoformat() if post.published_at else "",
                "published_url": post.published_url or "",
                "milestone": latest_stat.milestone if latest_stat else None,
                "source_type": latest_stat.source_type if latest_stat else "N/A",
                "reach": latest_stat.reach_count if latest_stat else 0,
                "views": latest_stat.view_count if latest_stat else 0,
                "likes": latest_stat.like_count if latest_stat else 0,
                "comments": latest_stat.comment_count if latest_stat else 0,
                "shares": latest_stat.share_count if latest_stat else 0,
            })
        return rows
