import time
import json
import logging
from typing import Dict, Any, List, Optional
import requests
from urllib.parse import urlencode
from app.config import settings

logger = logging.getLogger("FacebookGraphService")

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
    def publish_video_to_facebook(
        cls,
        page_id: str,
        page_access_token: str,
        video_url: str,
        description: str,
        title: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Đăng video lên Facebook Fanpage qua endpoint /{page_id}/videos.
        """
        url = f"{cls.GRAPH_API_BASE}/{cls.get_version()}/{page_id}/videos"
        payload = {
            "file_url": video_url,
            "description": description,
            "access_token": page_access_token
        }
        if title:
            payload["title"] = title
        try:
            res = requests.post(url, data=payload, timeout=60)
            return res.json()
        except Exception as e:
            return {"error": {"message": f"Lỗi kết nối khi đăng video lên Facebook: {str(e)}"}}

    @classmethod
    def publish_album_to_facebook(
        cls,
        page_id: str,
        page_access_token: str,
        message: str,
        image_urls: List[str]
    ) -> Dict[str, Any]:
        """
        Đăng album nhiều ảnh lên Facebook Fanpage:
        1. Gọi /{page_id}/photos với từng ảnh kèm published=false để lấy danh sách photo_id.
        2. Gọi /{page_id}/feed với attached_media=[{"media_fbid": id}, ...] và message.
        """
        if not image_urls:
            return cls.publish_post_to_facebook(page_id, page_access_token, message)
        if len(image_urls) == 1:
            return cls.publish_post_to_facebook(page_id, page_access_token, message, image_url=image_urls[0])

        attached_media = []
        for img_url in image_urls:
            try:
                photo_url = f"{cls.GRAPH_API_BASE}/{cls.get_version()}/{page_id}/photos"
                photo_payload = {
                    "url": img_url,
                    "published": "false",
                    "access_token": page_access_token
                }
                res = requests.post(photo_url, data=photo_payload, timeout=30)
                data = res.json()
                if "id" in data:
                    attached_media.append({"media_fbid": str(data["id"])})
                else:
                    logger.warning(f"Không thể upload ảnh con cho album Facebook: {data.get('error')}")
            except Exception as ex:
                logger.warning(f"Lỗi khi upload ảnh con cho album Facebook: {ex}")

        if not attached_media:
            return cls.publish_post_to_facebook(page_id, page_access_token, message, image_url=image_urls[0])

        feed_url = f"{cls.GRAPH_API_BASE}/{cls.get_version()}/{page_id}/feed"
        feed_payload = {
            "message": message,
            "attached_media": json.dumps(attached_media),
            "access_token": page_access_token
        }
        try:
            feed_res = requests.post(feed_url, data=feed_payload, timeout=30)
            return feed_res.json()
        except Exception as e:
            return {"error": {"message": f"Lỗi khi đăng album Facebook: {str(e)}"}}

    @classmethod
    def get_facebook_post_insights(cls, fb_post_id: str, access_token: str) -> Dict[str, Any]:
        """Lấy số liệu thống kê (Insights) bài viết Facebook."""
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

        # Lấy reach và views
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
        Bước 2: Phát hành (publish) container
        """
        # Bước 1: Tạo container
        create_url = f"{cls.GRAPH_API_BASE}/{cls.get_version()}/{ig_user_id}/media"
        create_payload = {
            "image_url": image_url,
            "caption": caption,
            "access_token": access_token
        }
        create_res = requests.post(create_url, data=create_payload, timeout=15)
        create_data = create_res.json()
        if "id" not in create_data:
            return {"success": False, "error": create_data.get("error", "Container creation failed")}

        creation_id = create_data["id"]

        # Bước 2: Publish media
        publish_url = f"{cls.GRAPH_API_BASE}/{cls.get_version()}/{ig_user_id}/media_publish"
        publish_payload = {
            "creation_id": creation_id,
            "access_token": access_token
        }
        pub_res = requests.post(publish_url, data=publish_payload, timeout=15)
        pub_data = pub_res.json()
        if "id" not in pub_data:
            return {"success": False, "error": pub_data.get("error", "Publish failed")}

        ig_media_id = pub_data["id"]
        permalink = None
        try:
            detail_res = requests.get(
                f"{cls.GRAPH_API_BASE}/{cls.get_version()}/{ig_media_id}",
                params={"fields": "permalink", "access_token": access_token},
                timeout=10
            )
            permalink = detail_res.json().get("permalink")
        except Exception:
            pass

        return {
            "success": True,
            "ig_media_id": ig_media_id,
            "permalink": permalink or f"https://www.instagram.com/p/{ig_media_id}/"
        }

    @classmethod
    def publish_reel_to_instagram(
        cls,
        ig_user_id: str,
        access_token: str,
        video_url: str,
        caption: str
    ) -> Dict[str, Any]:
        """
        Đăng Reels/Video lên Instagram Business Account:
        Bước 1: Tạo media container với media_type='REELS'
        Bước 2: Polling container status (chờ trạng thái 'FINISHED')
        Bước 3: Phát hành (media_publish) và lấy permalink thật
        """
        create_url = f"{cls.GRAPH_API_BASE}/{cls.get_version()}/{ig_user_id}/media"
        create_payload = {
            "media_type": "REELS",
            "video_url": video_url,
            "caption": caption,
            "access_token": access_token
        }
        create_res = requests.post(create_url, data=create_payload, timeout=20)
        create_data = create_res.json()
        if "id" not in create_data:
            return {"success": False, "error": create_data.get("error", "Tạo Reel container thất bại")}

        creation_id = create_data["id"]

        # Polling container status (chờ tối đa 60 giây, mỗi lần 5 giây)
        attempts = 0
        ready = False
        while attempts < 12:
            time.sleep(5)
            attempts += 1
            try:
                status_res = requests.get(
                    f"{cls.GRAPH_API_BASE}/{cls.get_version()}/{creation_id}",
                    params={"fields": "status_code", "access_token": access_token},
                    timeout=10
                )
                s_data = status_res.json()
                code = s_data.get("status_code")
                if code == "FINISHED":
                    ready = True
                    break
                elif code == "ERROR":
                    return {"success": False, "error": f"Instagram container báo lỗi khi xử lý video: {s_data}"}
            except Exception as e:
                logger.warning(f"Lỗi khi polling Reel container status: {e}")

        if not ready:
            return {"success": False, "error": "Quá thời gian chờ Instagram xử lý video (timeout sau 60s)"}

        # Phát hành container
        publish_url = f"{cls.GRAPH_API_BASE}/{cls.get_version()}/{ig_user_id}/media_publish"
        publish_payload = {
            "creation_id": creation_id,
            "access_token": access_token
        }
        pub_res = requests.post(publish_url, data=publish_payload, timeout=20)
        pub_data = pub_res.json()
        if "id" not in pub_data:
            return {"success": False, "error": pub_data.get("error", "Xuất bản Reel thất bại")}

        ig_media_id = pub_data["id"]
        permalink = None
        try:
            detail_res = requests.get(
                f"{cls.GRAPH_API_BASE}/{cls.get_version()}/{ig_media_id}",
                params={"fields": "permalink", "access_token": access_token},
                timeout=10
            )
            permalink = detail_res.json().get("permalink")
        except Exception:
            pass

        return {
            "success": True,
            "ig_media_id": ig_media_id,
            "permalink": permalink or f"https://www.instagram.com/reel/{ig_media_id}/"
        }

    @classmethod
    def get_instagram_media_insights(cls, ig_media_id: str, access_token: str) -> Dict[str, Any]:
        """
        Lấy số liệu thống kê bài đăng Instagram (Likes, Comments, Reach, Impressions):
        Instagram Graph API cung cấp metric: impressions, reach, total_interactions, saved, video_views
        """
        # Lấy like và comments cơ bản
        media_url = f"{cls.GRAPH_API_BASE}/{cls.get_version()}/{ig_media_id}"
        media_params = {
            "fields": "like_count,comments_count,media_type,permalink",
            "access_token": access_token
        }
        media_res = requests.get(media_url, params=media_params, timeout=10)
        media_data = media_res.json()

        if "error" in media_data:
            return {"success": False, "error": media_data["error"]}

        likes = media_data.get("like_count", 0)
        comments = media_data.get("comments_count", 0)

        # Lấy insights chi tiết
        insights_url = f"{cls.GRAPH_API_BASE}/{cls.get_version()}/{ig_media_id}/insights"
        insights_params = {
            "metric": "impressions,reach,total_interactions",
            "access_token": access_token
        }
        insights_res = requests.get(insights_url, params=insights_params, timeout=10)
        insights_data = insights_res.json()

        reach = 0
        views = 0
        shares = 0
        for item in insights_data.get("data", []):
            name = item.get("name")
            val = item.get("values", [{}])[0].get("value", 0)
            if name == "reach":
                reach = val
            elif name == "impressions":
                views = val
            elif name == "total_interactions":
                # total_interactions = likes + comments + shares + saves
                shares = max(0, val - (likes + comments))

        return {
            "success": True,
            "reach_count": reach,
            "view_count": views,
            "like_count": likes,
            "comment_count": comments,
            "share_count": shares
        }
