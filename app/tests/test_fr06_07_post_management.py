import os
import sys
import unittest
from datetime import datetime, date

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi import HTTPException

from app.core.database import Base
import app.models  # noqa: F401
from app.models.role import Role
from app.models.user import User
from app.models.platform import Platform
from app.models.post import Post
from app.schemas.post import PostFilterParams
from app.services.post_service import PostService

class TestFR0607SoftDeleteAndPostList(unittest.TestCase):
    """
    Kiểm thử tự động FR-06/07: Xóa mềm & danh sách bài viết (Task T06A662)
    Bao phủ:
    - FR-06: Xóa mềm (Soft delete) bài viết ở trạng thái DRAFT / REJECTED (ghi nhận deleted_at, ẩn khỏi danh sách)
    - FR-06 (ERR-01 / BR-06): Chặn xóa bài viết ở trạng thái PENDING_APPROVAL, APPROVED, SCHEDULED, PUBLISHED
    - FR-07: Tìm kiếm từ khóa, lọc theo nền tảng, trạng thái, nhân viên (tác giả), ngày dự kiến đăng
    - FR-07 (NFR-01): Phân trang và phản hồi dưới 2 giây (< 2000ms)
    """

    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=self.engine)
        SessionTesting = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        self.db = SessionTesting()

        self.role_manager = Role(role_id=1, role_code="MANAGER", role_name="Marketing Manager")
        self.role_staff = Role(role_id=2, role_code="STAFF", role_name="Marketing Staff")
        self.db.add_all([self.role_manager, self.role_staff])

        self.manager = User(
            user_id=1,
            username="minhanh",
            email="minhanh@blossom.vn",
            password_hash="fakehash",
            full_name="Nguyễn Minh Anh",
            role_id=1,
            status="ACTIVE"
        )
        self.staff1 = User(
            user_id=2,
            username="halinh",
            email="halinh@blossom.vn",
            password_hash="fakehash",
            full_name="Nguyễn Hà Linh",
            role_id=2,
            status="ACTIVE"
        )
        self.staff2 = User(
            user_id=3,
            username="ngocmai",
            email="ngocmai@blossom.vn",
            password_hash="fakehash",
            full_name="Trần Ngọc Mai",
            role_id=2,
            status="ACTIVE"
        )
        self.db.add_all([self.manager, self.staff1, self.staff2])

        self.db.add_all([
            Platform(platform_id=1, platform_code="FACEBOOK", platform_name="Facebook Fanpage", is_active=True),
            Platform(platform_id=2, platform_code="INSTAGRAM", platform_name="Instagram Business", is_active=True),
            Platform(platform_id=3, platform_code="TIKTOK", platform_name="TikTok Official", is_active=True),
        ])
        self.db.commit()

        # Seed 6 bài viết đa dạng trạng thái, nền tảng, tác giả, ngày đăng
        self.posts_seed = [
            Post(
                post_id=123,
                title="Routine tối giản cho ngày bận rộn",
                caption="Chăm da tối giản cùng Blossom",
                hashtags="#MinimalRoutine",
                platform_id=3,
                author_id=self.staff2.user_id,
                planned_publish_time=datetime(2026, 11, 3, 9, 0),
                status="REJECTED"
            ),
            Post(
                post_id=124,
                title="Chống nắng mỗi ngày, nâng niu làn da",
                caption="Kem chống nắng phổ rộng",
                hashtags="#Sunscreen",
                platform_id=1,
                author_id=self.staff1.user_id,
                planned_publish_time=datetime(2026, 11, 8, 8, 0),
                status="SCHEDULED"
            ),
            Post(
                post_id=125,
                title="Chọn serum phù hợp với làn da của bạn",
                caption="Bí quyết chọn serum cấp ẩm",
                hashtags="#Serum #Skincare",
                platform_id=2,
                author_id=self.staff1.user_id,
                planned_publish_time=datetime(2026, 11, 7, 10, 0),
                status="DRAFT"
            ),
            Post(
                post_id=126,
                title="Một chút yêu thương cho làn da",
                caption="Dưỡng ẩm chuyên sâu",
                hashtags="#Hydration",
                platform_id=2,
                author_id=self.staff2.user_id,
                planned_publish_time=datetime(2026, 11, 6, 14, 0),
                status="APPROVED"
            ),
            Post(
                post_id=127,
                title="Bí quyết chăm da mùa hanh khô",
                caption="Giữ ẩm mùa thu đông",
                hashtags="#DrySkin",
                platform_id=1,
                author_id=self.staff2.user_id,
                planned_publish_time=datetime(2026, 11, 5, 8, 0),
                status="PENDING_APPROVAL"
            ),
            Post(
                post_id=128,
                title="5 bước dưỡng da cho buổi sáng rạng rỡ",
                caption="Routine buổi sáng rạng ngời",
                hashtags="#MorningGlow",
                platform_id=1,
                author_id=self.staff1.user_id,
                planned_publish_time=datetime(2026, 11, 4, 8, 0),
                status="PUBLISHED"
            ),
        ]
        self.db.add_all(self.posts_seed)
        self.db.commit()

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(bind=self.engine)
        self.engine.dispose()

    def test_tc01_soft_delete_draft_and_rejected_succeeds(self):
        """TC-01 (FR-06): Xóa mềm thành công bài viết DRAFT và REJECTED, cập nhật deleted_at và ẩn khỏi danh sách."""
        deleted_draft = PostService.delete_post(self.db, 125, self.staff1)
        self.assertIsNotNone(deleted_draft.deleted_at)

        deleted_rejected = PostService.delete_post(self.db, 123, self.staff2)
        self.assertIsNotNone(deleted_rejected.deleted_at)

        # Kiểm tra bản ghi vẫn còn trong DB (Soft Delete) nhưng bị ẩn khỏi danh sách mặc định
        visible_posts = PostService.get_posts(self.db, PostFilterParams(page=1, page_size=20), self.manager)
        visible_ids = [p.post_id for p in visible_posts]
        self.assertNotIn(125, visible_ids)
        self.assertNotIn(123, visible_ids)
        self.assertEqual(len(visible_ids), 4)

    def test_tc02_block_deleting_non_draft_or_rejected_posts_err01(self):
        """TC-02 (FR-06 ERR-01 / BR-06): Chặn xóa bài ở trạng thái PENDING_APPROVAL, APPROVED, SCHEDULED, PUBLISHED."""
        protected_ids = [124, 126, 127, 128]  # SCHEDULED, APPROVED, PENDING_APPROVAL, PUBLISHED
        for pid in protected_ids:
            with self.assertRaises(HTTPException) as ctx:
                PostService.delete_post(self.db, pid, self.manager)
            self.assertEqual(ctx.exception.status_code, 400)
            self.assertIn("ERR-01", ctx.exception.detail)

    def test_tc03_search_and_filter_by_platform_status_author_date(self):
        """TC-03 (FR-07): Tìm kiếm từ khóa và lọc chính xác theo nền tảng, trạng thái, nhân viên và ngày đăng."""
        # 1. Tìm kiếm theo từ khóa "serum"
        by_kw = PostService.get_posts(self.db, PostFilterParams(search="serum"), self.manager)
        self.assertEqual(len(by_kw), 1)
        self.assertEqual(by_kw[0].post_id, 125)

        # 2. Lọc theo nền tảng INSTAGRAM
        by_plat = PostService.get_posts(self.db, PostFilterParams(platform="INSTAGRAM"), self.manager)
        self.assertEqual({p.post_id for p in by_plat}, {125, 126})

        # 3. Lọc theo trạng thái PUBLISHED
        by_status = PostService.get_posts(self.db, PostFilterParams(status="PUBLISHED"), self.manager)
        self.assertEqual([p.post_id for p in by_status], [128])

        # 4. Lọc theo nhân viên "Trần Ngọc Mai"
        by_author = PostService.get_posts(self.db, PostFilterParams(author_name="Trần Ngọc Mai"), self.manager)
        self.assertEqual({p.post_id for p in by_author}, {123, 126, 127})

        # 5. Lọc theo ngày dự kiến đăng 2026-11-04
        by_date = PostService.get_posts(self.db, PostFilterParams(planned_date=date(2026, 11, 4)), self.manager)
        self.assertEqual([p.post_id for p in by_date], [128])

    def test_tc04_pagination_and_response_latency_under_2_seconds(self):
        """TC-04 (FR-07 & NFR-01): Phân trang chính xác và thời gian phản hồi < 2000ms."""
        res_p1 = PostService.get_posts_paginated(self.db, PostFilterParams(page=1, page_size=4), self.manager)
        self.assertEqual(res_p1["total"], 6)
        self.assertEqual(res_p1["total_pages"], 2)
        self.assertEqual(len(res_p1["items"]), 4)
        self.assertLess(res_p1["response_time_ms"], 2000.0)

        res_p2 = PostService.get_posts_paginated(self.db, PostFilterParams(page=2, page_size=4), self.manager)
        self.assertEqual(len(res_p2["items"]), 2)

if __name__ == "__main__":
    unittest.main()
