from typing import Dict, Any, Optional
import requests
from urllib.parse import urlencode
from app.config import settings

class ThreadsApiService:
    """
    Dich vu tich hop Meta Threads API (Threads Graph API v1.0) - SDD 2.1 & 3.2.7.
    Su dung App ID va App Secret de xac thuc OAuth 2.0, dang bai va dong bo so lieu thong ke.
    """
    AUTH_BASE_URL = "https://threads.net/oauth/authorize"
    GRAPH_API_BASE = "https://graph.threads.net"

    @classmethod
    def get_version(cls) -> str:
        return settings.THREADS_API_VERSION or "v1.0"

    @classmethod
    def get_authorization_url(cls, redirect_uri: str, state: Optional[str] = None) -> str:
        """
        Tao duong dan dang nhap Threads OAuth 2.0.
        Bao gom quyen doc thong tin co ban, dang bai viet va doc chi so thong ke (Insights).
        """
        scopes = [
            "threads_basic",
            "threads_content_publish",
            "threads_read_replies",
            "threads_manage_replies",
            "threads_manage_insights"
        ]
        params = {
            "client_id": settings.THREADS_APP_ID,
            "redirect_uri": redirect_uri,
            "scope": ",".join(scopes),
            "response_type": "code"
        }
        if state:
            params["state"] = state
        return f"{cls.AUTH_BASE_URL}?{urlencode(params)}"

    @classmethod
    def exchange_code_for_token(cls, code: str, redirect_uri: str) -> Dict[str, Any]:
        """
        Doi ma authorization code lay Short-lived Token (1 gio),
        sau do tu dong nang cap len Long-lived Access Token (thoi han 60 ngay).
        """
        token_url = f"{cls.GRAPH_API_BASE}/oauth/access_token"
        data = {
            "client_id": settings.THREADS_APP_ID,
            "client_secret": settings.THREADS_APP_SECRET,
            "grant_type": "authorization_code",
            "redirect_uri": redirect_uri,
            "code": code
        }
        res = requests.post(token_url, data=data, timeout=15)
        res_data = res.json()

        if "error" in res_data:
            return {"success": False, "error": res_data["error"]}

        short_lived_token = res_data.get("access_token")
        user_id = res_data.get("user_id")

        # Nang cap sang Long-lived Access Token (60 ngay)
        extend_url = f"{cls.GRAPH_API_BASE}/access_token"
        extend_params = {
            "grant_type": "th_exchange_token",
            "client_secret": settings.THREADS_APP_SECRET,
            "access_token": short_lived_token
        }
        extend_res = requests.get(extend_url, params=extend_params, timeout=15)
        extend_data = extend_res.json()

        if "error" in extend_data:
            # Fallback ve short-lived token neu khong the nang cap
            return {
                "success": True,
                "access_token": short_lived_token,
                "user_id": user_id,
                "token_type": "bearer",
                "expires_in": 3600,
                "is_long_lived": False
            }

        return {
            "success": True,
            "access_token": extend_data.get("access_token"),
            "token_type": extend_data.get("token_type", "bearer"),
            "expires_in": extend_data.get("expires_in", 5184000),
            "user_id": user_id,
            "is_long_lived": True
        }

    @classmethod
    def refresh_access_token(cls, access_token: str) -> Dict[str, Any]:
        """Lam moi Long-lived Access Token khi sap het han."""
        url = f"{cls.GRAPH_API_BASE}/refresh_access_token"
        params = {
            "grant_type": "th_refresh_token",
            "access_token": access_token
        }
        res = requests.get(url, params=params, timeout=15)
        res_data = res.json()
        if "error" in res_data:
            return {"success": False, "error": res_data["error"]}

        return {
            "success": True,
            "access_token": res_data.get("access_token"),
            "token_type": res_data.get("token_type", "bearer"),
            "expires_in": res_data.get("expires_in", 5184000)
        }

    @classmethod
    def get_user_profile(cls, access_token: str) -> Dict[str, Any]:
        """Lay thong tin ho so nguoi dung Threads (ID, username, avatar, bio)."""
        url = f"{cls.GRAPH_API_BASE}/{cls.get_version()}/me"
        params = {
            "fields": "id,username,name,threads_profile_picture_url,threads_biography",
            "access_token": access_token
        }
        res = requests.get(url, params=params, timeout=10)
        res_data = res.json()
        if "error" in res_data:
            return {"success": False, "error": res_data["error"]}
        return {"success": True, "data": res_data}

    @classmethod
    def publish_threads_post(
        cls,
        user_id: str,
        access_token: str,
        text: str,
        media_url: Optional[str] = None,
        media_type: str = "TEXT"
    ) -> Dict[str, Any]:
        """
        Xuat ban bai viet len Threads qua quy trinh 2 buoc:
        Buoc 1: Tao Media Container (TEXT, IMAGE, VIDEO).
        Buoc 2: Xuat ban Container len trang ca nhan cua tai khoan Threads.
        """
        # Buoc 1: Tao container
        container_url = f"{cls.GRAPH_API_BASE}/{cls.get_version()}/{user_id}/threads"
        payload: Dict[str, Any] = {
            "access_token": access_token,
            "text": text
        }

        m_type = media_type.upper() if media_type else "TEXT"
        if media_url and m_type == "IMAGE":
            payload["media_type"] = "IMAGE"
            payload["image_url"] = media_url
        elif media_url and m_type == "VIDEO":
            payload["media_type"] = "VIDEO"
            payload["video_url"] = media_url
        else:
            payload["media_type"] = "TEXT"

        c_res = requests.post(container_url, data=payload, timeout=20)
        c_data = c_res.json()

        if "error" in c_data:
            return {"success": False, "error": c_data["error"]}

        creation_id = c_data.get("id")
        if not creation_id:
            return {"success": False, "error": "Khong nhan duoc creation_id tu Threads API"}

        # Buoc 2: Xuat ban container
        publish_url = f"{cls.GRAPH_API_BASE}/{cls.get_version()}/{user_id}/threads_publish"
        publish_payload = {
            "creation_id": creation_id,
            "access_token": access_token
        }
        p_res = requests.post(publish_url, data=publish_payload, timeout=20)
        p_data = p_res.json()

        if "error" in p_data:
            return {"success": False, "error": p_data["error"]}

        threads_post_id = p_data.get("id")
        return {
            "success": True,
            "threads_post_id": threads_post_id,
            "permalink": f"https://www.threads.net/t/{threads_post_id}" if threads_post_id else "",
            "raw_response": p_data
        }

    @classmethod
    def get_threads_insights(cls, threads_media_id: str, access_token: str) -> Dict[str, Any]:
        """
        Truy van so lieu thong ke (Insights) bai dang Threads:
        - views (Luot xem)
        - likes (Luot thich)
        - replies (Luot tra loi / binh luan)
        - reposts (Luot dang lai / chia se)
        - quotes (Luot trich dan)
        """
        url = f"{cls.GRAPH_API_BASE}/{cls.get_version()}/{threads_media_id}/insights"
        params = {
            "metric": "views,likes,replies,reposts,quotes",
            "access_token": access_token
        }
        res = requests.get(url, params=params, timeout=15)
        res_data = res.json()

        if "error" in res_data:
            return {"success": False, "error": res_data["error"]}

        views = 0
        likes = 0
        replies = 0
        reposts = 0
        quotes = 0

        for item in res_data.get("data", []):
            name = item.get("name")
            val = item.get("values", [{}])[0].get("value", 0)
            if name == "views":
                views = val
            elif name == "likes":
                likes = val
            elif name == "replies":
                replies = val
            elif name == "reposts":
                reposts = val
            elif name == "quotes":
                quotes = val

        shares = reposts + quotes
        reach = views

        return {
            "success": True,
            "threads_media_id": threads_media_id,
            "reach_count": reach,
            "view_count": views,
            "like_count": likes,
            "comment_count": replies,
            "share_count": shares,
            "reposts_count": reposts,
            "quotes_count": quotes
        }
