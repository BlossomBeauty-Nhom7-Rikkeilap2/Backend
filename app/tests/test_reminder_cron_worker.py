import pytest
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models.role import Role
from app.models.user import User
from app.models.platform import Platform
from app.models.post import Post
from app.models.schedule import Schedule
from app.models.notification import Notification
from app.services.scheduler_worker import ReminderCronWorker

@pytest.fixture
def db_session():
    """Tạo database SQLite in-memory biệt lập cho mỗi test case."""
    test_engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=test_engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    session = TestingSessionLocal()

    # Seed roles: MANAGER (1) & STAFF (2)
    mgr_role = Role(role_id=1, role_code="MANAGER", role_name="Marketing Manager")
    staff_role = Role(role_id=2, role_code="STAFF", role_name="Content Creator")
    session.add_all([mgr_role, staff_role])

    # Seed users: 1 Manager & 1 Staff
    manager_user = User(
        user_id=1,
        username="manager1",
        email="manager@blossom.vn",
        password_hash="fakehash",
        full_name="Nguyễn Quản Lý",
        role_id=1,
        status="ACTIVE"
    )
    staff_user = User(
        user_id=2,
        username="staff1",
        email="staff1@blossom.vn",
        password_hash="fakehash",
        full_name="Trần Nhân Viên",
        role_id=2,
        status="ACTIVE"
    )
    session.add_all([manager_user, staff_user])

    # Seed platform: Facebook
    platform = Platform(
        platform_id=1,
        platform_code="FACEBOOK",
        platform_name="Facebook Fanpage",
        is_active=True
    )
    session.add(platform)
    session.commit()

    yield session

    session.close()
    Base.metadata.drop_all(bind=test_engine)

@pytest.mark.asyncio
async def test_reminder_30_minutes_milestone(db_session):
    """
    Test mốc 1: Nhắc trước 30 phút.
    Khi lịch hẹn còn 25 phút nữa đến hạn, worker quét và:
    - Bật cờ is_reminded_30m = True.
    - Tạo 1 Notification loại SCHEDULE_REMINDER cho Staff (tác giả).
    - Các cờ 10m, ontime, overdue vẫn là False.
    """
    worker = ReminderCronWorker(interval_seconds=60)
    now = datetime(2026, 11, 17, 10, 0, 0)
    # Lịch đăng lúc 10:25 (còn 25 phút -> nằm trong khoảng 0 < diff_minutes <= 30)
    scheduled_time = now + timedelta(minutes=25)

    post = Post(
        post_id=101,
        author_id=2, # Staff
        platform_id=1,
        title="Khuyến mãi mùa hè 2026",
        caption="Nội dung khuyến mãi",
        status="SCHEDULED"
    )
    db_session.add(post)
    db_session.commit()

    sched = Schedule(
        schedule_id=1,
        post_id=101,
        scheduled_time=scheduled_time,
        scheduled_by=2,
        schedule_status="ACTIVE",
        is_reminded_30m=False,
        is_reminded_10m=False,
        is_reminded_ontime=False,
        is_overdue_alerted=False
    )
    db_session.add(sched)
    db_session.commit()

    # Thực thi chu kỳ quét
    stats = await worker.scan_and_process(now=now, db=db_session)

    db_session.refresh(sched)
    assert 101 in stats["reminded_30m"]
    assert sched.is_reminded_30m is True
    assert sched.is_reminded_10m is False
    assert sched.is_reminded_ontime is False
    assert sched.is_overdue_alerted is False

    # Kiểm tra Notification tạo ra trong DB
    notifs = db_session.query(Notification).filter(Notification.post_id == 101).all()
    assert len(notifs) == 1
    assert notifs[0].recipient_id == 2
    assert notifs[0].notification_type == "SCHEDULE_REMINDER"
    assert "30 phút" in notifs[0].title

