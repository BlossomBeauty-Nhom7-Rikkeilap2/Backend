-- ==============================================================================
-- KỊCH BẢN KHỞI TẠO CƠ SỞ DỮ LIỆU CHUẨN (SQL DDL SCRIPT)
-- Dự án: Hệ thống Quản lý Truyền thông Đa kênh (Multi-Channel CMS)
-- Nhóm thực hiện: Nhóm 7 RikkeiLab 2
-- Chuẩn kỹ thuật: MySQL 8.0+ / MariaDB 10.6+ | Engine: InnoDB | Charset: utf8mb4
-- Nguồn tham chiếu: Bảng 17 - Tài liệu Thiết kế Hệ thống (SDD v1.1)
-- ==============================================================================

CREATE DATABASE IF NOT EXISTS multichannel_cms 
CHARACTER SET utf8mb4 
COLLATE utf8mb4_unicode_ci;

USE multichannel_cms;

-- ------------------------------------------------------------------------------
-- 1. BẢNG roles (Thực thể Vai trò & Quyền hạn)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS roles (
    role_id INT AUTO_INCREMENT PRIMARY KEY,
    role_code VARCHAR(30) NOT NULL UNIQUE,
    role_name VARCHAR(100) NOT NULL,
    permissions JSON NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ------------------------------------------------------------------------------
-- 2. BẢNG users (Thực thể Người dùng Hệ thống)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS users (
    user_id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE,
    email VARCHAR(150) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(100) NOT NULL,
    role_id INT NOT NULL,
    avatar_url VARCHAR(500) NULL,
    status ENUM('ACTIVE', 'LOCKED', 'DEACTIVATED') NOT NULL DEFAULT 'ACTIVE',
    failed_login_attempts INT NOT NULL DEFAULT 0,
    locked_until DATETIME NULL,
    last_login_at DATETIME NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_users_role FOREIGN KEY (role_id) REFERENCES roles(role_id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ------------------------------------------------------------------------------
-- 3. BẢNG platforms (Thực thể Nền tảng Truyền thông)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS platforms (
    platform_id INT AUTO_INCREMENT PRIMARY KEY,
    platform_code VARCHAR(30) NOT NULL UNIQUE,
    platform_name VARCHAR(100) NOT NULL,
    channel_url VARCHAR(500) NULL,
    color_hex VARCHAR(10) NOT NULL DEFAULT '#1877F2',
    oauth_config JSON NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ------------------------------------------------------------------------------
-- 4. BẢNG posts (Thực thể Bài viết Truyền thông)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS posts (
    post_id BIGINT AUTO_INCREMENT PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    caption TEXT NULL,
    hashtags VARCHAR(1000) NULL,
    platform_id INT NOT NULL,
    author_id INT NOT NULL,
    media_type ENUM('IMAGE', 'VIDEO') NOT NULL DEFAULT 'IMAGE',
    media_files JSON NULL,
    total_media_size_bytes BIGINT NOT NULL DEFAULT 0,
    planned_publish_time DATETIME NULL,
    status ENUM('DRAFT', 'PENDING_APPROVAL', 'REVISION_REQUESTED', 'REJECTED', 'APPROVED', 'SCHEDULED', 'PUBLISHED') NOT NULL DEFAULT 'DRAFT',
    published_url VARCHAR(1000) NULL,
    published_at DATETIME NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    deleted_at DATETIME NULL,
    CONSTRAINT fk_posts_platform FOREIGN KEY (platform_id) REFERENCES platforms(platform_id) ON DELETE RESTRICT,
    CONSTRAINT fk_posts_author FOREIGN KEY (author_id) REFERENCES users(user_id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ------------------------------------------------------------------------------
-- 5. BẢNG approvals (Thực thể Lịch sử Quy trình Phê duyệt)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS approvals (
    approval_id BIGINT AUTO_INCREMENT PRIMARY KEY,
    post_id BIGINT NOT NULL,
    actor_id INT NOT NULL,
    action ENUM('SUBMITTED', 'RESUBMITTED', 'APPROVED', 'REVISION_REQUESTED', 'REJECTED') NOT NULL,
    comment TEXT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted_at DATETIME NULL,
    CONSTRAINT fk_approvals_post FOREIGN KEY (post_id) REFERENCES posts(post_id) ON DELETE RESTRICT,
    CONSTRAINT fk_approvals_actor FOREIGN KEY (actor_id) REFERENCES users(user_id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ------------------------------------------------------------------------------
-- 6. BẢNG schedules (Thực thể Lịch đăng bài trên Content Calendar)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS schedules (
    schedule_id BIGINT AUTO_INCREMENT PRIMARY KEY,
    post_id BIGINT NOT NULL UNIQUE,
    scheduled_time DATETIME NOT NULL,
    remind_before_minutes INT NOT NULL DEFAULT 30,
    is_reminded_30m BOOLEAN NOT NULL DEFAULT FALSE,
    is_reminded_10m BOOLEAN NOT NULL DEFAULT FALSE,
    is_overdue_alerted BOOLEAN NOT NULL DEFAULT FALSE,
    schedule_status ENUM('ACTIVE', 'COMPLETED', 'CANCELLED') NOT NULL DEFAULT 'ACTIVE',
    scheduled_by INT NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_schedules_post FOREIGN KEY (post_id) REFERENCES posts(post_id) ON DELETE RESTRICT,
    CONSTRAINT fk_schedules_user FOREIGN KEY (scheduled_by) REFERENCES users(user_id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ------------------------------------------------------------------------------
-- 7. BẢNG notifications (Thực thể Thông báo Thời gian thực)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS notifications (
    notification_id BIGINT AUTO_INCREMENT PRIMARY KEY,
    recipient_id INT NOT NULL,
    post_id BIGINT NULL,
    notification_type ENUM('APPROVAL_REQUEST', 'POST_APPROVED', 'POST_REJECTED', 'SCHEDULE_REMINDER', 'OVERDUE_ALERT') NOT NULL,
    title VARCHAR(255) NOT NULL,
    message VARCHAR(1000) NOT NULL,
    is_read BOOLEAN NOT NULL DEFAULT FALSE,
    read_at DATETIME NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_notifications_recipient FOREIGN KEY (recipient_id) REFERENCES users(user_id) ON DELETE RESTRICT,
    CONSTRAINT fk_notifications_post FOREIGN KEY (post_id) REFERENCES posts(post_id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ------------------------------------------------------------------------------
-- 8. BẢNG post_statistics (Thực thể Chỉ số Đo lường Bài đăng)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS post_statistics (
    stat_id BIGINT AUTO_INCREMENT PRIMARY KEY,
    post_id BIGINT NOT NULL,
    reach_count INT UNSIGNED NOT NULL DEFAULT 0,
    view_count INT UNSIGNED NOT NULL DEFAULT 0,
    like_count INT UNSIGNED NOT NULL DEFAULT 0,
    comment_count INT UNSIGNED NOT NULL DEFAULT 0,
    share_count INT UNSIGNED NOT NULL DEFAULT 0,
    source_type ENUM('MANUAL', 'API') NOT NULL DEFAULT 'MANUAL',
    updated_by INT NULL,
    recorded_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_stats_post FOREIGN KEY (post_id) REFERENCES posts(post_id) ON DELETE RESTRICT,
    CONSTRAINT fk_stats_user FOREIGN KEY (updated_by) REFERENCES users(user_id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ------------------------------------------------------------------------------
-- 9. CHỈ MỤC TỐI ƯU TRUY VẤN (INDEXING STRATEGY THEO MỤC 4.4 SDD)
-- ------------------------------------------------------------------------------
CREATE INDEX idx_users_email_status ON users(email, status);
CREATE INDEX idx_posts_filter ON posts(status, platform_id, author_id, deleted_at);
CREATE INDEX idx_posts_created_at ON posts(created_at DESC);
CREATE INDEX idx_schedules_time_status ON schedules(schedule_status, scheduled_time);
CREATE INDEX idx_notif_recipient_unread ON notifications(recipient_id, is_read, created_at DESC);
CREATE INDEX idx_stats_post_recorded ON post_statistics(post_id, recorded_at DESC);

-- ------------------------------------------------------------------------------
-- 10. DỮ LIỆU HẠT GIỐNG BAN ĐẦU (SEED DATA THEO MỤC 4.5 SDD & TASK T06A65C)
-- ------------------------------------------------------------------------------
-- 10.1. Khởi tạo Vai trò cố định (Role)
INSERT INTO roles (role_id, role_code, role_name, permissions) VALUES 
(1, 'MANAGER', 'Marketing Manager', '{"all": true, "approve_post": true, "manage_user": true}'),
(2, 'STAFF', 'Marketing Staff', '{"create_post": true, "edit_draft": true, "submit_approval": true}')
ON DUPLICATE KEY UPDATE role_name = VALUES(role_name);

-- 10.2. Khởi tạo 3 Kênh truyền thông ban đầu (Platform: Facebook, Instagram, Threads)
INSERT INTO platforms (platform_id, platform_code, platform_name, channel_url, color_hex) VALUES 
(1, 'FACEBOOK', 'Facebook Fanpage', 'https://facebook.com/korean_cosmetics_sample', '#1877F2'),
(2, 'INSTAGRAM', 'Instagram Business', 'https://instagram.com/korean_cosmetics_sample', '#E1306C'),
(3, 'THREADS', 'Threads Official', 'https://www.threads.net/@korean_cosmetics_sample', '#000000')
ON DUPLICATE KEY UPDATE platform_name = VALUES(platform_name);

-- 10.3. Khởi tạo 1 Manager và 4 Staff mẫu thử nghiệm (Mật khẩu: Manager@123 / Staff@123)
-- Chuỗi băm bcrypt: $2b$12$6Kk4B7a1jN9kQz8sR7qDse0hV3yF1fS9mX0qZ2lA3pB4c5d6e7f8g
INSERT INTO users (user_id, username, email, password_hash, full_name, role_id, status) VALUES 
(1, 'manager', 'manager@rikkeilab.vn', '$2b$12$6Kk4B7a1jN9kQz8sR7qDse0hV3yF1fS9mX0qZ2lA3pB4c5d6e7f8g', 'Doãn Thị Minh Anh (Manager)', 1, 'ACTIVE'),
(2, 'staff1', 'staff1@rikkeilab.vn', '$2b$12$6Kk4B7a1jN9kQz8sR7qDse0hV3yF1fS9mX0qZ2lA3pB4c5d6e7f8g', 'Trịnh Trần Công Huy (Staff)', 2, 'ACTIVE'),
(3, 'staff2', 'staff2@rikkeilab.vn', '$2b$12$6Kk4B7a1jN9kQz8sR7qDse0hV3yF1fS9mX0qZ2lA3pB4c5d6e7f8g', 'Nguyễn Văn Đạt (Staff)', 2, 'ACTIVE'),
(4, 'staff3', 'staff3@rikkeilab.vn', '$2b$12$6Kk4B7a1jN9kQz8sR7qDse0hV3yF1fS9mX0qZ2lA3pB4c5d6e7f8g', 'Phan Hoàng Sơn (Staff)', 2, 'ACTIVE'),
(5, 'staff4', 'staff4@rikkeilab.vn', '$2b$12$6Kk4B7a1jN9kQz8sR7qDse0hV3yF1fS9mX0qZ2lA3pB4c5d6e7f8g', 'Lê Thị Thu Thảo (Staff)', 2, 'ACTIVE')
ON DUPLICATE KEY UPDATE full_name = VALUES(full_name);

-- 10.4. Khởi tạo các Bài viết mẫu (Posts & Approvals)
INSERT INTO posts (post_id, title, caption, hashtags, platform_id, author_id, media_type, status, total_media_size_bytes) VALUES
(1, 'Bộ sưu tập Son Dưỡng Thu Đông 2026 - Hương Đào Tự Nhiên', 'Khám phá dòng son dưỡng thuần chay chiết xuất từ hoa quả tươi hữu cơ, cấp ẩm sâu 24h.', '#SonDuong #BlossomBeauty #VeganCosmetics #LipCare', 1, 2, 'IMAGE', 'DRAFT', 358400),
(2, 'Top 5 Serum Dưỡng Trắng & Mờ Thâm Được Yêu Thích Nhất', 'Review chân thực 5 dòng serum quốc dân phục hồi hàng rào bảo vệ da và làm đều màu da.', '#Skincare #Serum #BeautyTips #Whitening', 2, 3, 'IMAGE', 'PENDING_APPROVAL', 524288),
(3, 'Tips Chăm Sóc Da Dầu Mụn Cho Gen Z Trong Mùa Hè', 'Bỏ túi ngay 3 thói quen đơn giản giúp kiềm dầu cả ngày và ngăn ngừa mụn ẩn hiệu quả.', '#Threads #TipsChamsocda #AcneCare #BlossomGenZ', 3, 4, 'IMAGE', 'APPROVED', 614400),
(4, 'Đại Tiệc Sale Cuối Tuần - Giảm 50% Toàn Bộ Cửa Hàng', 'Duy nhất cuối tuần này tại hệ thống showroom Blossom Beauty trên toàn quốc. Đừng bỏ lỡ!', '#SaleCuoiTuan #KhuyenMai #BlossomBeauty #BigSale', 1, 2, 'IMAGE', 'PUBLISHED', 819200),
(5, 'Threads Hot: Liệu Có Cần Dùng Kem Chống Nắng Trong Nhà?', 'Tia UVA vẫn xuyên qua kính cửa sổ và ánh sáng xanh từ màn hình máy tính có thực sự gây hại?', '#Threads #Sunscreen #SkincareScience #FactCheck', 3, 5, 'IMAGE', 'PUBLISHED', 430080)
ON DUPLICATE KEY UPDATE title = VALUES(title);

-- 10.5. Khởi tạo Thống kê tương tác mẫu (Post Statistics)
INSERT INTO post_statistics (stat_id, post_id, reach_count, view_count, like_count, comment_count, share_count, source_type, updated_by) VALUES
(1, 4, 15800, 11200, 850, 120, 54, 'API', 2),
(2, 5, 6200, 4900, 410, 45, 22, 'MANUAL', 5)
ON DUPLICATE KEY UPDATE view_count = VALUES(view_count);
