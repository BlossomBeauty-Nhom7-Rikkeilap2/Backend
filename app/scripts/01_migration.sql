-- ============================================================================
-- MIGRATION SCRIPT: HỆ THỐNG QUẢN LÝ TRUYỀN THÔNG ĐA KÊNH (multichannel_cms)
-- Task: T06A65C | Người thực hiện: Nguyễn Phát Đạt (N25DTCN082)
-- Sản phẩm: Tạo đủ 8 bảng CSDL, toàn vẹn khóa ngoại (FK) và đánh chỉ mục (Index)
-- Chuẩn kỹ thuật: MySQL 8.0+ | Engine: InnoDB | Charset: utf8mb4
-- ============================================================================

CREATE DATABASE IF NOT EXISTS multichannel_cms
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE multichannel_cms;

-- ------------------------------------------------------------------------------
-- 1. BẢNG roles (Thực thể Vai trò & Quyền hạn RBAC)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS roles (
    role_id INT AUTO_INCREMENT PRIMARY KEY,
    role_code VARCHAR(30) NOT NULL UNIQUE,
    role_name VARCHAR(100) NOT NULL,
    permissions JSON NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ------------------------------------------------------------------------------
-- 2. BẢNG users (Thực thể Người dùng Hệ thống: 1 Manager, 4 Staff)
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
-- 3. BẢNG platforms (Thực thể 3 Nền tảng: Facebook, Instagram, TikTok)
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
-- 4. BẢNG posts (Thực thể Bài viết Truyền thông Đa kênh)
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
-- 5. BẢNG approvals (Thực thể Lịch sử Phê duyệt Bài viết)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS approvals (
    approval_id BIGINT AUTO_INCREMENT PRIMARY KEY,
    post_id BIGINT NOT NULL,
    actor_id INT NOT NULL,
    action ENUM('SUBMITTED', 'RESUBMITTED', 'APPROVED', 'REVISION_REQUESTED', 'REJECTED') NOT NULL,
    comment TEXT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted_at DATETIME NULL,
    CONSTRAINT fk_approvals_post FOREIGN KEY (post_id) REFERENCES posts(post_id) ON DELETE CASCADE,
    CONSTRAINT fk_approvals_actor FOREIGN KEY (actor_id) REFERENCES users(user_id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ------------------------------------------------------------------------------
-- 6. BẢNG schedules (Thực thể Lên lịch Xuất bản & Hẹn giờ)
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
    CONSTRAINT fk_schedules_post FOREIGN KEY (post_id) REFERENCES posts(post_id) ON DELETE CASCADE,
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
-- 8. BẢNG post_statistics (Thực thể Chỉ số Tương tác Bài viết)
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
    CONSTRAINT fk_stats_post FOREIGN KEY (post_id) REFERENCES posts(post_id) ON DELETE CASCADE,
    CONSTRAINT fk_stats_user FOREIGN KEY (updated_by) REFERENCES users(user_id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ------------------------------------------------------------------------------
-- 9. TỐI ƯU HÓA CHỈ MỤC TRUY VẤN (INDEXING)
-- ------------------------------------------------------------------------------
CREATE INDEX idx_users_email_status ON users(email, status);
CREATE INDEX idx_posts_filter ON posts(status, platform_id, author_id, deleted_at);
CREATE INDEX idx_posts_created_at ON posts(created_at DESC);
CREATE INDEX idx_schedules_time_status ON schedules(schedule_status, scheduled_time);
CREATE INDEX idx_notif_recipient_unread ON notifications(recipient_id, is_read, created_at DESC);
CREATE INDEX idx_stats_post_recorded ON post_statistics(post_id, recorded_at DESC);
