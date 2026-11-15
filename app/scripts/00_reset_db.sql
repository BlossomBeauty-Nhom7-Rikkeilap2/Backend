-- ============================================================================
-- RESET DATABASE SCRIPT (+1 ĐIỂM THƯỞNG)
-- Công dụng: Xóa sạch toàn bộ dữ liệu/bảng cũ và khởi tạo lại CSDL từ đầu
-- Task: T06A65C | Người thực hiện: Nguyễn Phát Đạt (N25DTCN082)
-- Dự án: Hệ thống Quản lý Truyền thông Đa kênh (Multi-Channel CMS)
-- ============================================================================

SET FOREIGN_KEY_CHECKS = 0;

DROP DATABASE IF EXISTS multichannel_cms;

CREATE DATABASE multichannel_cms
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

SET FOREIGN_KEY_CHECKS = 1;
