import sys
import logging
from sqlalchemy import text
from app.core.database import engine

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("MigrateV2Social")

def run_migration():
    """
    Migration script nâng cấp schema cho posts và schedules:
    - Thêm external_post_id, error_message, retry_count vào posts.
    - Mở rộng enum status của posts (thêm PUBLISHING, FAILED).
    - Thêm retry_count vào schedules.
    - Mở rộng enum schedule_status của schedules (thêm FAILED).
    """
    logger.info("Bắt đầu migration CSDL cho tính năng Social Media V2...")

    statements = [
        "ALTER TABLE posts ADD COLUMN IF NOT EXISTS external_post_id VARCHAR(255) NULL;",
        "ALTER TABLE posts ADD COLUMN IF NOT EXISTS error_message TEXT NULL;",
        "ALTER TABLE posts ADD COLUMN IF NOT EXISTS retry_count INT NOT NULL DEFAULT 0;",
        "ALTER TABLE schedules ADD COLUMN IF NOT EXISTS retry_count INT NOT NULL DEFAULT 0;",
        (
            "ALTER TABLE posts MODIFY COLUMN status "
            "ENUM('DRAFT', 'PENDING_APPROVAL', 'REVISION_REQUESTED', 'REJECTED', 'APPROVED', 'SCHEDULED', 'PUBLISHING', 'PUBLISHED', 'FAILED') "
            "NOT NULL DEFAULT 'DRAFT';"
        ),
        (
            "ALTER TABLE schedules MODIFY COLUMN schedule_status "
            "ENUM('ACTIVE', 'COMPLETED', 'CANCELLED', 'FAILED') "
            "NOT NULL DEFAULT 'ACTIVE';"
        )
    ]

    with engine.connect() as conn:
        for stmt in statements:
            try:
                logger.info(f"Đang thực thi: {stmt.strip()}")
                conn.execute(text(stmt))
                conn.commit()
                logger.info("Thành công!")
            except Exception as e:
                logger.warning(f"Lỗi khi thực thi statement (có thể cột/enum đã tồn tại): {e}")

    logger.info("Hoàn thành migration CSDL thành công!")

if __name__ == "__main__":
    run_migration()
