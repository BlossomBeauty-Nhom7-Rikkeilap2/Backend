import pytest
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.database import Base, get_db
from app.core.dependencies import get_current_user
from app.main import app
from app.models.role import Role
from app.models.user import User
from app.models.platform import Platform
from app.models.post import Post
from app.models.post_statistic import PostStatistic
from app.schemas.analytics import PostStatisticCreate, MockSyncRequest
from app.services.analytics_service import AnalyticsService

from sqlalchemy.pool import StaticPool

@pytest.fixture
def db_session():
    """Khoi tao database SQLite in-memory biet lap cho moi test case."""
    test_engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool
    )
    Base.metadata.create_all(bind=test_engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    session = TestingSessionLocal()

    # Seed roles: MANAGER (1) & STAFF (2)
    mgr_role = Role(role_id=1, role_code="MANAGER", role_name="Marketing Manager")
    staff_role = Role(role_id=2, role_code="STAFF", role_name="Content Creator")
    session.add_all([mgr_role, staff_role])

    # Seed users
    manager_user = User(
        user_id=1,
        username="manager1",
        email="manager@blossom.vn",
        password_hash="fakehash",
        full_name="Doan Thi Minh Anh",
        role_id=1,
        status="ACTIVE"
    )
    staff_user = User(
        user_id=2,
        username="staff1",
        email="staff1@blossom.vn",
        password_hash="fakehash",
        full_name="Phan Hoang Son",
        role_id=2,
        status="ACTIVE"
    )
    session.add_all([manager_user, staff_user])

    # Seed platform
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

def _create_sample_post(db, post_id=1, status="PUBLISHED", published_at=None):
    post = Post(
        post_id=post_id,
        title="Bai viet test thong ke",
        caption="Mo ta bai viet",
        platform_id=1,
        author_id=2,
        status=status,
        published_at=published_at or (datetime.now() - timedelta(days=2)),
        published_url="https://facebook.com/post/1"
    )
    db.add(post)
    db.commit()
    db.refresh(post)
    return post

# ==============================================================================
# UNIT TESTS: ANALYTICS SERVICE
# ==============================================================================

def test_record_statistics_manual_success(db_session):
    """Test nhap tay so lieu thanh cong (FR-14 & BR-08), luu nguon MANUAL va kiem tra so nguyen >= 0."""
    user = db_session.query(User).filter(User.user_id == 2).first()
    post = _create_sample_post(db_session, post_id=10, status="PUBLISHED")

    stat_in = PostStatisticCreate(
        reach_count=12000,
        view_count=9500,
        like_count=750,
        comment_count=85,
        share_count=32,
        source_type="MANUAL",
        milestone="24H"
    )

    stat = AnalyticsService.record_statistics(db_session, post.post_id, stat_in, user)

    assert stat.stat_id is not None
    assert stat.post_id == 10
    assert stat.reach_count == 12000
    assert stat.view_count == 9500
    assert stat.like_count == 750
    assert stat.comment_count == 85
    assert stat.share_count == 32
    assert stat.source_type == "MANUAL"
    assert stat.milestone == "24H"
    assert stat.updated_by == 2

def test_record_statistics_rejects_negative_numbers(db_session):
    """Test tu choi khi nhap so am (< 0)."""
    # 1. Kiem tra qua Pydantic schema validation
    with pytest.raises(ValidationError):
        PostStatisticCreate(
            reach_count=-10,
            view_count=100,
            like_count=10,
            comment_count=5,
            share_count=2
        )

    # 2. Kiem tra qua Service layer validation
    user = db_session.query(User).filter(User.user_id == 2).first()
    post = _create_sample_post(db_session, post_id=11, status="PUBLISHED")

    with pytest.raises(HTTPException) as exc_info:
        AnalyticsService._validate_integer_metrics(-1, 100, 10, 5, 2)
    assert exc_info.value.status_code == 400
    assert "reach_count" in exc_info.value.detail

def test_record_statistics_rejects_unpublished_post(db_session):
    """Test khong cho phep nhap so lieu cho bai viet chua xuat ban (BR-08)."""
    user = db_session.query(User).filter(User.user_id == 2).first()
    draft_post = _create_sample_post(db_session, post_id=12, status="DRAFT")

    stat_in = PostStatisticCreate(
        reach_count=100,
        view_count=50,
        like_count=10,
        comment_count=2,
        share_count=1,
        source_type="MANUAL"
    )

    with pytest.raises(HTTPException) as exc_info:
        AnalyticsService.record_statistics(db_session, draft_post.post_id, stat_in, user)
    assert exc_info.value.status_code == 400
    assert "PUBLISHED" in exc_info.value.detail

def test_record_statistics_non_existent_post(db_session):
    """Test bao loi 404 khi khong tim thay bai viet."""
    user = db_session.query(User).filter(User.user_id == 2).first()
    stat_in = PostStatisticCreate(reach_count=100)

    with pytest.raises(HTTPException) as exc_info:
        AnalyticsService.record_statistics(db_session, 99999, stat_in, user)
    assert exc_info.value.status_code == 404

def test_sync_mock_statistics_auto_generation(db_session):
    """Test dong bo Mock API tu dong sinh so lieu hop ly, luu nguon API (Goi y thuong +1)."""
    user = db_session.query(User).filter(User.user_id == 2).first()
    post = _create_sample_post(db_session, post_id=13, status="PUBLISHED")

    stat = AnalyticsService.sync_mock_statistics(db_session, post.post_id, user)

    assert stat.stat_id is not None
    assert stat.post_id == 13
    assert stat.source_type == "API"
    assert stat.reach_count >= 0
    assert stat.view_count >= 0
    assert stat.like_count >= 0
    assert stat.comment_count >= 0
    assert stat.share_count >= 0
    assert stat.updated_by == 2

def test_sync_mock_statistics_custom_values(db_session):
    """Test dong bo Mock API voi tham so moc thoi gian va chi so tuy chon."""
    user = db_session.query(User).filter(User.user_id == 2).first()
    post = _create_sample_post(db_session, post_id=14, status="PUBLISHED")

    mock_req = MockSyncRequest(
        milestone="7D",
        reach_count=8888,
        view_count=6666,
        like_count=555,
        comment_count=77,
        share_count=33
    )

    stat = AnalyticsService.sync_mock_statistics(db_session, post.post_id, user, mock_req)

    assert stat.source_type == "API"
    assert stat.milestone == "7D"
    assert stat.reach_count == 8888
    assert stat.view_count == 6666
    assert stat.like_count == 555
    assert stat.comment_count == 77
    assert stat.share_count == 33

def test_simulate_milestones_and_growth_rate(db_session):
    """Test khoi tao tron bo 3 moc (24H, 7D, 30D) va kiem tra ty le tang truong."""
    user = db_session.query(User).filter(User.user_id == 1).first()
    published_time = datetime.now() - timedelta(days=32)
    post = _create_sample_post(db_session, post_id=15, status="PUBLISHED", published_at=published_time)

    simulated_list = AnalyticsService.simulate_milestones(db_session, post.post_id, user)
    assert len(simulated_list) == 3

    # Lay lich su thong ke
    history_res = AnalyticsService.get_post_statistics_history(db_session, post.post_id)

    assert history_res.post_id == 15
    assert history_res.total_records == 3
    assert history_res.milestones.m24h is not None
    assert history_res.milestones.m7d is not None
    assert history_res.milestones.m30d is not None
    assert history_res.milestones.latest is not None

    # Kiem tra ty le tang truong
    assert history_res.growth_rate.m24h_to_m7d is not None
    assert history_res.growth_rate.m24h_to_m7d["reach_growth_pct"] > 0
    assert history_res.growth_rate.m7d_to_m30d is not None
    assert history_res.growth_rate.m7d_to_m30d["reach_growth_pct"] > 0

def test_history_timeframe_and_milestone_filters(db_session):
    """Test bo loc lich su theo timeframe (24h, 7d, 30d) va milestone."""
    user = db_session.query(User).filter(User.user_id == 2).first()
    post = _create_sample_post(db_session, post_id=16, status="PUBLISHED")
    now = datetime.now()

    # Tao cac ban ghi o cac thoi diem khac nhau
    r1 = PostStatistic(post_id=16, reach_count=100, milestone="24H", source_type="MANUAL", recorded_at=now - timedelta(hours=5), updated_by=2)
    r2 = PostStatistic(post_id=16, reach_count=300, milestone="7D", source_type="API", recorded_at=now - timedelta(days=3), updated_by=2)
    r3 = PostStatistic(post_id=16, reach_count=800, milestone="30D", source_type="API", recorded_at=now - timedelta(days=15), updated_by=2)
    r4 = PostStatistic(post_id=16, reach_count=1500, milestone="CUSTOM", source_type="MANUAL", recorded_at=now - timedelta(days=45), updated_by=2)
    db_session.add_all([r1, r2, r3, r4])
    db_session.commit()

    # Loc 24h
    res_24h = AnalyticsService.get_post_statistics_history(db_session, 16, timeframe="24h")
    assert res_24h.total_records == 1

    # Loc 7d
    res_7d = AnalyticsService.get_post_statistics_history(db_session, 16, timeframe="7d")
    assert res_7d.total_records == 2

    # Loc 30d
    res_30d = AnalyticsService.get_post_statistics_history(db_session, 16, timeframe="30d")
    assert res_30d.total_records == 3

    # Loc toan bo
    res_all = AnalyticsService.get_post_statistics_history(db_session, 16, timeframe="all")
    assert res_all.total_records == 4

    # Loc theo source_type
    res_api = AnalyticsService.get_post_statistics_history(db_session, 16, source_type="API")
    assert res_api.total_records == 2
    for item in res_api.history:
        assert item.source_type == "API"

# ==============================================================================
# INTEGRATION TESTS: FASTAPI HTTP ENDPOINTS
# ==============================================================================

def test_fastapi_analytics_endpoints(db_session):
    """Test cac endpoint API qua TestClient FastAPI."""
    from app.config import settings
    user = db_session.query(User).filter(User.user_id == 2).first()
    post = _create_sample_post(db_session, post_id=20, status="PUBLISHED")

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = lambda: user

    client = TestClient(app)
    api_prefix = settings.API_V1_PREFIX

    # 1. POST /api/posts/{post_id}/statistics (Nhap tay)
    payload_manual = {
        "reach_count": 5000,
        "view_count": 4200,
        "like_count": 310,
        "comment_count": 42,
        "share_count": 18,
        "source_type": "MANUAL",
        "milestone": "24H"
    }
    res_manual = client.post(f"{api_prefix}/posts/20/statistics", json=payload_manual)
    assert res_manual.status_code == 201
    data_manual = res_manual.json()
    assert data_manual["source_type"] == "MANUAL"
    assert data_manual["reach_count"] == 5000

    # 2. POST /api/posts/{post_id}/statistics/sync-mock (Dong bo Mock API)
    res_mock = client.post(f"{api_prefix}/posts/20/statistics/sync-mock", json={"milestone": "7D"})
    assert res_mock.status_code == 201
    data_mock = res_mock.json()
    assert data_mock["source_type"] == "API"
    assert data_mock["milestone"] == "7D"

    # 3. GET /api/posts/{post_id}/statistics/history (Lich su moc)
    res_hist = client.get(f"{api_prefix}/posts/20/statistics/history")
    assert res_hist.status_code == 200
    data_hist = res_hist.json()
    assert data_hist["post_id"] == 20
    assert data_hist["total_records"] == 2

    # 4. GET /api/posts/{post_id}/statistics/latest (Moi nhat)
    res_latest = client.get(f"{api_prefix}/posts/20/statistics/latest")
    assert res_latest.status_code == 200
    data_latest = res_latest.json()
    assert data_latest["post_id"] == 20
    assert data_latest["source_type"] == "API"

    # 5. POST /api/posts/{post_id}/statistics/simulate-milestones
    res_sim = client.post(f"{api_prefix}/posts/20/statistics/simulate-milestones")
    assert res_sim.status_code == 201
    assert len(res_sim.json()) == 3

    # Don dep overrides
    app.dependency_overrides.clear()
