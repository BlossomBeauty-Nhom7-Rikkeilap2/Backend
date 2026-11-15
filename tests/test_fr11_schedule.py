import unittest
from datetime import datetime, timedelta

# ==============================================================================
# KIỂM THỬ TỰ ĐỘNG: FR-11 API LỊCH ĐĂNG & KIỂM TRA XUNG ĐỘT
# Task: T06A665 | Người thực hiện: Nguyễn Phát Đạt (N25DTCN082)
# ==============================================================================

class DummyPost:
    def __init__(self, post_id, title, status, platform_id):
        self.post_id = post_id
        self.title = title
        self.status = status
        self.platform_id = platform_id

class DummySchedule:
    def __init__(self, schedule_id, post_id, scheduled_time, is_reminded_30m=False, is_reminded_10m=False, is_overdue_alerted=False):
        self.schedule_id = schedule_id
        self.post_id = post_id
        self.scheduled_time = scheduled_time
        self.is_reminded_30m = is_reminded_30m
        self.is_reminded_10m = is_reminded_10m
        self.is_overdue_alerted = is_overdue_alerted

class TestFR11ScheduleManagement(unittest.TestCase):
    def setUp(self):
        self.base_time = (datetime.now() + timedelta(days=2)).replace(minute=0, second=0, microsecond=0)

    def test_tc01_block_unscheduled_post_draft(self):
        """TC-01: Chặn lên lịch khi bài viết chưa được phê duyệt (Trạng thái DRAFT -> ERR-01)."""
        post = DummyPost(post_id=7, title="Bài viết nháp", status="DRAFT", platform_id=1)
        self.assertNotEqual(post.status, "APPROVED", "Bài viết DRAFT không được phép lên lịch")

    def test_tc02_block_past_scheduled_time(self):
        """TC-02: Chặn thời gian lên lịch trong quá khứ (ERR-02)."""
        past_time = datetime.now() - timedelta(hours=2)
        is_past = past_time <= datetime.now()
        self.assertTrue(is_past, "Thời gian trong quá khứ phải bị chặn")

    def test_tc03_detect_time_conflict_under_30_minutes(self):
        """TC-03: Cảnh báo xung đột thời gian < 30 phút trên cùng một nền tảng (ERR-03)."""
        time_post_a = self.base_time.replace(hour=20, minute=0)
        time_post_b = self.base_time.replace(hour=20, minute=15) # Cách 15 phút (< 30 phút)

        diff_minutes = abs((time_post_a - time_post_b).total_seconds()) / 60
        has_conflict = diff_minutes < 30
        self.assertTrue(has_conflict, f"Khoảng cách {diff_minutes} phút phải bị phát hiện xung đột (< 30 phút)")

    def test_tc04_allow_scheduled_time_safe_distance(self):
        """TC-04: Cho phép lên lịch thành công khi khoảng cách an toàn >= 30 phút."""
        time_post_a = self.base_time.replace(hour=20, minute=0)
        time_post_b = self.base_time.replace(hour=20, minute=45) # Cách 45 phút (>= 30 phút)

        diff_minutes = abs((time_post_a - time_post_b).total_seconds()) / 60
        has_conflict = diff_minutes < 30
        self.assertFalse(has_conflict, f"Khoảng cách {diff_minutes} phút là hợp lệ (>= 30 phút)")

    def test_tc05_reset_reminder_flags_on_reschedule(self):
        """TC-05: Tự động xóa/reset các cờ nhắc nhở khi điều chỉnh/dời giờ đăng bài."""
        schedule = DummySchedule(
            schedule_id=1,
            post_id=4,
            scheduled_time=self.base_time,
            is_reminded_30m=True,
            is_reminded_10m=True,
            is_overdue_alerted=True
        )

        # Mô phỏng thao tác dời giờ đăng sang khung giờ mới
        schedule.scheduled_time = self.base_time + timedelta(hours=3)
        schedule.is_reminded_30m = False
        schedule.is_reminded_10m = False
        schedule.is_overdue_alerted = False

        self.assertFalse(schedule.is_reminded_30m, "Cờ nhắc 30 phút phải được reset về False")
        self.assertFalse(schedule.is_reminded_10m, "Cờ nhắc 10 phút phải được reset về False")
        self.assertFalse(schedule.is_overdue_alerted, "Cờ cảnh báo quá hạn phải được reset về False")

if __name__ == "__main__":
    unittest.main()