@pytest.mark.asyncio
async def test_reminder_10_minutes_milestone(db_session):
    """
    Test mốc 2: Nhắc trước 10 phút.
    Khi lịch hẹn còn 8 phút nữa đến hạn, worker quét và:
    - Bật cờ is_reminded_10m = True và is_reminded_30m = True.
    - Tạo 1 Notification khẩn (SCHEDULE_REMINDER) cho Staff.
    """
    worker = ReminderCronWorker(interval_seconds=60)
    now = datetime(2026, 11, 17, 10, 0, 0)
    # Lịch đăng lúc 10:08 (còn 8 phút)
    scheduled_time = now + timedelta(minutes=8)

    post = Post(
        post_id=102,
        author_id=2,
        platform_id=1,
        title="BST Son Môi Mới",
        status="SCHEDULED"
    )
    db_session.add(post)
    db_session.commit()

    sched = Schedule(
        schedule_id=2,
        post_id=102,
        scheduled_time=scheduled_time,
        scheduled_by=2,
        schedule_status="ACTIVE",
        is_reminded_30m=False,
        is_reminded_10m=False,
        is_reminded_ontime=False,
        is_overdue_alerted=False
    )
    db_session.add(sched)
    db_session.commit()

    stats = await worker.scan_and_process(now=now, db=db_session)

    db_session.refresh(sched)
    assert 102 in stats["reminded_10m"]
    assert sched.is_reminded_10m is True
    assert sched.is_reminded_30m is True
    assert sched.is_reminded_ontime is False
    assert sched.is_overdue_alerted is False

    notifs = db_session.query(Notification).filter(Notification.post_id == 102).all()
    assert len(notifs) == 1
    assert notifs[0].recipient_id == 2
    assert "10 phút" in notifs[0].title

@pytest.mark.asyncio
async def test_reminder_ontime_milestone(db_session):
    """
    Test mốc 3: Đúng giờ (0 phút / Đến giờ đăng bài).
    Khi now >= scheduled_time (diff <= 0):
    - Bật cờ is_reminded_ontime = True (và các cờ trước đó = True).
    - Gửi thông báo đến giờ đăng bài cho Staff.
    """
    worker = ReminderCronWorker(interval_seconds=60)
    now = datetime(2026, 11, 17, 10, 0, 0)
    scheduled_time = datetime(2026, 11, 17, 10, 0, 0) # Đúng 10:00:00

    post = Post(
        post_id=103,
        author_id=2,
        platform_id=1,
        title="Ra mắt Serum Dưỡng Da",
        status="SCHEDULED"
    )
    db_session.add(post)
    db_session.commit()

    sched = Schedule(
        schedule_id=3,
        post_id=103,
        scheduled_time=scheduled_time,
        scheduled_by=2,
        schedule_status="ACTIVE",
        is_reminded_30m=True,
        is_reminded_10m=True,
        is_reminded_ontime=False,
        is_overdue_alerted=False
    )
    db_session.add(sched)
    db_session.commit()

    stats = await worker.scan_and_process(now=now, db=db_session)

    db_session.refresh(sched)
    assert 103 in stats["reminded_ontime"]
    assert sched.is_reminded_ontime is True
    assert sched.is_overdue_alerted is False

    notifs = db_session.query(Notification).filter(Notification.post_id == 103).all()
    assert len(notifs) == 1
    assert notifs[0].recipient_id == 2
    assert "Đến giờ đăng bài" in notifs[0].title

