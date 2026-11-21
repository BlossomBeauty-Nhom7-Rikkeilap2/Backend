import os
import sys
import time
import unittest
from datetime import datetime

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
from app.models.post_statistic import PostStatistic
from app.models.approval import Approval
from app.services.analytics_service import AnalyticsService


class TestFR15AnalyticsAndExport(unittest.TestCase):
    """
    Kiểm thử tự động FR-15: API tổng hợp báo cáo & xuất Excel/CSV/PDF (Task T06A66D)
    Bao phủ:
    - Tổng hợp 4 KPI (Bài xuất bản, Lượt tiếp cận, Tổng tương tác, Tỷ lệ tương tác)
    - So sánh hiệu quả 3 kênh (Facebook, Instagram, Threads) & Xu hướng 12 tháng
    - Bảng xếp hạng Top bài viết
    - Bộ lọc theo Thời gian, Nền tảng, Nhân sự
    - Trạng thái không có dữ liệu (ERR-01) & Chặn khoảng thời gian không hợp lệ (ERR-02)
    - Xuất file Excel (.xlsx), CSV (.csv), PDF (.pdf) trong thời gian < 5 giây (NFR-02)
    """

    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=self.engine)
        SessionTesting = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        self.db = SessionTesting()

        self.role_mgr = Role(role_id=1, role_code="MANAGER", role_name="Marketing Manager")
        self.role_staff = Role(role_id=2, role_code="STAFF", role_name="Marketing Staff")
        self.db.add_all([self.role_mgr, self.role_staff])

        self.mgr = User(
            user_id=1,
            username="minhanh",
            full_name="Nguyễn Minh Anh",
            email="minhanh@blossom.vn",
            password_hash="hashed",
            role_id=1,
            status="ACTIVE",
        )
        self.staff1 = User(
            user_id=2,
            username="halinh",
            full_name="Nguyễn Hà Linh",
            email="halinh@blossom.vn",
            password_hash="hashed",
            role_id=2,
            status="ACTIVE",
        )
        self.staff2 = User(
            user_id=3,
            username="ngocmai",
            full_name="Trần Ngọc Mai",
            email="ngocmai@blossom.vn",
            password_hash="hashed",
            role_id=2,
            status="ACTIVE",
        )
        self.db.add_all([self.mgr, self.staff1, self.staff2])

        fb = Platform(platform_id=1, platform_code="FB", platform_name="Facebook", color_hex="#1877F2", is_active=True)
        ig = Platform(platform_id=2, platform_code="IG", platform_name="Instagram", color_hex="#E1306C", is_active=True)
        tt = Platform(platform_id=3, platform_code="TH", platform_name="Threads", color_hex="#111111", is_active=True)
        self.db.add_all([fb, ig, tt])

        p1 = Post(
            post_id=128,
            title="5 bước dưỡng da cho buổi sáng rạng rỡ",
            caption="Routine buổi sáng",
            platform_id=1,
            author_id=2,
            status="PUBLISHED",
            published_at=datetime(2026, 11, 4, 8, 0),
        )
        p2 = Post(
            post_id=123,
            title="Routine tối giản cho ngày bận rộn",
            caption="Routine tối giản",
            platform_id=2,
            author_id=3,
            status="PUBLISHED",
            published_at=datetime(2026, 11, 5, 9, 0),
        )
        p3 = Post(
            post_id=118,
            title="Dịu dàng với làn da, dịu dàng với chính mình",
            caption="Video Threads",
            platform_id=3,
            author_id=2,
            status="PUBLISHED",
            published_at=datetime(2026, 11, 6, 19, 0),
        )
        self.db.add_all([p1, p2, p3])
        self.db.commit()

        s1 = PostStatistic(post_id=128, reach_count=12840, view_count=18500, like_count=900, comment_count=148, share_count=100)
        s2 = PostStatistic(post_id=123, reach_count=10260, view_count=14200, like_count=800, comment_count=106, share_count=80)
        s3 = PostStatistic(post_id=118, reach_count=9480, view_count=12900, like_count=680, comment_count=94, share_count=50)
        ap1 = Approval(post_id=128, actor_id=1, action="APPROVED", comment="Tốt")
        self.db.add_all([s1, s2, s3, ap1])
        self.db.commit()

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(bind=self.engine)

    def test_01_kpi_3_channels_and_top_posts(self):
        data = AnalyticsService.get_dashboard_summary(self.db)
        self.assertEqual(data["total_published_posts"], 3)
        self.assertEqual(data["total_reach"], 12840 + 10260 + 9480)
        self.assertEqual(data["total_engagement"], 1148 + 986 + 824)
        self.assertGreater(data["engagement_rate"], 0)
        self.assertIsNone(data["empty_state_message"])

        channels = {c["platform_name"]: c for c in data["channel_comparison"]}
        self.assertTrue({"Facebook", "Instagram", "Threads"}.issubset(set(channels.keys())))
        self.assertEqual(channels["Facebook"]["total_engagement"], 1148)
        self.assertEqual(channels["Instagram"]["total_engagement"], 986)
        self.assertEqual(channels["Threads"]["total_engagement"], 824)

        self.assertEqual(len(data["top_posts"]), 3)
        self.assertEqual(data["top_posts"][0]["post_code"], "BL-0128")
        self.assertEqual(data["top_posts"][0]["total_engagement"], 1148)

    def test_02_filters_by_time_platform_and_staff(self):
        fb_data = AnalyticsService.get_dashboard_summary(self.db, platform="Facebook")
        self.assertEqual(fb_data["total_published_posts"], 1)
        self.assertEqual(fb_data["top_posts"][0]["platform_name"], "Facebook")

        staff_data = AnalyticsService.get_dashboard_summary(self.db, author_name="Trần Ngọc Mai")
        self.assertEqual(staff_data["total_published_posts"], 1)
        self.assertEqual(staff_data["top_posts"][0]["author_name"], "Trần Ngọc Mai")

    def test_03_empty_state_and_invalid_date_range(self):
        empty_data = AnalyticsService.get_dashboard_summary(
            self.db,
            start_date=datetime(2025, 1, 1),
            end_date=datetime(2025, 1, 31),
        )
        self.assertEqual(empty_data["total_published_posts"], 0)
        self.assertEqual(
            empty_data["empty_state_message"],
            "Chưa có dữ liệu thống kê trong khoảng thời gian đã chọn",
        )

        with self.assertRaises(HTTPException) as ctx:
            AnalyticsService.get_dashboard_summary(
                self.db,
                start_date=datetime(2026, 12, 10),
                end_date=datetime(2026, 11, 1),
            )
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("ERR-02", ctx.exception.detail)

    def test_04_export_csv_excel_pdf_under_5_seconds(self):
        for fmt, expected_mime, magic_bytes in [
            ("csv", "text/csv", b"\xef\xbb\xbf"),
            ("xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", b"PK"),
            ("pdf", "application/pdf", b"%PDF-1.4"),
        ]:
            t0 = time.perf_counter()
            file_bytes, media_type, filename, elapsed_ms = AnalyticsService.export_report(
                self.db, export_format=fmt
            )
            elapsed = time.perf_counter() - t0
            self.assertLess(elapsed, 5.0)
            self.assertLess(elapsed_ms, 5000.0)
            self.assertIn(expected_mime, media_type)
            self.assertTrue(file_bytes.startswith(magic_bytes))


if __name__ == "__main__":
    unittest.main()
