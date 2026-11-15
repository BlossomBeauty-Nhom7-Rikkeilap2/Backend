-- ============================================================================
-- SEED DATA SCRIPT: DỮ LIỆU MẪU HỆ THỐNG QUẢN LÝ TRUYỀN THÔNG ĐA KÊNH
-- Task: T06A65C | Người thực hiện: Nguyễn Phát Đạt (N25DTCN082)
-- Sản phẩm: Seed 1 Manager, 4 Staff, 3 Nền tảng MXH và các bài viết mẫu
-- Mật khẩu mặc định cho các tài khoản mẫu: Password@123 (Bcrypt hash)
-- ============================================================================

USE multichannel_cms;

-- ------------------------------------------------------------------------------
-- 1. SEED BẢNG roles (2 vai trò cố định: MANAGER và STAFF)
-- ------------------------------------------------------------------------------
INSERT INTO roles (role_id, role_code, role_name, permissions) VALUES
(1, 'MANAGER', 'Marketing Manager', JSON_ARRAY('user.manage', 'post.view_all', 'post.approve', 'post.reject', 'schedule.manage', 'analytics.view', 'analytics.export')),
(2, 'STAFF', 'Marketing Staff', JSON_ARRAY('post.create', 'post.edit_own', 'post.delete_own', 'post.submit', 'schedule.view', 'post.publish', 'stats.update'))
ON DUPLICATE KEY UPDATE role_name = VALUES(role_name);

-- ------------------------------------------------------------------------------
-- 2. SEED BẢNG users (1 Marketing Manager & 4 Marketing Staff)
-- Bcrypt hash của 'Password@123': $2b$12$KIX/y7Z1w6n8Q2v.6X8uOu7yH5mX5L2G9x1J6R0p4W3v8N2q1Y5eC
-- ------------------------------------------------------------------------------
INSERT INTO users (user_id, username, email, password_hash, full_name, role_id, avatar_url, status, last_login_at) VALUES
(1, 'minhanh_mgr', 'minhanh.manager@kbeauty.vn', '$2b$12$KIX/y7Z1w6n8Q2v.6X8uOu7yH5mX5L2G9x1J6R0p4W3v8N2q1Y5eC', 'Đoãn Thị Minh Anh (Manager)', 1, 'https://ui-avatars.com/api/?name=Minh+Anh&background=E1306C&color=fff', 'ACTIVE', NOW()),
(2, 'conghuy_staff', 'conghuy.staff@kbeauty.vn', '$2b$12$KIX/y7Z1w6n8Q2v.6X8uOu7yH5mX5L2G9x1J6R0p4W3v8N2q1Y5eC', 'Trịnh Trần Công Huy (Staff)', 2, 'https://ui-avatars.com/api/?name=Cong+Huy&background=1877F2&color=fff', 'ACTIVE', NOW()),
(3, 'phatdat_staff', 'phatdat.staff@kbeauty.vn', '$2b$12$KIX/y7Z1w6n8Q2v.6X8uOu7yH5mX5L2G9x1J6R0p4W3v8N2q1Y5eC', 'Nguyễn Phát Đạt (Staff)', 2, 'https://ui-avatars.com/api/?name=Phat+Dat&background=00F2FE&color=000', 'ACTIVE', NOW()),
(4, 'hoangson_staff', 'hoangson.staff@kbeauty.vn', '$2b$12$KIX/y7Z1w6n8Q2v.6X8uOu7yH5mX5L2G9x1J6R0p4W3v8N2q1Y5eC', 'Phan Hoàng Sơn (Staff)', 2, 'https://ui-avatars.com/api/?name=Hoang+Son&background=82b366&color=fff', 'ACTIVE', NOW()),
(5, 'phuongthao_staff', 'phuongthao.staff@kbeauty.vn', '$2b$12$KIX/y7Z1w6n8Q2v.6X8uOu7yH5mX5L2G9x1J6R0p4W3v8N2q1Y5eC', 'Lê Phương Thảo (Staff)', 2, 'https://ui-avatars.com/api/?name=Phuong+Thao&background=9673a6&color=fff', 'ACTIVE', NOW())
ON DUPLICATE KEY UPDATE full_name = VALUES(full_name);