@pytest.mark.asyncio
async def test_overdue_15_minutes_alert_staff_and_manager(db_session):
    """
    Test mốc 4: Cảnh báo quá hạn 15 phút gửi CẢ Staff và Manager.
    Khi đã quá giờ đăng >= 15 phút (diff_minutes <= -15) mà bài viết chưa published:
    - Bật cờ is_overdue_alerted = True.
    - Gửi 1 Notification OVERDUE_ALERT cho Staff (tác giả).
    - Gửi Notification OVERDUE_ALERT cho toàn bộ Marketing Manager.
    """
    worker = ReminderCronWorker(interval_seconds=60)
    now = datetime(2026, 11, 17, 10, 20, 0)
    # Lịch đăng lúc 10:00 (đã quá 20 phút >= 15 phút)
    scheduled_time = datetime(2026, 11, 17, 10, 0, 0)

    post = Post(
        post_id=104,
        author_id=2, # Staff ID = 2
        platform_id=1,
        title="Kem Chống Nắng SPF 50+",
        status="SCHEDULED"
    )
    db_session.add(post)
    db_session.commit()

    sched = Schedule(
        schedule_id=4,
        post_id=104,
        scheduled_time=scheduled_time,
        scheduled_by=2,
        schedule_status="ACTIVE",
        is_reminded_30m=True,
        is_reminded_10m=True,
        is_reminded_ontime=True,
        is_overdue_alerted=False
    )
    db_session.add(sched)
    db_session.commit()

    stats = await worker.scan_and_process(now=now, db=db_session)

    db_session.refresh(sched)
    assert 104 in stats["overdue_alerted"]
    assert sched.is_overdue_alerted is True

    # Kiểm tra notifications gửi cho CẢ Staff và Manager
    notifs = db_session.query(Notification).filter(Notification.post_id == 104).all()
    # Có 2 thông báo: 1 cho Staff (user_id=2) và 1 cho Manager (user_id=1)
    assert len(notifs) == 2

    staff_notif = next((n for n in notifs if n.recipient_id == 2), None)
    mgr_notif = next((n for n in notifs if n.recipient_id == 1), None)

    assert staff_notif is not None
    assert staff_notif.notification_type == "OVERDUE_ALERT"
    assert "Quá hạn đăng bài 15 phút" in staff_notif.title

    assert mgr_notif is not None
    assert mgr_notif.notification_type == "OVERDUE_ALERT"
    assert "Cảnh báo quá hạn đăng bài" in mgr_notif.title

@pytest.mark.asyncio
async def test_anti_duplicate_flags_prevent_multiple_sends(db_session):
    """
    Test mốc 5: Cơ chế tránh gửi trùng bằng cờ (Idempotency).
    Quét liên tục ở cùng một mốc thời gian không bao giờ sinh thêm thông báo thừa.
    """
    worker = ReminderCronWorker(interval_seconds=60)
    now = datetime(2026, 11, 17, 10, 0, 0)
    scheduled_time = now + timedelta(minutes=20) # Mốc 30 phút

    post = Post(
        post_id=105,
        author_id=2,
        platform_id=1,
        title="Nước Tẩy Trang Hoa Hồng",
        status="SCHEDULED"
    )
    db_session.add(post)
    db_session.commit()

    sched = Schedule(
        schedule_id=5,
        post_id=105,
        scheduled_time=scheduled_time,
        scheduled_by=2,
        schedule_status="ACTIVE",
        is_reminded_30m=False,
        is_reminded_10m=False,
        is_reminded_ontime=False,
        is_overdue_alerted=False
    )
    db_session.add(sched)
    db_session.commit()

    # Lần quét 1: Gửi nhắc 30 phút
    stats1 = await worker.scan_and_process(now=now, db=db_session)
    assert 105 in stats1["reminded_30m"]
    assert db_session.query(Notification).filter(Notification.post_id == 105).count() == 1

    # Lần quét 2: Worker quét tiếp 1 phút sau (vẫn mốc 30 phút), không gửi lại do is_reminded_30m = True
    now_next_minute = now + timedelta(minutes=1)
    stats2 = await worker.scan_and_process(now=now_next_minute, db=db_session)
    assert 105 not in stats2["reminded_30m"]
    assert db_session.query(Notification).filter(Notification.post_id == 105).count() == 1

    # Lần quét 3: Đến mốc 10 phút -> gửi nhắc 10 phút (thêm đúng 1 notif)
    now_10m = now + timedelta(minutes=12) # lúc này còn 8 phút
    stats3 = await worker.scan_and_process(now=now_10m, db=db_session)
    assert 105 in stats3["reminded_10m"]
    assert db_session.query(Notification).filter(Notification.post_id == 105).count() == 2

    # Lần quét 4: Quét lại mốc 10 phút -> không gửi trùng
    stats4 = await worker.scan_and_process(now=now_10m + timedelta(minutes=1), db=db_session)
    assert 105 not in stats4["reminded_10m"]
    assert db_session.query(Notification).filter(Notification.post_id == 105).count() == 2

