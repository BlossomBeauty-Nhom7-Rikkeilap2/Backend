import sys
import os

# Cấu hình UTF-8 cho Windows console tránh lỗi charmap UnicodeEncodeError
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Thêm đường dẫn gốc vào sys.path để import được app
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from app.core.database import engine, SessionLocal, Base
from app.scripts.init_db import seed_database

def reset_database():
    """Script Reset toàn bộ Cơ sở dữ liệu và nạp lại Seed Data sạch (Task T06A65C - Bonus +1 điểm).
    Các bước thực hiện:
    1. Xóa bỏ toàn bộ các bảng hiện có (Drop all tables).
    2. Khởi tạo lại cấu trúc 8 bảng chuẩn ERD (Create all tables).
    3. Nạp lại dữ liệu hạt giống tiêu chuẩn (Seed Roles, Platforms, 1 Manager + 4 Staff, Sample Posts & Stats).
    """
    print("=" * 65)
    print("SCRIPT RESET CƠ SỞ DỮ LIỆU TOÀN DIỆN (Task T06A65C)")
    print("=" * 65)

    # 1. Drop toàn bộ các bảng
    print("[1/3] Đang tiến hành xóa sạch toàn bộ các bảng dữ liệu cũ (Drop all)...")
    Base.metadata.drop_all(bind=engine)
    print("  -> Đã xóa sạch dữ liệu và cấu trúc các bảng cũ thành công.")

    # 2. Khởi tạo lại 8 bảng
    print("[2/3] Đang tái tạo cấu trúc 8 bảng theo chuẩn ERD (Create all)...")
    Base.metadata.create_all(bind=engine)
    print("  -> Đã tạo mới thành công 8 bảng: roles, users, platforms, posts, approvals, schedules, notifications, post_statistics.")

    # 3. Nạp lại dữ liệu hạt giống sạch
    print("[3/3] Đang nạp lại dữ liệu hạt giống chuẩn sạch...")
    db = SessionLocal()
    try:
        seed_database(db)
        print("=" * 65)
        print("RESET CƠ SỞ DỮ LIỆU HOÀN TẤT 100%! CƠ SỞ DỮ LIỆU ĐÃ SẠCH VÀ SẴN SÀNG.")
        print("=" * 65)
    except Exception as e:
        db.rollback()
        print(f"LỖI KHI NẠP LẠI DỮ LIỆU: {str(e)}")
        raise e
    finally:
        db.close()

if __name__ == "__main__":
    reset_database()
