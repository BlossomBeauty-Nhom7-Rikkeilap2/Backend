import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.core.database import Base, get_db
from app.core.dependencies import get_current_user
from app.main import app
from app.config import settings
from app.models.role import Role
from app.models.user import User
from app.models.platform import Platform
from app.models.post import Post
from app.services.threads_service import ThreadsApiService

@pytest.fixture
def db_session():
    """Khoi tao database SQLite in-memory biet lap voi StaticPool."""
    test_engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool
    )
    Base.metadata.create_all(bind=test_engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    session = TestingSessionLocal()

    # Seed role va user
    mgr_role = Role(role_id=1, role_code="MANAGER", role_name="Marketing Manager")
    staff_role = Role(role_id=2, role_code="STAFF", role_name="Content Creator")
    session.add_all([mgr_role, staff_role])

    user = User(
        user_id=1,
        username="threads_manager",
        email="manager@threads.test",
        password_hash="fakehash",
        full_name="Doan Thi Minh Anh",
        role_id=1,
        status="ACTIVE"
    )
    session.add(user)

    # Seed platform Threads
    plat = Platform(
        platform_id=3,
        platform_code="THREADS",
        platform_name="Threads Official",
        color_hex="#000000",
        channel_url="https://www.threads.net/@korean_cosmetics",
        oauth_config={"app_id": "2206691199880753", "api_version": "v1.0"},
        is_active=True
    )
    session.add(plat)
    session.commit()

    yield session
    session.close()

def _create_sample_threads_post(db, post_id=101, status="PUBLISHED"):
    post = Post(
        post_id=post_id,
        title="Threads Post Ve Cham Soc Da",
        caption="Review tinh chat phuc hoi da sau 7 ngay su dung.",
        hashtags="#Threads #BeautyTips #Skincare",
        platform_id=3,
        author_id=1,
        status=status,
        published_at=datetime.now() - timedelta(days=1),
        published_url="https://www.threads.net/t/123456"
    )
    db.add(post)
    db.commit()
    db.refresh(post)
    return post

# ==============================================================================
# UNIT TESTS: THREADS API SERVICE
# ==============================================================================

def test_threads_authorization_url():
    """Kiem tra URL tao dang nhap Threads OAuth 2.0 voi App ID va day du scopes."""
    redirect_uri = "http://localhost:5500/oauth/threads/callback"
    url = ThreadsApiService.get_authorization_url(redirect_uri, state="state_123")

    assert "https://threads.net/oauth/authorize" in url
    assert "client_id=" in url
    assert "threads_basic" in url
    assert "threads_content_publish" in url
    assert "threads_manage_insights" in url
    assert "state=state_123" in url
    assert "response_type=code" in url

@patch("requests.post")
@patch("requests.get")
def test_threads_exchange_token_success(mock_get, mock_post):
    """Kiem tra doi code lay short-lived token va tu dong nang cap len long-lived token (60 ngay)."""
    # Mock post doi code -> short-lived token
    mock_post_res = MagicMock()
    mock_post_res.json.return_value = {
        "access_token": "th_short_lived_token",
        "user_id": 123456789
    }
    mock_post.return_value = mock_post_res

    # Mock get nang cap -> long-lived token
    mock_get_res = MagicMock()
    mock_get_res.json.return_value = {
        "access_token": "th_long_lived_token_60d",
        "token_type": "bearer",
        "expires_in": 5184000
    }
    mock_get.return_value = mock_get_res

    res = ThreadsApiService.exchange_code_for_token("auth_code_xyz", "http://localhost:5500/callback")

    assert res["success"] is True
    assert res["access_token"] == "th_long_lived_token_60d"
    assert res["user_id"] == 123456789
    assert res["is_long_lived"] is True
    assert res["expires_in"] == 5184000

@patch("requests.post")
def test_threads_exchange_token_error(mock_post):
    """Kiem tra xu ly loi khi doi code that bai."""
    mock_post_res = MagicMock()
    mock_post_res.json.return_value = {
        "error": {
            "message": "Invalid verification code",
            "type": "OAuthException",
            "code": 100
        }
    }
    mock_post.return_value = mock_post_res

    res = ThreadsApiService.exchange_code_for_token("invalid_code", "http://localhost:5500/callback")
    assert res["success"] is False
    assert "error" in res

@patch("requests.get")
def test_threads_refresh_token(mock_get):
    """Kiem tra lam moi long-lived access token."""
    mock_get_res = MagicMock()
    mock_get_res.json.return_value = {
        "access_token": "th_refreshed_long_lived_token",
        "token_type": "bearer",
        "expires_in": 5184000
    }
    mock_get.return_value = mock_get_res

    res = ThreadsApiService.refresh_access_token("old_token")
    assert res["success"] is True
    assert res["access_token"] == "th_refreshed_long_lived_token"

@patch("requests.get")
def test_threads_get_user_profile(mock_get):
    """Kiem tra lay thong tin ho so tai khoan Threads."""
    mock_get_res = MagicMock()
    mock_get_res.json.return_value = {
        "id": "2206691199880753",
        "username": "korean_cosmetics",
        "name": "Korean Cosmetics Official",
        "threads_profile_picture_url": "https://threads.net/avatar.jpg"
    }
    mock_get.return_value = mock_get_res

    res = ThreadsApiService.get_user_profile("valid_token")
    assert res["success"] is True
    assert res["data"]["username"] == "korean_cosmetics"
    assert res["data"]["id"] == "2206691199880753"

@patch("requests.post")
def test_threads_publish_flow(mock_post):
    """Kiem tra quy trinh xuat ban bai viet 2 buoc: tao container va publish container."""
    # Lan 1: tao container -> {"id": "c_999"}
    # Lan 2: publish container -> {"id": "th_media_888"}
    res_step1 = MagicMock()
    res_step1.json.return_value = {"id": "c_999"}

    res_step2 = MagicMock()
    res_step2.json.return_value = {"id": "th_media_888"}

    mock_post.side_effect = [res_step1, res_step2]

    res = ThreadsApiService.publish_threads_post(
        user_id="th_user_1",
        access_token="th_token_abc",
        text="Review san pham kem chong nang",
        media_url="https://media.blossom.vn/sunscreen.jpg",
        media_type="IMAGE"
    )

    assert res["success"] is True
    assert res["threads_post_id"] == "th_media_888"
    assert "https://www.threads.net/t/th_media_888" in res["permalink"]

@patch("requests.get")
def test_threads_get_insights(mock_get):
    """Kiem tra truy van Insights va tinh toan reach, views, likes, comments, shares tren Threads."""
    mock_get_res = MagicMock()
    mock_get_res.json.return_value = {
        "data": [
            {"name": "views", "values": [{"value": 14500}]},
            {"name": "likes", "values": [{"value": 1250}]},
            {"name": "replies", "values": [{"value": 180}]},
            {"name": "reposts", "values": [{"value": 65}]},
            {"name": "quotes", "values": [{"value": 25}]}
        ]
    }
    mock_get.return_value = mock_get_res

    insights = ThreadsApiService.get_threads_insights("th_media_888", "valid_token")

    assert insights["success"] is True
    assert insights["view_count"] == 14500
    assert insights["reach_count"] == 14500
    assert insights["like_count"] == 1250
    assert insights["comment_count"] == 180
    assert insights["share_count"] == 90 # 65 reposts + 25 quotes
    assert insights["reposts_count"] == 65
    assert insights["quotes_count"] == 25

# ==============================================================================
# INTEGRATION TESTS: FASTAPI HTTP ENDPOINTS
# ==============================================================================

def test_fastapi_threads_routes(db_session):
    """Kiem tra cac endpoint HTTP cua Threads qua TestClient FastAPI."""
    user = db_session.query(User).filter(User.user_id == 1).first()
    post = _create_sample_threads_post(db_session, post_id=101, status="PUBLISHED")

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = lambda: user

    client = TestClient(app)
    api_prefix = settings.API_V1_PREFIX

    # 1. GET /api/social/threads/login-url
    res_login = client.get(f"{api_prefix}/social/threads/login-url")
    assert res_login.status_code == 200
    assert "oauth_url" in res_login.json()
    assert "threads.net/oauth/authorize" in res_login.json()["oauth_url"]

    # 2. POST /api/social/threads/exchange-token (Mocked)
    with patch("app.services.threads_service.ThreadsApiService.exchange_code_for_token") as mock_ex:
        mock_ex.return_value = {
            "success": True,
            "access_token": "th_token_mock_60d",
            "user_id": 2206691199880753,
            "expires_in": 5184000
        }
        res_ex = client.post(
            f"{api_prefix}/social/threads/exchange-token",
            json={"code": "sample_auth_code", "redirect_uri": "http://localhost:5500/callback"}
        )
        assert res_ex.status_code == 200
        assert res_ex.json()["access_token"] == "th_token_mock_60d"

    # 3. POST /api/social/posts/{post_id}/sync-threads (Mocked)
    with patch("app.services.threads_service.ThreadsApiService.get_threads_insights") as mock_ins:
        mock_ins.return_value = {
            "success": True,
            "threads_media_id": "th_media_101",
            "reach_count": 25000,
            "view_count": 25000,
            "like_count": 1800,
            "comment_count": 240,
            "share_count": 120
        }
        res_sync = client.post(
            f"{api_prefix}/social/posts/101/sync-threads",
            json={
                "threads_media_id": "th_media_101",
                "access_token": "mock_token",
                "milestone": "24H"
            }
        )
        assert res_sync.status_code == 200
        sync_data = res_sync.json()
        assert sync_data["source_type"] == "API"
        assert sync_data["milestone"] == "24H"
        assert sync_data["reach_count"] == 25000
        assert sync_data["like_count"] == 1800

    app.dependency_overrides.clear()
