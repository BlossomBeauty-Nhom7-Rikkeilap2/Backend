import unittest
from unittest.mock import patch, MagicMock, AsyncMock
import io
import json
from datetime import datetime
from fastapi import UploadFile

from app.models.post import Post
from app.models.schedule import Schedule
from app.models.platform import Platform
from app.services.media_service import MediaUploadService
from app.services.facebook_service import FacebookGraphService
from app.services.tiktok_service import TikTokApiService
from app.services.auto_publish_service import AutoPublishService

class TestSocialMediaRepair(unittest.IsolatedAsyncioTestCase):

    def test_01_models_schema(self):
        """Kiểm tra schema CSDL của Post và Schedule đã có đầy đủ các cột mới."""
        post = Post(
            title="Bài viết test",
            platform_id=1,
            author_id=1,
            external_post_id="ext_123456",
            error_message="Lỗi thử nghiệm",
            retry_count=1,
            status="FAILED"
        )
        self.assertEqual(post.external_post_id, "ext_123456")
        self.assertEqual(post.error_message, "Lỗi thử nghiệm")
        self.assertEqual(post.retry_count, 1)
        self.assertEqual(post.status, "FAILED")

        sched = Schedule(
            post_id=1,
            scheduled_time=datetime.now(),
            schedule_status="FAILED",
            scheduled_by=1,
            retry_count=2
        )
        self.assertEqual(sched.schedule_status, "FAILED")
        self.assertEqual(sched.retry_count, 2)

    @patch("app.services.media_service.settings")
    @patch("app.services.media_service.MediaUploadService.get_s3_client", return_value=None)
    async def test_02_media_service_fallback_url(self, mock_s3, mock_settings):
        """Kiểm tra nếu upload R2 thất bại/không có token thì URL trả về phải là /uploads/ chứ không phải R2_PUBLIC_URL."""
        mock_settings.R2_PUBLIC_URL = "https://pub-49e7128ed9044cc8afb86fbafbb282d1.r2.dev"
        mock_settings.LOCAL_UPLOAD_DIR = "test_uploads"
        mock_settings.R2_BUCKET_NAME = ""

        file_content = b"dummy image content"
        file = UploadFile(filename="test_photo.jpg", file=io.BytesIO(file_content), headers={"content-type": "image/jpeg"})

        with patch("builtins.open", unittest.mock.mock_open()), patch("os.makedirs"):
            file_url, size, media_type = await MediaUploadService.validate_and_save(file)

        self.assertTrue(file_url.startswith("/uploads/"))
        self.assertNotIn("r2.dev", file_url)
        self.assertEqual(media_type, "IMAGE")

    def test_03_tiktok_scope_and_direct_post(self):
        """Kiểm tra TikTok OAuth scope bao gồm video.publish và hàm publish_video_to_tiktok."""
        auth_url = TikTokApiService.get_authorization_url(redirect_uri="http://localhost:5500/callback")
        self.assertIn("video.publish", auth_url)

        with patch("requests.post") as mock_post:
            # Mock init response
            mock_init_resp = MagicMock()
            mock_init_resp.json.return_value = {
                "data": {"publish_id": "v_pub_tiktok_999"},
                "error": {"code": "ok"}
            }
            # Mock status fetch response
            mock_status_resp = MagicMock()
            mock_status_resp.json.return_value = {
                "data": {"status": "PUBLISH_COMPLETE"},
                "error": {"code": "ok"}
            }
            mock_post.side_effect = [mock_init_resp, mock_status_resp]

            result = TikTokApiService.publish_video_to_tiktok(
                access_token="act_valid_token",
                video_url="https://example.com/video.mp4",
                title="Review son môi mới"
            )

            self.assertTrue(result["success"])
            self.assertEqual(result["publish_id"], "v_pub_tiktok_999")
            self.assertEqual(result["status"], "PUBLISH_COMPLETE")

    def test_04_facebook_video_and_album(self):
        """Kiểm tra Facebook Graph API đăng video và album nhiều ảnh."""
        # 1. Đăng video
        with patch("requests.post") as mock_post:
            mock_resp = MagicMock()
            mock_resp.json.return_value = {"id": "fb_video_12345"}
            mock_post.return_value = mock_resp

            res = FacebookGraphService.publish_video_to_facebook(
                page_id="page_123",
                page_access_token="token_abc",
                video_url="https://example.com/clip.mp4",
                description="Mô tả video",
                title="Tiêu đề clip"
            )
            self.assertEqual(res.get("id"), "fb_video_12345")

        # 2. Đăng album nhiều ảnh
        with patch("requests.post") as mock_post:
            photo_resp1 = MagicMock()
            photo_resp1.json.return_value = {"id": "photo_1"}
            photo_resp2 = MagicMock()
            photo_resp2.json.return_value = {"id": "photo_2"}
            feed_resp = MagicMock()
            feed_resp.json.return_value = {"id": "post_album_123"}

            mock_post.side_effect = [photo_resp1, photo_resp2, feed_resp]

            res_album = FacebookGraphService.publish_album_to_facebook(
                page_id="page_123",
                page_access_token="token_abc",
                message="Album ảnh mùa hè",
                image_urls=["https://example.com/1.jpg", "https://example.com/2.jpg"]
            )
            self.assertEqual(res_album.get("id"), "post_album_123")

    def test_05_instagram_reel_with_polling(self):
        """Kiểm tra Instagram Reels đăng video với polling container và lấy permalink."""
        with patch("requests.post") as mock_post, patch("requests.get") as mock_get, patch("time.sleep"):
            # Mock container creation
            mock_create_resp = MagicMock()
            mock_create_resp.json.return_value = {"id": "container_reel_001"}
            # Mock publish
            mock_pub_resp = MagicMock()
            mock_pub_resp.json.return_value = {"id": "ig_media_reel_999"}
            mock_post.side_effect = [mock_create_resp, mock_pub_resp]

            # Mock status check (FINISHED) & detail permalink
            mock_status_resp = MagicMock()
            mock_status_resp.json.return_value = {"status_code": "FINISHED"}
            mock_detail_resp = MagicMock()
            mock_detail_resp.json.return_value = {"permalink": "https://www.instagram.com/reel/C123abc/"}
            mock_get.side_effect = [mock_status_resp, mock_detail_resp]

            res = FacebookGraphService.publish_reel_to_instagram(
                ig_user_id="ig_user_456",
                access_token="ig_token_xyz",
                video_url="https://example.com/reel.mp4",
                caption="Reels làm đẹp"
            )
            self.assertTrue(res["success"])
            self.assertEqual(res["ig_media_id"], "ig_media_reel_999")
            self.assertEqual(res["permalink"], "https://www.instagram.com/reel/C123abc/")

    @patch("app.services.auto_publish_service.settings")
    async def test_06_auto_publish_no_mock_returns_error(self, mock_settings):
        """Kiểm tra gỡ bỏ hoàn toàn mock: khi thiếu token hoặc không cấu hình, phải trả về {success: False} và không set PUBLISHED."""
        mock_settings.FB_PAGE_ID = ""
        mock_settings.FB_PAGE_ACCESS_TOKEN = ""
        mock_settings.IG_ACCOUNT_ID = ""
        mock_settings.IG_ACCESS_TOKEN = ""

        db_mock = MagicMock()
        # Mock Platform Facebook
        platform_fb = Platform(platform_id=1, platform_code="FACEBOOK", platform_name="Facebook")
        db_mock.query().filter().first.return_value = platform_fb

        post = Post(
            post_id=101,
            title="Bài viết không token",
            platform_id=1,
            author_id=1,
            status="APPROVED",
            media_files=json.dumps(["https://example.com/photo.jpg"])
        )

        res = await AutoPublishService.execute_auto_publish(db_mock, post, None, datetime.now())
        self.assertFalse(res["success"])
        self.assertIn("error", res)
        # Post KHÔNG được chuyển thành PUBLISHED
        self.assertNotEqual(post.status, "PUBLISHED")

    @patch("app.services.auto_publish_service.settings")
    async def test_07_auto_publish_instagram_no_mock(self, mock_settings):
        """Kiểm tra Instagram khi không có cấu hình token thật, không được tự sinh link blossom_... và không set PUBLISHED."""
        mock_settings.IG_ACCOUNT_ID = ""
        mock_settings.IG_ACCESS_TOKEN = ""

        db_mock = MagicMock()
        platform_ig = Platform(platform_id=2, platform_code="INSTAGRAM", platform_name="Instagram")
        db_mock.query().filter().first.return_value = platform_ig

        post = Post(
            post_id=202,
            title="Bài viết Instagram không token",
            platform_id=2,
            author_id=1,
            status="APPROVED",
            media_files=json.dumps(["https://example.com/photo.jpg"])
        )

        res = await AutoPublishService.execute_auto_publish(db_mock, post, None, datetime.now())
        self.assertFalse(res["success"])
        self.assertNotEqual(post.status, "PUBLISHED")
        self.assertIsNone(post.published_url)

    @patch("app.core.websocket.manager.broadcast_to_role", new_callable=AsyncMock)
    @patch("app.core.websocket.manager.send_to_user", new_callable=AsyncMock)
    @patch("app.services.auto_publish_service.AutoPublishService.execute_auto_publish")
    async def test_08_scheduler_retry_limit_and_cancellation(self, mock_publish, mock_ws_send, mock_ws_broadcast):
        """Kiểm tra xử lý retry trong Scheduler qua hàm thật process_active_schedules:
        nếu thất bại 3 lần thì hủy lịch (CANCELLED), đánh dấu FAILED và gửi PUBLISH_FAILED."""
        from app.services.scheduler_worker import process_active_schedules

        mock_publish.return_value = {"success": False, "error": "Graph API Token Expired"}

        post = Post(
            post_id=303,
            title="Bài viết lỗi API",
            author_id=10,
            status="SCHEDULED",
            retry_count=0
        )
        sched = Schedule(
            schedule_id=50,
            post_id=303,
            scheduled_time=datetime(2026, 1, 1, 10, 0, 0),
            schedule_status="ACTIVE",
            scheduled_by=10,
            retry_count=0
        )
        now = datetime(2026, 1, 1, 10, 5, 0)

        db_mock = MagicMock()
        db_mock.query().join().filter().all.return_value = [(sched, post)]

        # Chu kỳ 1: Thất bại lần 1
        count1 = await process_active_schedules(db_mock, now)
        self.assertEqual(count1, 1)
        self.assertEqual(sched.retry_count, 1)
        self.assertEqual(sched.schedule_status, "ACTIVE")
        self.assertEqual(post.status, "SCHEDULED")

        # Chu kỳ 2: Thất bại lần 2
        count2 = await process_active_schedules(db_mock, now)
        self.assertEqual(count2, 1)
        self.assertEqual(sched.retry_count, 2)
        self.assertEqual(sched.schedule_status, "ACTIVE")
        self.assertEqual(post.status, "SCHEDULED")

        # Chu kỳ 3: Thất bại lần 3 -> Hủy lịch, chuyển FAILED
        count3 = await process_active_schedules(db_mock, now)
        self.assertEqual(count3, 1)
        self.assertEqual(sched.retry_count, 3)
        self.assertEqual(sched.schedule_status, "CANCELLED")
        self.assertEqual(post.status, "FAILED")
        self.assertEqual(post.error_message, "Graph API Token Expired")

        # Xác minh WebSocket gửi PUBLISH_FAILED
        self.assertTrue(mock_ws_send.called)
        self.assertTrue(mock_ws_broadcast.called)
        send_payload = mock_ws_send.call_args[0][1]
        self.assertEqual(send_payload["type"], "PUBLISH_FAILED")
        self.assertEqual(send_payload["post_id"], 303)

    @patch("app.routers.social.AnalyticsService.record_statistics")
    @patch("app.routers.social.FacebookGraphService.get_facebook_post_insights")
    @patch("app.routers.social.settings")
    def test_09_social_sync_auto_endpoint(self, mock_settings, mock_insights, mock_record):
        """Kiểm tra endpoint tự động đồng bộ thống nhất POST /social/posts/{post_id}/sync không cần client truyền ID/token."""
        from app.routers.social import sync_post_statistics_auto
        from app.models.user import User

        mock_settings.FB_PAGE_ACCESS_TOKEN = "valid_fb_token"
        mock_insights.return_value = {
            "success": True,
            "reach_count": 1200,
            "view_count": 3500,
            "like_count": 450,
            "comment_count": 60,
            "share_count": 25
        }
        mock_record.return_value = MagicMock(
            statistic_id=1,
            post_id=404,
            reach_count=1200,
            view_count=3500,
            like_count=450,
            comment_count=60,
            share_count=25,
            source_type="API"
        )

        post = Post(
            post_id=404,
            title="Bài viết đã xuất bản FB",
            platform_id=1,
            external_post_id="1449291238269103_998877",
            status="PUBLISHED"
        )
        platform = Platform(platform_id=1, platform_code="FACEBOOK", platform_name="Facebook Fanpage")
        user = User(user_id=1, username="admin")

        db_mock = MagicMock()
        db_mock.query().filter().first.side_effect = [post, platform]

        result = sync_post_statistics_auto(post_id=404, current_user=user, db=db_mock)

        mock_insights.assert_called_once_with("1449291238269103_998877", "valid_fb_token")
        self.assertTrue(mock_record.called)
        stat_in_arg = mock_record.call_args[0][2]
        self.assertEqual(stat_in_arg.reach_count, 1200)
        self.assertEqual(stat_in_arg.source_type, "API")

    def test_10_tiktok_error_handling_string_and_dict(self):
        """Kiểm tra TikTok API khi trả về error là chuỗi hoặc dictionary không bao giờ gây AttributeError."""
        # 1. Error là chuỗi
        with patch("requests.post") as mock_post:
            resp_str_err = MagicMock()
            resp_str_err.json.return_value = {
                "error": "invalid_grant",
                "error_description": "Authorization code expired"
            }
            mock_post.return_value = resp_str_err

            res = TikTokApiService.publish_video_to_tiktok("token", "https://ex.com/vid.mp4", "Title")
            self.assertFalse(res["success"])
            self.assertIn("Authorization code expired", res["error"])

        # 2. Error là dictionary
        with patch("requests.post") as mock_post:
            resp_dict_err = MagicMock()
            resp_dict_err.json.return_value = {
                "error": {
                    "code": "spam_risk_user",
                    "message": "User is restricted from posting"
                }
            }
            mock_post.return_value = resp_dict_err

            res_dict = TikTokApiService.publish_video_to_tiktok("token", "https://ex.com/vid.mp4", "Title")
            self.assertFalse(res_dict["success"])
            self.assertIn("User is restricted from posting", res_dict["error"])

    @patch("app.routers.social.AnalyticsService.record_statistics")
    @patch("app.routers.social.TikTokApiService.get_video_insights")
    @patch("app.routers.social.TikTokApiService.get_publish_status")
    def test_11_tiktok_sync_with_publish_id_lookup(self, mock_status, mock_insights, mock_record):
        """Kiểm tra khi bài viết TikTok chỉ lưu publish_id (v_pub_), sync tự động tra cứu video_id thật."""
        from app.routers.social import sync_post_statistics_auto
        from app.models.user import User

        mock_status.return_value = {
            "data": {
                "status": "PUBLISH_COMPLETE",
                "publicaly_available_post_id": ["7123456789012345678"]
            }
        }
        mock_insights.return_value = {
            "success": True,
            "reach_count": 5000,
            "view_count": 5000,
            "like_count": 800,
            "comment_count": 40,
            "share_count": 100
        }
        mock_record.return_value = MagicMock()

        post = Post(
            post_id=505,
            title="Video TikTok",
            platform_id=3,
            external_post_id="v_pub_tiktok_abc123",
            status="PUBLISHED"
        )
        platform = Platform(
            platform_id=3,
            platform_code="TIKTOK",
            platform_name="TikTok",
            oauth_config={"access_token": "valid_tt_token"}
        )
        user = User(user_id=1, username="admin")

        db_mock = MagicMock()
        db_mock.query().filter().first.side_effect = [post, platform]

        sync_post_statistics_auto(post_id=505, current_user=user, db=db_mock)

        # Đã tra cứu status từ v_pub_
        mock_status.assert_called_once_with("v_pub_tiktok_abc123", "valid_tt_token")
        # Post được cập nhật external_post_id thành video_id thật
        self.assertEqual(post.external_post_id, "7123456789012345678")
        # Đã gọi insights với video_id thật
        mock_insights.assert_called_once_with("7123456789012345678", "valid_tt_token")

    @patch("app.services.facebook_service.FacebookGraphService.publish_post_to_facebook")
    @patch("app.services.auto_publish_service.settings")
    async def test_12_relative_media_url_normalized(self, mock_settings, mock_fb_pub):
        """Kiểm tra URL tương đối (/uploads/...) được tự động chuẩn hóa thành public URL trước khi gửi tới API."""
        mock_settings.FB_PAGE_ID = "page_999"
        mock_settings.FB_PAGE_ACCESS_TOKEN = "token_999"

        mock_fb_pub.return_value = {"id": "fb_post_999"}

        post = Post(
            post_id=606,
            title="Bài viết ảnh cục bộ",
            platform_id=1,
            author_id=1,
            status="SCHEDULED",
            media_files=json.dumps(["/uploads/my_photo.jpg"])
        )
        platform = Platform(platform_id=1, platform_code="FACEBOOK", platform_name="Facebook")

        db_mock = MagicMock()
        db_mock.query().filter().first.return_value = platform

        res = await AutoPublishService.execute_auto_publish(db_mock, post, None, datetime.now())

        self.assertTrue(res["success"])
        # Kiểm tra URL truyền vào publish_post_to_facebook đã được biến đổi thành https://...
        passed_url = mock_fb_pub.call_args[1]["image_url"]
        self.assertTrue(passed_url.startswith("https://"))
        self.assertIn("/uploads/my_photo.jpg", passed_url)

if __name__ == "__main__":
    unittest.main()
