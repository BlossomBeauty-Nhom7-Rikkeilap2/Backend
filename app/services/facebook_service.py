from typing import Dict, Any, List, Optional
import requests
from urllib.parse import urlencode
from app.config import settings

class FacebookGraphService:
    """
    Dịch vụ tích hợp Meta Graph API (Facebook & Instagram Graph API) - SDD 2.1 & 3.2.7.
    Dùng chung App ID và App Secret của ứng dụng Meta for Developers.
    """
    GRAPH_API_BASE = "https://graph.facebook.com"

    @classmethod
    def get_version(cls) -> str:
        return settings.FACEBOOK_GRAPH_VERSION or "v19.0"

    @classmethod
    def get_authorization_url(cls, redirect_uri: str, state: Optional[str] = None) -> str:
        """
        Tạo đường dẫn đăng nhập Facebook & Instagram OAuth 2.0.
        Bao gồm toàn bộ quyền quản trị Fanpage và Instagram Business Account.
        """
        scopes = [
            "public_profile",
            "email",
            "pages_show_list",
            "pages_read_engagement",
            "pages_manage_posts",
            "read_insights",
            "instagram_basic",
            "instagram_manage_insights",
            "instagram_content_publish"
        ]
        params = {
            "client_id": settings.FACEBOOK_APP_ID,
            "redirect_uri": redirect_uri,
            "scope": ",".join(scopes),
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

        # Nâng cấp lên Long-lived Token
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
        """Lấy danh sách Fanpage và Instagram Business Account liên kết."""
        url = f"{cls.GRAPH_API_BASE}/{cls.get_version()}/me/accounts"
        params = {
            "fields": "id,name,access_token,category,instagram_business_account",
            "access_token": user_access_token
        }
        res = requests.get(url, params=params, timeout=10)
        data = res.json()
        return data.get("data", [])

    # --------------------------------------------------------------------------
    # FACEBOOK API METHODS
    # --------------------------------------------------------------------------
    @classmethod
    def publish_post_to_facebook(
        cls,
        page_id: str,
        page_access_token: str,
        message: str,
        image_url: Optional[str] = None,
        link: Optional[str] = None
    ) -> Dict[str, Any]:
        """Đăng bài viết mới lên Facebook Fanpage (hỗ trợ cả ảnh và văn bản)."""
        if image_url:
            url = f"{cls.GRAPH_API_BASE}/{cls.get_version()}/{page_id}/photos"
            payload = {
                "caption": message,
                "url": image_url,
                "access_token": page_access_token
            }
        else:
            url = f"{cls.GRAPH_API_BASE}/{cls.get_version()}/{page_id}/feed"
            payload = {
                "message": message,
                "access_token": page_access_token
            }
            if link:
                payload["link"] = link
        res = requests.post(url, data=payload, timeout=15)
        return res.json()

    @classmethod
    def get_facebook_post_insights(cls, fb_post_id: str, access_token: str) -> Dict[str, Any]:
        """Lấy số liệu thống kê (Insights) bài viết Facebook (hỗ trợ cả PagePost ID và Photo ID)."""
        target_id = fb_post_id
        if "_" not in target_id and settings.FB_PAGE_ID:
            target_id = f"{settings.FB_PAGE_ID}_{target_id}"

        url = f"{cls.GRAPH_API_BASE}/{cls.get_version()}/{target_id}"
        params = {
            "fields": "shares,comments.summary(true),reactions.summary(true)",
            "access_token": access_token
        }
        res = requests.get(url, params=params, timeout=10)
        data = res.json()

        # Nếu là Photo node (không có trường shares/reactions), thử lại bằng fields của Photo node
        if "error" in data and data["error"].get("code") == 100:
            photo_url = f"{cls.GRAPH_API_BASE}/{cls.get_version()}/{fb_post_id}"
            photo_params = {
                "fields": "likes.summary(true),comments.summary(true)",
                "access_token": access_token
            }
            res = requests.get(photo_url, params=photo_params, timeout=10)
            data = res.json()

        if "error" in data:
            return {"success": False, "error": data["error"]}

        likes = (
            data.get("reactions", {}).get("summary", {}).get("total_count")
            if "reactions" in data
            else data.get("likes", {}).get("summary", {}).get("total_count", 0)
        ) or 0
        comments = data.get("comments", {}).get("summary", {}).get("total_count", 0)
        shares = data.get("shares", {}).get("count", 0)

        # Lấy reach và views
        insights_url = f"{cls.GRAPH_API_BASE}/{cls.get_version()}/{target_id}/insights"
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

    # --------------------------------------------------------------------------
    # INSTAGRAM API METHODS (DÙNG CHUNG META APP ID VÀ SECRET)
    # --------------------------------------------------------------------------
    @classmethod
    def get_instagram_business_account_id(cls, page_id: str, page_access_token: str) -> Optional[str]:
        """Lấy ID của Instagram Business Account đã liên kết với Fanpage."""
        url = f"{cls.GRAPH_API_BASE}/{cls.get_version()}/{page_id}"
        params = {
            "fields": "instagram_business_account",
            "access_token": page_access_token
        }
        res = requests.get(url, params=params, timeout=10)
        data = res.json()
        ig_account = data.get("instagram_business_account")
        return ig_account.get("id") if ig_account else None

    @classmethod
    def publish_photo_to_instagram(
        cls,
        ig_user_id: str,
        access_token: str,
        image_url: str,
        caption: str
    ) -> Dict[str, Any]:
        """
        Đăng ảnh lên Instagram Business Account (Quy trình 2 bước của Meta):
        Bước 1: Tạo media container
        Bước 2: Chờ container xử lý và phát hành (publish)
        """
        import time

        # Bước 1: Tạo container
        create_url = f"{cls.GRAPH_API_BASE}/{cls.get_version()}/{ig_user_id}/media"
        create_payload = {
            "image_url": image_url,
            "caption": caption,
            "access_token": access_token
        }
        create_res = requests.post(create_url, data=create_payload, timeout=20)
        create_data = create_res.json()
        if "id" not in create_data:
            return {"success": False, "error": create_data.get("error", "Container creation failed")}

        creation_id = create_data["id"]

        # Kiểm tra trạng thái container cho đến khi FINISHED
        max_attempts = 10
        for _ in range(max_attempts):
            status_url = f"{cls.GRAPH_API_BASE}/{cls.get_version()}/{creation_id}"
            try:
                status_res = requests.get(
                    status_url,
                    params={"fields": "status_code", "access_token": access_token},
                    timeout=10
                )
                status_data = status_res.json()
                code = status_data.get("status_code")
                if code == "FINISHED":
                    break
                elif code == "ERROR":
                    return {"success": False, "error": f"Instagram container error: {status_data}"}
            except Exception:
                pass
            time.sleep(1.5)

        # Bước 2: Publish media
        publish_url = f"{cls.GRAPH_API_BASE}/{cls.get_version()}/{ig_user_id}/media_publish"
        publish_payload = {
            "creation_id": creation_id,
            "access_token": access_token
        }
        pub_res = requests.post(publish_url, data=publish_payload, timeout=20)
        pub_data = pub_res.json()
        if "id" not in pub_data:
            return {"success": False, "error": pub_data.get("error", "Publish failed")}

        ig_media_id = pub_data["id"]

        # Lấy permalink thực tế từ Instagram
        permalink = None
        try:
            perm_url = f"{cls.GRAPH_API_BASE}/{cls.get_version()}/{ig_media_id}"
            perm_res = requests.get(
                perm_url,
                params={"fields": "permalink", "access_token": access_token},
                timeout=10
            )
            perm_data = perm_res.json()
            permalink = perm_data.get("permalink")
        except Exception:
            pass

        return {
            "success": True,
            "ig_media_id": ig_media_id,
            "permalink": permalink or f"https://www.instagram.com/p/{ig_media_id}/"
        }

    @classmethod
    def resolve_instagram_media_id(
        cls,
        id_or_shortcode: str,
        access_token: str,
        published_url: Optional[str] = None
    ) -> str:
        """
        Chuyển đổi shortcode hoặc permalink Instagram sang numeric Media ID nếu cần.
        """
        candidate = (id_or_shortcode or "").strip()
        if candidate.isdigit():
            return candidate
        ig_user_id = (settings.IG_ACCOUNT_ID or "").strip()
        if not ig_user_id or not access_token:
            return candidate

        norm_pub = (published_url or "").strip().rstrip("/")
        try:
            url = f"{cls.GRAPH_API_BASE}/{cls.get_version()}/{ig_user_id}/media"
            res = requests.get(
                url,
                params={"fields": "id,shortcode,permalink", "limit": 50, "access_token": access_token},
                timeout=10
            )
            items = res.json().get("data", [])
            for item in items:
                sc = (item.get("shortcode") or "").strip()
                perm = (item.get("permalink") or "").strip().rstrip("/")
                if (candidate and sc == candidate) or (norm_pub and perm == norm_pub):
                    return str(item.get("id") or candidate)
        except Exception:
            pass
        return candidate

    @classmethod
    def get_instagram_media_insights(
        cls,
        ig_media_id: str,
        access_token: str,
        published_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Lấy số liệu thống kê bài đăng Instagram (Likes, Comments, Reach, Impressions):
        Hỗ trợ tự động phân giải shortcode từ published_url sang numeric Media ID.
        """
        resolved_media_id = cls.resolve_instagram_media_id(ig_media_id, access_token, published_url)

        # Lấy like và comments cơ bản
        media_url = f"{cls.GRAPH_API_BASE}/{cls.get_version()}/{resolved_media_id}"
        media_params = {
            "fields": "like_count,comments_count,media_type,permalink",
            "access_token": access_token
        }
        media_res = requests.get(media_url, params=media_params, timeout=10)
        media_data = media_res.json()

        if "error" in media_data:
            return {"success": False, "error": media_data["error"]}

        likes = media_data.get("like_count", 0) or 0
        comments = media_data.get("comments_count", 0) or 0

        # Lấy insights chi tiết (fallback sang reach,total_interactions nếu impressions bị gỡ trên Graph API mới)
        insights_url = f"{cls.GRAPH_API_BASE}/{cls.get_version()}/{resolved_media_id}/insights"
        insights_data: Dict[str, Any] = {}
        for metric_list in ("impressions,reach,total_interactions", "reach,total_interactions"):
            try:
                insights_res = requests.get(
                    insights_url,
                    params={"metric": metric_list, "access_token": access_token},
                    timeout=10
                )
                insights_data = insights_res.json()
                if "data" in insights_data:
                    break
            except Exception:
                pass

        reach = 0
        views = 0
        shares = 0
        for item in insights_data.get("data", []):
            name = item.get("name")
            val = item.get("values", [{}])[0].get("value", 0) or 0
            if name == "reach":
                reach = val
            elif name == "impressions":
                views = val
            elif name == "total_interactions":
                # total_interactions = likes + comments + shares + saves
                shares = max(0, val - (likes + comments))

        if views == 0 and reach > 0:
            views = reach

        return {
            "success": True,
            "reach_count": reach,
            "view_count": views,
            "like_count": likes,
            "comment_count": comments,
            "share_count": shares
        }


class ThreadsGraphService:
    """
    Dịch vụ tích hợp Meta Threads Graph API.
    Sử dụng endpoint chính thức https://graph.threads.net/v1.0.
    """
    API_BASE = "https://graph.threads.net"

    @classmethod
    def get_version(cls) -> str:
        return settings.THREADS_API_VERSION or "v1.0"

    @classmethod
    def publish_thread(
        cls,
        threads_user_id: str,
        access_token: str,
        text: str,
        image_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Đăng bài lên Meta Threads:
        Bước 1: Tạo media container (TEXT hoặc IMAGE)
        Bước 2: Chờ xử lý và phát hành (publish)
        """
        import time

        version = cls.get_version()
        create_url = f"{cls.API_BASE}/{version}/{threads_user_id}/threads"
        payload = {
            "media_type": "IMAGE" if image_url else "TEXT",
            "text": text,
            "access_token": access_token
        }
        if image_url:
            payload["image_url"] = image_url

        create_res = requests.post(create_url, data=payload, timeout=20)
        create_data = create_res.json()
        if "id" not in create_data:
            return {"success": False, "error": create_data.get("error", "Threads container creation failed")}

        creation_id = create_data["id"]

        # Chờ container sẵn sàng
        max_attempts = 10
        for _ in range(max_attempts):
            status_url = f"{cls.API_BASE}/{version}/{creation_id}"
            try:
                status_res = requests.get(
                    status_url,
                    params={"fields": "status,error_message", "access_token": access_token},
                    timeout=10
                )
                status_data = status_res.json()
                code = status_data.get("status")
                if code == "FINISHED":
                    break
                elif code == "ERROR":
                    return {"success": False, "error": f"Threads container processing error: {status_data}"}
            except Exception:
                pass
            time.sleep(1.5)

        # Bước 2: Publish
        pub_url = f"{cls.API_BASE}/{version}/{threads_user_id}/threads_publish"
        pub_payload = {
            "creation_id": creation_id,
            "access_token": access_token
        }
        pub_res = requests.post(pub_url, data=pub_payload, timeout=20)
        pub_data = pub_res.json()
        if "id" not in pub_data:
            return {"success": False, "error": pub_data.get("error", "Threads publish failed")}

        threads_media_id = pub_data["id"]

        # Lấy permalink
        permalink = None
        try:
            perm_url = f"{cls.API_BASE}/{version}/{threads_media_id}"
            perm_res = requests.get(
                perm_url,
                params={"fields": "permalink", "access_token": access_token},
                timeout=10
            )
            perm_data = perm_res.json()
            permalink = perm_data.get("permalink")
        except Exception:
            pass

        return {
            "success": True,
            "threads_media_id": threads_media_id,
            "permalink": permalink or f"https://www.threads.net/post/{threads_media_id}"
        }

    @classmethod
    def resolve_threads_media_id(
        cls,
        id_or_shortcode: str,
        access_token: str,
        published_url: Optional[str] = None
    ) -> str:
        """
        Chuyển đổi shortcode hoặc permalink Threads sang numeric Media ID nếu cần.
        """
        candidate = (id_or_shortcode or "").strip()
        if candidate.isdigit():
            return candidate
        threads_user_id = (settings.THREADS_USER_ID or "").strip()
        if not threads_user_id or not access_token:
            return candidate

        def _norm_threads_url(u: str) -> str:
            return (u or "").strip().rstrip("/").replace("threads.com/", "threads.net/")

        norm_pub = _norm_threads_url(published_url or "")
        try:
            version = cls.get_version()
            url = f"{cls.API_BASE}/{version}/{threads_user_id}/threads"
            res = requests.get(
                url,
                params={"fields": "id,shortcode,permalink", "limit": 50, "access_token": access_token},
                timeout=10
            )
            items = res.json().get("data", [])
            for item in items:
                sc = (item.get("shortcode") or "").strip()
                perm = _norm_threads_url(item.get("permalink") or "")
                if (candidate and sc == candidate) or (norm_pub and perm == norm_pub) or (candidate and perm.endswith("/" + candidate)):
                    return str(item.get("id") or candidate)
        except Exception:
            pass
        return candidate

    @classmethod
    def get_threads_insights(
        cls,
        threads_media_id: str,
        access_token: str,
        published_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """Lấy số liệu thống kê bài đăng Threads (hỗ trợ cả numeric ID và shortcode)."""
        resolved_id = cls.resolve_threads_media_id(threads_media_id, access_token, published_url)
        version = cls.get_version()
        url = f"{cls.API_BASE}/{version}/{resolved_id}/insights"
        params = {
            "metric": "views,likes,replies,reposts,quotes",
            "access_token": access_token
        }
        res = requests.get(url, params=params, timeout=10)
        data = res.json()
        if "error" in data:
            return {"success": False, "error": data["error"]}

        metrics_map = {}
        for item in data.get("data", []):
            metrics_map[item.get("name")] = item.get("values", [{}])[0].get("value", 0)

        return {
            "success": True,
            "reach_count": metrics_map.get("views", 0),
            "view_count": metrics_map.get("views", 0),
            "like_count": metrics_map.get("likes", 0),
            "comment_count": metrics_map.get("replies", 0),
            "share_count": metrics_map.get("reposts", 0) + metrics_map.get("quotes", 0)
        }