-- ------------------------------------------------------------------------------
-- 3. SEED BẢNG platforms (3 nền tảng truyền thông: Facebook, Instagram, TikTok)
-- ------------------------------------------------------------------------------
INSERT INTO platforms (platform_id, platform_code, platform_name, channel_url, color_hex, is_active) VALUES
(1, 'FACEBOOK', 'Facebook Fanpage', 'https://www.facebook.com/KBeautyCosmeticsVN', '#1877F2', TRUE),
(2, 'INSTAGRAM', 'Instagram Business', 'https://www.instagram.com/kbeauty.official.vn', '#E1306C', TRUE),
(3, 'TIKTOK', 'TikTok Official', 'https://www.tiktok.com/@kbeauty.vietnam', '#00F2FE', TRUE)
ON DUPLICATE KEY UPDATE platform_name = VALUES(platform_name);

-- ------------------------------------------------------------------------------
-- 4. SEED BẢNG posts (6 bài viết mẫu phủ đều các trạng thái và nền tảng)
-- ------------------------------------------------------------------------------
INSERT INTO posts (
    post_id, title, caption, hashtags, platform_id, author_id,
    media_type, media_files, total_media_size_bytes,
    planned_publish_time, status, published_url, published_at
) VALUES
-- Post 1: PUBLISHED (Facebook)
(1, 'Ra mắt Serum Vitamin C Hàn Quốc sáng da mờ thâm',
 'Bí quyết cho làn da căng bóng chuẩn Hàn! Tinh chất Vitamin C nguyên chất 15% giúp mờ thâm sạm chỉ sau 14 ngày sử dụng.',
 '#KBeauty #SerumVitaminC #SkincareHanQuoc #SangDaMoTham',
 1, 2, 'IMAGE',
 JSON_ARRAY(JSON_OBJECT('url', 'https://cdn.kbeauty.vn/media/serum-vitc-01.jpg', 'file_name', 'serum-vitc-01.jpg', 'mime_type', 'image/jpeg', 'size_bytes', 2450000)),
 2450000, DATE_SUB(NOW(), INTERVAL 3 DAY), 'PUBLISHED',
 'https://www.facebook.com/KBeautyCosmeticsVN/posts/1010101', DATE_SUB(NOW(), INTERVAL 3 DAY)),

-- Post 2: PUBLISHED (TikTok)
(2, 'Review Kem chống nắng nâng tông kiềm dầu 12h',
 'Test độ kiềm dầu của kem chống nắng quốc dân Hàn Quốc dưới nắng Sài Gòn 38 độ! Không bết dính, nâng tông tự nhiên.',
 '#KemChongNang #TikTokBeauty #MyPhamHanQuoc #ReviewLamDep',
 3, 3, 'VIDEO',
 JSON_ARRAY(JSON_OBJECT('url', 'https://cdn.kbeauty.vn/media/sunscreen-test.mp4', 'file_name', 'sunscreen-test.mp4', 'mime_type', 'video/mp4', 'size_bytes', 18500000)),
 18500000, DATE_SUB(NOW(), INTERVAL 1 DAY), 'PUBLISHED',
 'https://www.tiktok.com/@kbeauty.vietnam/video/72938475610', DATE_SUB(NOW(), INTERVAL 1 DAY)),

-- Post 3: SCHEDULED (Instagram)
(3, 'Tips dưỡng ẩm phục hồi ban đêm cho da đang treatment',
 'Da đang dùng Retinol hoặc BHA thì không thể bỏ qua kem dưỡng ẩm B5 rau má lên men này nhé cả nhà ơi!',
 '#PhucHoiDa #B5RauMa #TreatmentSkincare #InstagramBeauty',
 2, 4, 'IMAGE',
 JSON_ARRAY(JSON_OBJECT('url', 'https://cdn.kbeauty.vn/media/b5-night-care.jpg', 'file_name', 'b5-night-care.jpg', 'mime_type', 'image/jpeg', 'size_bytes', 3200000)),
 3200000, DATE_ADD(NOW(), INTERVAL 1 DAY), 'SCHEDULED', NULL, NULL),