@pytest.mark.asyncio
async def test_reschedule_resets_all_flags(db_session):
    """
    Test mốc 6: Đặt lại toàn bộ cờ khi dời lịch đăng bài.
    Khi đổi sang lịch mới, các cờ is_reminded_* và is_overdue_alerted phải được reset về False.
    """
    from app.services.schedule_service import ScheduleService
    from app.schemas.schedule import ScheduleUpdate

    now = datetime(2026, 11, 17, 10, 0, 0)
    post = Post(
        post_id=106,
        author_id=2,
        platform_id=1,
        title="Mặt Nạ Tràm Trà",
        status="SCHEDULED"
    )
    db_session.add(post)
    db_session.commit()

    sched = Schedule(
        schedule_id=6,
        post_id=106,
        scheduled_time=now - timedelta(minutes=20),
        scheduled_by=2,
        schedule_status="ACTIVE",
        is_reminded_30m=True,
        is_reminded_10m=True,
        is_reminded_ontime=True,
        is_overdue_alerted=True
    )
    db_session.add(sched)
    db_session.commit()

    # Dời lịch sang ngày mai
    new_time = now + timedelta(days=1)
    staff_user = db_session.query(User).filter(User.user_id == 2).first()
    update_data = ScheduleUpdate(scheduled_time=new_time, remind_before_minutes=30)

    updated_sched = ScheduleService.update_schedule(
        db=db_session,
        post_id=106,
        schedule_in=update_data,
        current_user=staff_user
    )

    assert updated_sched.scheduled_time == new_time
    assert updated_sched.is_reminded_30m is False
    assert updated_sched.is_reminded_10m is False
    assert updated_sched.is_reminded_ontime is False
    assert updated_sched.is_overdue_alerted is False

@pytest.mark.asyncio
async def test_ignored_when_post_deleted_or_cancelled(db_session):
    """
    Test edge case: Bỏ qua khi bài viết bị xóa mềm (deleted_at is not None)
    hoặc lịch đã bị hủy (CANCELLED).
    """
    worker = ReminderCronWorker(interval_seconds=60)
    now = datetime(2026, 11, 17, 10, 0, 0)
    scheduled_time = now + timedelta(minutes=20)

    # Post 107 bị xóa mềm
    post_deleted = Post(
        post_id=107,
        author_id=2,
        platform_id=1,
        title="Bài viết đã xóa mềm",
        status="SCHEDULED",
        deleted_at=now
    )
    # Post 108 có schedule CANCELLED
    post_cancelled = Post(
        post_id=108,
        author_id=2,
        platform_id=1,
        title="Bài viết đã hủy lịch",
        status="SCHEDULED"
    )
    db_session.add_all([post_deleted, post_cancelled])
    db_session.commit()

    sched_deleted = Schedule(
        schedule_id=7,
        post_id=107,
        scheduled_time=scheduled_time,
        scheduled_by=2,
        schedule_status="ACTIVE"
    )
    sched_cancelled = Schedule(
        schedule_id=8,
        post_id=108,
        scheduled_time=scheduled_time,
        scheduled_by=2,
        schedule_status="CANCELLED"
    )
    db_session.add_all([sched_deleted, sched_cancelled])
    db_session.commit()

    stats = await worker.scan_and_process(now=now, db=db_session)
    assert 107 not in stats["reminded_30m"]
    assert 108 not in stats["reminded_30m"]
    assert db_session.query(Notification).filter(Notification.post_id.in_([107, 108])).count() == 0

