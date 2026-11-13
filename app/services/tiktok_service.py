import time
import logging
from typing import Dict, Any, Optional
import requests
from urllib.parse import urlencode
from app.config import settings

logger = logging.getLogger("TikTokApiService")

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
            "video.upload",
            "video.publish"
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
    def publish_video_to_tiktok(
        cls,
        access_token: str,
        video_url: str,
        title: str,
        privacy_level: str = "PUBLIC_TO_EVERYONE"
    ) -> Dict[str, Any]:
        """
        Xuất bản video lên TikTok bằng Direct Post API v2 (PULL_FROM_URL).
        Bước 1: Khởi tạo tác vụ publish (/v2/post/publish/video/init/)
        Bước 2: Polling trạng thái xử lý (/v2/post/publish/status/fetch/)
        """
        init_url = f"{cls.API_BASE_URL}/post/publish/video/init/"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json; charset=UTF-8"
        }
        payload = {
            "post_info": {
                "title": title[:150],  # TikTok giới hạn độ dài caption
                "privacy_level": privacy_level,
                "disable_duet": False,
                "disable_stitch": False,
                "disable_comment": False,
                "video_cover_timestamp_ms": 1000
            },
            "source_info": {
                "source": "PULL_FROM_URL",
                "video_url": video_url
            }
        }

        try:
            res = requests.post(init_url, headers=headers, json=payload, timeout=20)
            res_data = res.json()
        except Exception as e:
            return {"success": False, "error": f"Lỗi kết nối khi gọi TikTok publish init: {str(e)}"}

        err_obj = res_data.get("error")
        if err_obj:
            if isinstance(err_obj, dict) and err_obj.get("code") != "ok":
                err_msg = err_obj.get("message") or res_data.get("error_description", "Lỗi khởi tạo đăng video TikTok")
                return {"success": False, "error": f"TikTok Direct Post Error: {err_msg}"}
            elif isinstance(err_obj, str) and err_obj != "ok":
                err_msg = res_data.get("error_description") or err_obj
                return {"success": False, "error": f"TikTok Direct Post Error: {err_msg}"}

        publish_id = res_data.get("data", {}).get("publish_id")
        if not publish_id:
            return {"success": False, "error": "TikTok không trả về publish_id"}

        # Polling kiểm tra trạng thái video
        status_url = f"{cls.API_BASE_URL}/post/publish/status/fetch/"
        status_payload = {"publish_id": publish_id}

        final_status = "PROCESSING"
        video_id = None
        attempts = 0
        while attempts < 6:
            time.sleep(3)
            attempts += 1
            try:
                s_res = requests.post(status_url, headers=headers, json=status_payload, timeout=15)
                s_data = s_res.json()
                data_body = s_data.get("data", {})
                current_status = data_body.get("status")

                # Trích xuất video_id thật từ TikTok status response
                post_ids = data_body.get("publicaly_available_post_id") or data_body.get("post_ids") or data_body.get("post_id")
                if post_ids:
                    if isinstance(post_ids, list) and len(post_ids) > 0:
                        video_id = str(post_ids[0])
                    elif isinstance(post_ids, (str, int)):
                        video_id = str(post_ids)

                if current_status == "PUBLISH_COMPLETE":
                    final_status = "PUBLISH_COMPLETE"
                    break
                elif current_status == "FAILED":
                    fail_reason = data_body.get("fail_reason", "Không rõ nguyên nhân")
                    return {"success": False, "error": f"TikTok xử lý video thất bại: {fail_reason}"}
                elif current_status in ["PROCESSING_DOWNLOAD", "PROCESSING_UPLOAD"]:
                    final_status = current_status
            except Exception as ex:
                logger.warning(f"Lỗi khi polling trạng thái TikTok: {ex}")

        pub_url = f"https://www.tiktok.com/video/{video_id}" if video_id else "https://www.tiktok.com"

        return {
            "success": True,
            "publish_id": publish_id,
            "video_id": video_id,
            "status": final_status,
            "published_url": pub_url
        }

    @classmethod
    def get_publish_status(cls, publish_id: str, access_token: str) -> Dict[str, Any]:
        """Truy vấn trạng thái của tác vụ xuất bản video TikTok."""
        url = f"{cls.API_BASE_URL}/post/publish/status/fetch/"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json; charset=UTF-8"
        }
        payload = {"publish_id": publish_id}
        try:
            res = requests.post(url, headers=headers, json=payload, timeout=15)
            return res.json()
        except Exception as e:
            return {"error": {"message": str(e)}}

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

        err_obj = res_data.get("error")
        if err_obj:
            is_err = False
            err_msg = "Không thể lấy thông tin video TikTok"
            if isinstance(err_obj, dict) and err_obj.get("code") != "ok":
                is_err = True
                err_msg = err_obj.get("message") or err_msg
            elif isinstance(err_obj, str) and err_obj != "ok":
                is_err = True
                err_msg = res_data.get("error_description") or err_obj
            if is_err:
                return {"success": False, "error": err_msg}

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
