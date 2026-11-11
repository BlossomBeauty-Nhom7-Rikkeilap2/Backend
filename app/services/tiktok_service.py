from typing import Dict, Any, Optional
import requests
from urllib.parse import urlencode
from app.config import settings

class TikTokApiService:
    """
    Dịch vụ tích hợp TikTok Open API v2 (Login Kit & Video Insights) - SDD 2.1 & 3.2.7.
    Sử dụng Client Key và Client Secret để xác thực OAuth 2.0 và đồng bộ số liệu video.
    """
    AUTH_BASE_URL = "https://www.tiktok.com/v2/auth/authorize/"
    API_BASE_URL = "https://open.tiktokapis.com/v2"

    @classmethod
    def get_authorization_url(cls, redirect_uri: str, state: Optional[str] = None) -> str:
        """
        Tạo đường dẫn đăng nhập TikTok OAuth 2.0 (Login Kit v2).
        Yêu cầu các quyền đọc thông tin tài khoản, danh sách video và chỉ số tương tác.
        """
        scopes = [
            "user.info.basic",
            "video.list",
            "video.upload"
        ]
        params = {
            "client_key": settings.tiktok_key,
            "scope": ",".join(scopes),
            "response_type": "code",
            "redirect_uri": redirect_uri
        }
        if state:
            params["state"] = state
        return f"{cls.AUTH_BASE_URL}?{urlencode(params)}"

    @classmethod
    def exchange_code_for_token(cls, code: str, redirect_uri: str) -> Dict[str, Any]:
        """
        Đổi mã authorization code lấy Access Token và Refresh Token từ TikTok API v2.
        """
        url = f"{cls.API_BASE_URL}/oauth/token/"
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Cache-Control": "no-cache"
        }
        data = {
            "client_key": settings.tiktok_key,
            "client_secret": settings.tiktok_secret,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": redirect_uri
        }
        res = requests.post(url, headers=headers, data=data, timeout=15)
        res_data = res.json()

        # TikTok API v2 trả về error nếu có mã lỗi khác 0 trong response
        if "error" in res_data and res_data.get("error") != "ok":
            return {"success": False, "error": res_data.get("error_description", res_data.get("error"))}

        token_info = res_data.get("data", res_data)
        return {
            "success": True,
            "access_token": token_info.get("access_token"),
            "refresh_token": token_info.get("refresh_token"),
            "expires_in": token_info.get("expires_in"),
            "open_id": token_info.get("open_id")
        }

    @classmethod
    def refresh_access_token(cls, refresh_token: str) -> Dict[str, Any]:
        """Làm mới Access Token khi hết hạn bằng Refresh Token."""
        url = f"{cls.API_BASE_URL}/oauth/token/"
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Cache-Control": "no-cache"
        }
        data = {
            "client_key": settings.tiktok_key,
            "client_secret": settings.tiktok_secret,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token
        }
        res = requests.post(url, headers=headers, data=data, timeout=15)
        res_data = res.json()

        if "error" in res_data and res_data.get("error") != "ok":
            return {"success": False, "error": res_data.get("error_description", res_data.get("error"))}

        token_info = res_data.get("data", res_data)
        return {
            "success": True,
            "access_token": token_info.get("access_token"),
            "refresh_token": token_info.get("refresh_token"),
            "expires_in": token_info.get("expires_in")
        }

    @classmethod
    def get_video_insights(cls, video_id: str, access_token: str) -> Dict[str, Any]:
        """
        Truy vấn số liệu thống kê của video TikTok (FR-14 & SDD 3.2.7):
        - Views (view_count)
        - Likes (like_count)
        - Comments (comment_count)
        - Shares (share_count)
        """
        url = f"{cls.API_BASE_URL}/video/query/"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        payload = {
            "filters": {
                "video_ids": [video_id]
            }
        }
        params = {
            "fields": "id,title,video_description,duration,like_count,comment_count,share_count,view_count"
        }

        res = requests.post(url, headers=headers, params=params, json=payload, timeout=15)
        res_data = res.json()

        if res_data.get("error", {}).get("code") != "ok" and "error" in res_data:
            return {
                "success": False,
                "error": res_data.get("error", {}).get("message", "Không thể lấy thông tin video TikTok")
            }

        videos = res_data.get("data", {}).get("videos", [])
        if not videos:
            return {"success": False, "error": "Không tìm thấy video với ID cung cấp"}

        target_video = videos[0]
        views = target_video.get("view_count", 0)
        likes = target_video.get("like_count", 0)
        comments = target_video.get("comment_count", 0)
        shares = target_video.get("share_count", 0)
        reach = views  # Đối với video ngắn TikTok, reach tương đương lượt tiếp cận xem video

        return {
            "success": True,
            "video_id": target_video.get("id"),
            "title": target_video.get("title", ""),
            "reach_count": reach,
            "view_count": views,
            "like_count": likes,
            "comment_count": comments,
            "share_count": shares
        }