-- Post 4: APPROVED (Facebook)
(4, 'Minigame: Đoán đúng thành phần - Nhận ngay quà khủng',
 'Cơ hội nhận trọn bộ kit dưỡng ẩm du lịch trị giá 500.000 VNĐ khi comment đúng tên thành phần bí mật trong video!',
 '#Minigame #Giveaway #MyPhamHanQuoc #KBeautyVN',
 1, 5, 'IMAGE',
 JSON_ARRAY(JSON_OBJECT('url', 'https://cdn.kbeauty.vn/media/minigame-banner.jpg', 'file_name', 'minigame-banner.jpg', 'mime_type', 'image/jpeg', 'size_bytes', 4100000)),
 4100000, DATE_ADD(NOW(), INTERVAL 2 DAY), 'APPROVED', NULL, NULL),

-- Post 5: PENDING_APPROVAL (TikTok)
(5, 'Top 5 màu son MLBB hot nhất mùa lễ hội cuối năm',
 'Tone màu tự nhiên tôn da châu Á, chất son kem lì mịn mượt như nhung không gây khô môi.',
 '#SonMoi #MLBB #SonKemLi #TikTokTrending #MakeupTutorial',
 3, 2, 'VIDEO',
 JSON_ARRAY(JSON_OBJECT('url', 'https://cdn.kbeauty.vn/media/lipstick-swatch.mp4', 'file_name', 'lipstick-swatch.mp4', 'mime_type', 'video/mp4', 'size_bytes', 35000000)),
 35000000, DATE_ADD(NOW(), INTERVAL 3 DAY), 'PENDING_APPROVAL', NULL, NULL),

-- Post 6: DRAFT (Instagram)
(6, 'Bản thảo chiến dịch Sale Black Friday giảm giá tới 50%',
 'Chương trình ưu đãi lớn nhất năm giảm tới 50% toàn bộ sản phẩm dưỡng ẩm và bảo vệ da mùa đông.',
 '#BlackFriday #Sale50 #KBeautySale #UuDaiCuoiNam',
 2, 3, 'IMAGE',
 JSON_ARRAY(JSON_OBJECT('url', 'https://cdn.kbeauty.vn/media/draft-bf-sale.jpg', 'file_name', 'draft-bf-sale.jpg', 'mime_type', 'image/jpeg', 'size_bytes', 1500000)),
 1500000, NULL, 'DRAFT', NULL, NULL)
ON DUPLICATE KEY UPDATE title = VALUES(title);

-- ------------------------------------------------------------------------------
-- 5. SEED BẢNG schedules (Lịch hẹn giờ cho Post 3)
-- ------------------------------------------------------------------------------
INSERT INTO schedules (
    schedule_id, post_id, scheduled_time, remind_before_minutes,
    is_reminded_30m, is_reminded_10m, is_overdue_alerted,
    schedule_status, scheduled_by
) VALUES
(1, 3, DATE_ADD(NOW(), INTERVAL 1 DAY), 30, FALSE, FALSE, FALSE, 'ACTIVE', 4)
ON DUPLICATE KEY UPDATE scheduled_time = VALUES(scheduled_time);

-- ------------------------------------------------------------------------------
-- 6. SEED BẢNG post_statistics (Thống kê cho các bài đã xuất bản Post 1 & Post 2)
-- ------------------------------------------------------------------------------
INSERT INTO post_statistics (stat_id, post_id, reach_count, view_count, like_count, comment_count, share_count, source_type) VALUES
(1, 1, 15420, 18900, 1250, 184, 96, 'API'),
(2, 2, 45200, 89300, 5420, 630, 820, 'API')
ON DUPLICATE KEY UPDATE reach_count = VALUES(reach_count);
