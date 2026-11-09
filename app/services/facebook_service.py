from typing import Dict, Any, List, Optional
import requests
from urllib.parse import urlencode
from app.config import settings

class FacebookGraphService:
    """
    Dịch vụ tích hợp Facebook Graph API & Instagram Graph API (SDD 2.1 & 3.2.7).
    Sử dụng App ID và App Secret để quản lý OAuth 2.0 và đồng bộ số liệu thống kê.
    """
    GRAPH_API_BASE = "https://graph.facebook.com"

    @classmethod
    def get_version(cls) -> str:
        return settings.FACEBOOK_GRAPH_VERSION or "v19.0"

    @classmethod
    def get_authorization_url(cls, redirect_uri: str, state: Optional[str] = None) -> str:
        """
        Tạo đường dẫn đăng nhập Facebook OAuth 2.0 để người dùng liên kết Fanpage.
        Yêu cầu các quyền quản lý bài viết và đọc chỉ số tương tác (Insights).
        """
        params = {
            "client_id": settings.FACEBOOK_APP_ID,
            "redirect_uri": redirect_uri,
            "scope": ",".join([
                "public_profile",
                "email",
                "pages_show_list",
                "pages_read_engagement",
                "pages_manage_posts",
                "read_insights",
                "instagram_basic",
                "instagram_manage_insights"
            ]),
            "response_type": "code"
        }
        if state:
            params["state"] = state
        return f"https://www.facebook.com/{cls.get_version()}/dialog/oauth?{urlencode(params)}"

    @classmethod
    def exchange_code_for_token(cls, code: str, redirect_uri: str) -> Dict[str, Any]:
        """
        Đổi mã authorization code lấy User Access Token ngắn hạn,
        sau đó tự động nâng cấp lên Long-lived Access Token (thời hạn 60 ngày).
        """
        # 1. Lấy short-lived access token
        token_url = f"{cls.GRAPH_API_BASE}/{cls.get_version()}/oauth/access_token"
        params = {
            "client_id": settings.FACEBOOK_APP_ID,
            "client_secret": settings.FACEBOOK_APP_SECRET,
            "redirect_uri": redirect_uri,
            "code": code
        }
        res = requests.get(token_url, params=params, timeout=10)
        res_data = res.json()
        if "error" in res_data:
            return {"success": False, "error": res_data["error"]}

        short_lived_token = res_data.get("access_token")

        # 2. Đổi sang long-lived token
        extend_params = {
            "grant_type": "fb_exchange_token",
            "client_id": settings.FACEBOOK_APP_ID,
            "client_secret": settings.FACEBOOK_APP_SECRET,
            "fb_exchange_token": short_lived_token
        }
        extend_res = requests.get(token_url, params=extend_params, timeout=10)
        extend_data = extend_res.json()
        if "error" in extend_data:
            return {"success": True, "access_token": short_lived_token, "expires_in": res_data.get("expires_in")}

        return {
            "success": True,
            "access_token": extend_data.get("access_token"),
            "expires_in": extend_data.get("expires_in")
        }

    @classmethod
    def get_managed_pages(cls, user_access_token: str) -> List[Dict[str, Any]]:
        """Lấy danh sách các Trang Fanpage mà người dùng quản lý cùng Page Access Token tương ứng."""
        url = f"{cls.GRAPH_API_BASE}/{cls.get_version()}/me/accounts"
        params = {"access_token": user_access_token}
        res = requests.get(url, params=params, timeout=10)
        data = res.json()
        return data.get("data", [])

    @classmethod
    def publish_post_to_page(
        cls,
        page_id: str,
        page_access_token: str,
        message: str,
        link: Optional[str] = None
    ) -> Dict[str, Any]:
        """Đăng bài viết mới lên Facebook Fanpage."""
        url = f"{cls.GRAPH_API_BASE}/{cls.get_version()}/{page_id}/feed"
        payload = {
            "message": message,
            "access_token": page_access_token
        }
        if link:
            payload["link"] = link
        res = requests.post(url, data=payload, timeout=10)
        return res.json()

    @classmethod
    def get_post_insights(cls, fb_post_id: str, access_token: str) -> Dict[str, Any]:
        """
        Lấy số liệu thống kê (Post Statistics) của một bài đăng trên Facebook (FR-14 & SDD 3.2.7):
        - Reach (Lượt tiếp cận)
        - Impressions (Lượt hiển thị)
        - Reactions / Likes (Lượt thích)
        - Comments (Bình luận)
        - Shares (Chia sẻ)
        """
        url = f"{cls.GRAPH_API_BASE}/{cls.get_version()}/{fb_post_id}"
        params = {
            "fields": "shares,comments.summary(true),reactions.summary(true)",
            "access_token": access_token
        }
        res = requests.get(url, params=params, timeout=10)
        data = res.json()

        if "error" in data:
            return {"success": False, "error": data["error"]}

        likes = data.get("reactions", {}).get("summary", {}).get("total_count", 0)
        comments = data.get("comments", {}).get("summary", {}).get("total_count", 0)
        shares = data.get("shares", {}).get("count", 0)

        # Lấy metrics reach/impressions qua /insights
        insights_url = f"{cls.GRAPH_API_BASE}/{cls.get_version()}/{fb_post_id}/insights"
        insights_params = {
            "metric": "post_impressions,post_impressions_unique",
            "access_token": access_token
        }
        insights_res = requests.get(insights_url, params=insights_params, timeout=10)
        insights_data = insights_res.json()

        views = 0
        reach = 0
        for item in insights_data.get("data", []):
            if item.get("name") == "post_impressions":
                views = item.get("values", [{}])[0].get("value", 0)
            elif item.get("name") == "post_impressions_unique":
                reach = item.get("values", [{}])[0].get("value", 0)

        return {
            "success": True,
            "reach_count": reach,
            "view_count": views,
            "like_count": likes,
            "comment_count": comments,
            "share_count": shares
        }
