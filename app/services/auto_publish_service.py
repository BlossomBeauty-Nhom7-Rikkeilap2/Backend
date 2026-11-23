import json
import logging
import mimetypes
import os
from datetime import datetime
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session

from app.models.post import Post
from app.models.schedule import Schedule
from app.models.notification import Notification
from app.models.user import User
from app.models.platform import Platform
from app.services.facebook_service import FacebookGraphService, ThreadsGraphService
from app.services.media_service import MediaUploadService
from app.core.websocket import manager as ws_manager
from app.config import settings

logger = logging.getLogger("AutoPublish")

class AutoPublishService:
    @staticmethod
    def _ensure_public_media_url(db: Session, post: Post, media_url: str) -> str:
        """Neu media_url la tep cuc bo (/uploads/...), tu dong day len R2 de co URL HTTPS cong khai cho Meta."""
        is_local = media_url.startswith("/uploads/") or (
            ("localhost" in media_url or "127.0.0.1" in media_url) and "/uploads/" in media_url
        )
        if not is_local:
            return media_url

        filename = media_url.split("/uploads/")[-1].split("?")[0]
        local_path = os.path.join(settings.LOCAL_UPLOAD_DIR, filename)
        if not os.path.exists(local_path):
            return media_url

        s3_client = MediaUploadService.get_s3_client()
        if not (s3_client and settings.R2_BUCKET_NAME and settings.R2_PUBLIC_URL):
            return media_url

        try:
            content_type, _ = mimetypes.guess_type(local_path)
            with open(local_path, "rb") as f:
                s3_client.put_object(
                    Bucket=settings.R2_BUCKET_NAME,
                    Key=filename,
                    Body=f.read(),
                    ContentType=content_type or "application/octet-stream"
                )
            public_url = f"{settings.R2_PUBLIC_URL.rstrip('/')}/{filename}"
            post.media_files = [public_url]
            db.commit()
            logger.info(f"Da tu dong day anh cuc bo len R2 cho bai #{post.post_id}: {public_url}")
            return public_url
        except Exception as e:
            logger.error(f"Khong the day anh cuc bo len R2 cho bai #{post.post_id}: {e}")
            return media_url

    @staticmethod
    async def publish_post_now(db: Session, post_id: int, current_user: Optional[User] = None) -> Dict[str, Any]:
        """Tự động xuất bản ngay lập tức một bài viết đã duyệt hoặc đã lên lịch."""
        post = db.query(Post).filter(Post.post_id == post_id, Post.deleted_at.is_(None)).first()
        if not post:
            return {"success": False, "error": "Không tìm thấy bài viết"}

        if current_user and current_user.role and current_user.role.role_code == "STAFF":
            if post.author_id != current_user.user_id:
                return {"success": False, "error": "Bạn chỉ có thể tự động xuất bản bài viết của chính mình"}

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

        # Neu media_url la duong dan cuc bo (/uploads/... hoac localhost), tu dong day len Cloudflare R2 neu R2 da cau hinh
        if media_url:
            media_url = AutoPublishService._ensure_public_media_url(db, post, media_url)
            if media_url and (media_url.startswith("/") or "localhost" in media_url or "127.0.0.1" in media_url):
                return {
                    "success": False,
                    "error": "Ảnh đính kèm đang lưu cục bộ (/uploads/...) nên Facebook/Instagram không thể tải được. Vui lòng khởi động lại Backend để nạp cấu hình Cloudflare R2 rồi thử lại."
                }

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
                    if "error" in fb_res:
                        error_detail = fb_res["error"].get("message", "Lỗi từ Facebook API")
                        logger.error(f"Facebook Graph API trả về lỗi: {error_detail}")
                        return {
                            "success": False,
                            "error": f"Lỗi Facebook API: {error_detail}"
                        }

                    fb_post_id = fb_res.get("id") or fb_res.get("post_id")
                    if fb_post_id:
                        published_url = f"https://www.facebook.com/{fb_post_id}"
                    else:
                        published_url = f"https://www.facebook.com/{page_id}/posts/{post.post_id}"
                except Exception as e:
                    logger.error(f"Lỗi kết nối Facebook API: {e}")
                    return {
                        "success": False,
                        "error": f"Lỗi kết nối mạng khi gọi Facebook API: {str(e)}"
                    }
            else:
                # Chưa cấu hình Token Fanpage thật
                err_msg = "Chưa cấu hình FB_PAGE_ID hoặc FB_PAGE_ACCESS_TOKEN trong file .env để đăng bài lên Fanpage thật!"
                logger.warning(err_msg)
                return {
                    "success": False,
                    "error": err_msg
                }

        # 2. INSTAGRAM
        elif "INSTAGRAM" in platform_code:
            ig_id = settings.IG_ACCOUNT_ID
            ig_token = settings.IG_ACCESS_TOKEN
            if not ig_id or not ig_token:
                return {
                    "success": False,
                    "error": "Chưa cấu hình IG_ACCOUNT_ID hoặc IG_ACCESS_TOKEN trong file .env để đăng bài lên Instagram thật!"
                }

            if not media_url:
                return {
                    "success": False,
                    "error": "Instagram yêu cầu bắt buộc phải có ít nhất 1 hình ảnh hoặc video công khai (media_files) để đăng bài."
                }

            try:
                logger.info(f"Đang gọi Instagram Content Publishing API cho bài #{post.post_id} lên tài khoản {ig_id}...")
                ig_res = FacebookGraphService.publish_photo_to_instagram(
                    ig_user_id=ig_id,
                    access_token=ig_token,
                    image_url=media_url,
                    caption=caption
                )
                api_response = ig_res
                if not ig_res.get("success"):
                    error_detail = ig_res.get("error", "Lỗi từ Instagram API")
                    logger.error(f"Instagram Graph API trả về lỗi: {error_detail}")
                    return {
                        "success": False,
                        "error": f"Lỗi Instagram API: {error_detail}"
                    }

                published_url = ig_res.get("permalink") or f"https://www.instagram.com/p/{ig_res.get('ig_media_id')}/"
            except Exception as e:
                logger.error(f"Lỗi kết nối khi gọi Instagram API: {e}")
                return {
                    "success": False,
                    "error": f"Lỗi kết nối mạng khi gọi Instagram API: {str(e)}"
                }

        # 3. THREADS & OTHER
        else:
            threads_uid = settings.THREADS_USER_ID
            threads_token = settings.THREADS_ACCESS_TOKEN

            if threads_uid and threads_token:
                try:
                    logger.info(f"Đang gọi Threads Graph API cho bài #{post.post_id} lên tài khoản {threads_uid}...")
                    th_res = ThreadsGraphService.publish_thread(
                        threads_user_id=threads_uid,
                        access_token=threads_token,
                        text=caption,
                        image_url=media_url
                    )
                    api_response = th_res
                    if not th_res.get("success"):
                        error_detail = th_res.get("error", "Lỗi từ Threads API")
                        logger.error(f"Threads Graph API trả về lỗi: {error_detail}")
                        return {
                            "success": False,
                            "error": f"Lỗi Threads API: {error_detail}"
                        }
                    published_url = th_res.get("permalink") or f"https://www.threads.net/post/{th_res.get('threads_media_id')}"
                except Exception as e:
                    logger.error(f"Lỗi khi gọi Threads API: {e}")
                    return {
                        "success": False,
                        "error": f"Lỗi kết nối mạng khi gọi Threads API: {str(e)}"
                    }
            else:
                err_msg = "Chưa cấu hình THREADS_USER_ID hoặc THREADS_ACCESS_TOKEN trong file .env để đăng bài lên Threads thật!"
                logger.warning(err_msg)
                return {
                    "success": False,
                    "error": err_msg
                }

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
            title="Tự động xuất bản thành công!",
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
