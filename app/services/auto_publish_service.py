import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session

from app.models.post import Post
from app.models.schedule import Schedule
from app.models.notification import Notification
from app.models.user import User
from app.models.platform import Platform
from app.services.facebook_service import FacebookGraphService
from app.services.tiktok_service import TikTokApiService
from app.core.websocket import manager as ws_manager
from app.config import settings

logger = logging.getLogger("AutoPublish")

class AutoPublishService:
    @staticmethod
    async def publish_post_now(db: Session, post_id: int, current_user: Optional[User] = None) -> Dict[str, Any]:
        """Tự động xuất bản ngay lập tức một bài viết đã duyệt hoặc đã lên lịch."""
        post = db.query(Post).filter(Post.post_id == post_id, Post.deleted_at.is_(None)).first()
        if not post:
            return {"success": False, "error": "Không tìm thấy bài viết"}
        
        if post.status not in ["APPROVED", "SCHEDULED"]:
            return {"success": False, "error": f"Chỉ có thể tự động đăng bài viết đã duyệt (APPROVED) hoặc đã lên lịch (SCHEDULED). Trạng thái hiện tại: {post.status}"}

        sched = db.query(Schedule).filter(Schedule.post_id == post_id).first()
        res = await AutoPublishService.execute_auto_publish(db, post, sched, datetime.now())
        if not res.get("success"):
            post.error_message = res.get("error")
            post.status = "FAILED"
            db.commit()
        return res

    @staticmethod
    async def execute_auto_publish(db: Session, post: Post, sched: Optional[Schedule], now: datetime) -> Dict[str, Any]:
        """Thực hiện đăng bài tự động 100% qua API mạng xã hội tương ứng."""
        platform = db.query(Platform).filter(Platform.platform_id == post.platform_id).first()
        platform_name = platform.platform_name if platform else "Mạng xã hội"
        platform_code = (platform.platform_code if platform else "FACEBOOK").upper()

        caption = (post.caption or post.title or "").strip()
        if post.hashtags:
            caption += f"\n\n{post.hashtags}"

        media_url = None
        media_list = []
        if post.media_files:
            try:
                files = json.loads(post.media_files) if isinstance(post.media_files, str) else post.media_files
                if isinstance(files, list):
                    media_list = [f for f in files if f]
                    if len(media_list) > 0:
                        media_url = media_list[0]
                elif isinstance(files, str) and files:
                    media_url = files
                    media_list = [files]
            except Exception:
                media_url = None
                media_list = []

        # Chuẩn hóa media_url thành public URL nếu đang là đường dẫn cục bộ /uploads/
        public_base = "https://backend-facj.onrender.com"
        if media_url and media_url.startswith("/"):
            media_url = f"{public_base}{media_url}"
        if media_list:
            media_list = [f"{public_base}{m}" if m.startswith("/") else m for m in media_list]

        published_url = None
        external_post_id = None
        api_response = {}

        # 1. FACEBOOK FANPAGE
        if "FACEBOOK" in platform_code:
            page_id = settings.FB_PAGE_ID
            access_token = settings.FB_PAGE_ACCESS_TOKEN

            if platform and platform.oauth_config and isinstance(platform.oauth_config, dict):
                page_id = platform.oauth_config.get("page_id") or page_id
                access_token = platform.oauth_config.get("page_access_token") or access_token

            if not page_id or not access_token:
                err_msg = "Chưa cấu hình FB_PAGE_ID hoặc FB_PAGE_ACCESS_TOKEN để xuất bản bài viết lên Facebook!"
                logger.warning(err_msg)
                return {"success": False, "error": err_msg}

            logger.info(f"Đang gọi Facebook Graph API tự động xuất bản bài #{post.post_id} lên Fanpage {page_id}...")
            try:
                if post.media_type == "VIDEO" and media_url:
                    fb_res = await asyncio.to_thread(
                        FacebookGraphService.publish_video_to_facebook,
                        page_id=page_id,
                        page_access_token=access_token,
                        video_url=media_url,
                        description=caption,
                        title=post.title
                    )
                elif len(media_list) > 1:
                    fb_res = await asyncio.to_thread(
                        FacebookGraphService.publish_album_to_facebook,
                        page_id=page_id,
                        page_access_token=access_token,
                        message=caption,
                        image_urls=media_list
                    )
                else:
                    fb_res = await asyncio.to_thread(
                        FacebookGraphService.publish_post_to_facebook,
                        page_id=page_id,
                        page_access_token=access_token,
                        message=caption,
                        image_url=media_url
                    )

                api_response = fb_res
                if "error" in fb_res:
                    error_detail = fb_res["error"].get("message", "Lỗi từ Facebook API")
                    logger.error(f"Facebook Graph API trả về lỗi: {error_detail}")
                    return {"success": False, "error": f"Lỗi Facebook API: {error_detail}"}

                external_post_id = fb_res.get("id") or fb_res.get("post_id")
                if external_post_id:
                    published_url = f"https://www.facebook.com/{external_post_id}"
                else:
                    published_url = f"https://www.facebook.com/{page_id}/posts/{post.post_id}"
            except Exception as e:
                logger.error(f"Lỗi kết nối Facebook API: {e}")
                return {"success": False, "error": f"Lỗi kết nối mạng khi gọi Facebook API: {str(e)}"}

        # 2. INSTAGRAM
        elif "INSTAGRAM" in platform_code:
            ig_id = settings.IG_ACCOUNT_ID
            ig_token = settings.IG_ACCESS_TOKEN

            if platform and platform.oauth_config and isinstance(platform.oauth_config, dict):
                ig_id = platform.oauth_config.get("ig_account_id") or platform.oauth_config.get("account_id") or ig_id
                ig_token = platform.oauth_config.get("access_token") or ig_token

            if not ig_id or not ig_token:
                err_msg = "Chưa cấu hình IG_ACCOUNT_ID hoặc IG_ACCESS_TOKEN để xuất bản lên Instagram!"
                logger.warning(err_msg)
                return {"success": False, "error": err_msg}

            if not media_url:
                return {"success": False, "error": "Instagram bắt buộc phải có ít nhất 1 hình ảnh hoặc video để xuất bản!"}

            logger.info(f"Đang gọi Instagram Graph API xuất bản bài #{post.post_id} lên Instagram {ig_id}...")
            try:
                if post.media_type == "VIDEO":
                    ig_res = await asyncio.to_thread(
                        FacebookGraphService.publish_reel_to_instagram,
                        ig_user_id=ig_id,
                        access_token=ig_token,
                        video_url=media_url,
                        caption=caption
                    )
                else:
                    ig_res = await asyncio.to_thread(
                        FacebookGraphService.publish_photo_to_instagram,
                        ig_user_id=ig_id,
                        access_token=ig_token,
                        image_url=media_url,
                        caption=caption
                    )

                api_response = ig_res
                if not ig_res.get("success"):
                    return {"success": False, "error": f"Lỗi Instagram API: {ig_res.get('error')}"}

                external_post_id = str(ig_res.get("ig_media_id"))
                published_url = ig_res.get("permalink") or f"https://www.instagram.com/p/{external_post_id}/"
            except Exception as e:
                logger.error(f"Lỗi khi gọi Instagram API: {e}")
                return {"success": False, "error": f"Lỗi kết nối khi gọi Instagram API: {str(e)}"}

        # 3. TIKTOK
        elif "TIKTOK" in platform_code:
            tiktok_token = None
            if platform and platform.oauth_config and isinstance(platform.oauth_config, dict):
                tiktok_token = platform.oauth_config.get("access_token")

            if not tiktok_token:
                err_msg = "Chưa kết nối tài khoản TikTok qua OAuth (hoặc chưa có Access Token) để xuất bản bài viết!"
                logger.warning(err_msg)
                return {"success": False, "error": err_msg}

            if not media_url or post.media_type != "VIDEO":
                return {"success": False, "error": "TikTok Direct Post API yêu cầu tệp video hợp lệ để xuất bản!"}

            logger.info(f"Đang gọi TikTok Direct Post API v2 xuất bản bài #{post.post_id}...")
            try:
                tt_res = await asyncio.to_thread(
                    TikTokApiService.publish_video_to_tiktok,
                    access_token=tiktok_token,
                    video_url=media_url,
                    title=caption
                )
                api_response = tt_res
                if not tt_res.get("success"):
                    return {"success": False, "error": f"Lỗi TikTok API: {tt_res.get('error')}"}

                external_post_id = str(tt_res.get("video_id") or tt_res.get("publish_id"))
                published_url = tt_res.get("published_url") or "https://www.tiktok.com"
            except Exception as e:
                logger.error(f"Lỗi khi gọi TikTok API: {e}")
                return {"success": False, "error": f"Lỗi kết nối khi gọi TikTok API: {str(e)}"}

        else:
            return {"success": False, "error": f"Nền tảng '{platform_code}' chưa được hỗ trợ xuất bản tự động."}

        # CẬP NHẬT TRẠNG THÁI POST VÀ SCHEDULE
        post.status = "PUBLISHED"
        post.published_at = now
        post.published_url = published_url
        post.external_post_id = external_post_id
        post.error_message = None
        post.retry_count = 0
        post.updated_at = now

        if sched:
            sched.schedule_status = "COMPLETED"
            sched.retry_count = 0

        # GỬI THÔNG BÁO CHO TÁC GIẢ VÀ QUẢN LÝ
        notif_msg = f"Bài viết '{post.title}' đã được hệ thống tự động xuất bản 100% lên {platform_name} vào lúc {now.strftime('%H:%M %d/%m/%Y')}!"
        author_notif = Notification(
            recipient_id=post.author_id,
            post_id=post.post_id,
            notification_type="SCHEDULE_REMINDER",
            title="Tự động xuất bản thành công! 🎉",
            message=notif_msg
        )
        db.add(author_notif)

        managers = db.query(User).join(User.role).filter(User.role.has(role_code="MANAGER")).all()
        for mgr in managers:
            if mgr.user_id != post.author_id:
                db.add(Notification(
                    recipient_id=mgr.user_id,
                    post_id=post.post_id,
                    notification_type="SCHEDULE_REMINDER",
                    title=f"Đã tự động đăng bài #{post.post_id}",
                    message=f"Bài viết '{post.title}' đã được tự động đăng lên {platform_name} theo lịch hẹn."
                ))

        db.commit()

        # BẮN REALTIME WEBSOCKET TỚI CẢ TÁC GIẢ VÀ TOÀN BỘ QUẢN LÝ
        try:
            ws_payload = {
                "type": "AUTO_PUBLISHED",
                "post_id": post.post_id,
                "title": post.title,
                "platform": platform_name,
                "published_url": published_url,
                "external_post_id": external_post_id
            }
            await ws_manager.send_to_user(post.author_id, ws_payload)
            await ws_manager.broadcast_to_role("MANAGER", ws_payload)
        except Exception:
            pass

        return {
            "success": True,
            "post_id": post.post_id,
            "external_post_id": external_post_id,
            "status": "PUBLISHED",
            "published_url": published_url,
            "api_response": api_response
        }
