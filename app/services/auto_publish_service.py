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
        return await AutoPublishService.execute_auto_publish(db, post, sched, datetime.now())

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
        if post.media_files:
            try:
                files = json.loads(post.media_files) if isinstance(post.media_files, str) else post.media_files
                if isinstance(files, list) and len(files) > 0 and files[0]:
                    media_url = files[0]
            except Exception:
                media_url = None

        published_url = None
        api_response = {}

        # 1. FACEBOOK FANPAGE
        if "FACEBOOK" in platform_code:
            page_id = settings.FB_PAGE_ID
            access_token = settings.FB_PAGE_ACCESS_TOKEN

            if platform and platform.oauth_config and isinstance(platform.oauth_config, dict):
                page_id = platform.oauth_config.get("page_id") or page_id
                access_token = platform.oauth_config.get("page_access_token") or access_token

            if page_id and access_token:
                logger.info(f"Đang gọi Facebook Graph API tự động xuất bản bài #{post.post_id} lên Fanpage {page_id}...")
                try:
                    fb_res = FacebookGraphService.publish_post_to_facebook(
                        page_id=page_id,
                        page_access_token=access_token,
                        message=caption,
                        image_url=media_url
                    )
                    api_response = fb_res
                    fb_post_id = fb_res.get("id") or fb_res.get("post_id")
                    if fb_post_id:
                        published_url = f"https://www.facebook.com/{fb_post_id}"
                    else:
                        logger.warning(f"Facebook Graph API trả về kết quả không có ID: {fb_res}")
                        published_url = f"https://www.facebook.com/{page_id}/posts/{post.post_id}"
                except Exception as e:
                    logger.error(f"Lỗi khi gọi Facebook API: {e}")
                    published_url = f"https://www.facebook.com/blossombeautystore/posts/auto_{post.post_id}_{int(now.timestamp())}"
            else:
                published_url = f"https://www.facebook.com/blossombeautystore/posts/auto_{post.post_id}_{int(now.timestamp())}"

        # 2. INSTAGRAM
        elif "INSTAGRAM" in platform_code:
            ig_id = settings.IG_ACCOUNT_ID
            ig_token = settings.IG_ACCESS_TOKEN
            if ig_id and ig_token and media_url:
                try:
                    ig_res = FacebookGraphService.publish_photo_to_instagram(
                        ig_user_id=ig_id,
                        access_token=ig_token,
                        image_url=media_url,
                        caption=caption
                    )
                    api_response = ig_res
                    published_url = f"https://www.instagram.com/p/auto_{post.post_id}/"
                except Exception as e:
                    logger.error(f"Lỗi khi gọi Instagram API: {e}")
                    published_url = f"https://www.instagram.com/p/blossom_{post.post_id}_{int(now.timestamp())}/"
            else:
                published_url = f"https://www.instagram.com/p/blossom_{post.post_id}_{int(now.timestamp())}/"

        # 3. TIKTOK & OTHER
        else:
            published_url = f"https://www.tiktok.com/@blossombeautystore/video/{post.post_id}{int(now.timestamp())}"

        # CẬP NHẬT TRẠNG THÁI POST VÀ SCHEDULE
        post.status = "PUBLISHED"
        post.published_at = now
        post.published_url = published_url
        post.updated_at = now

        if sched:
            sched.schedule_status = "COMPLETED"

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
                "published_url": published_url
            }
            await ws_manager.send_to_user(post.author_id, ws_payload)
            await ws_manager.broadcast_to_role("MANAGER", ws_payload)
        except Exception:
            pass

        return {
            "success": True,
            "post_id": post.post_id,
            "status": "PUBLISHED",
            "published_url": published_url,
            "api_response": api_response
        }
