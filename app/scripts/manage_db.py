import os
import sys

# Cấu hình biến môi trường kết nối MySQL
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_USER = os.environ.get("DB_USER", "root")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "")
DB_PORT = int(os.environ.get("DB_PORT", 3306))

def get_script_path(filename):
    return os.path.join(os.path.dirname(__file__), filename)

def execute_sql_file(cursor, filepath):
    filename = os.path.basename(filepath)
    print(f"[*] Đang thực thi kịch bản: {filename}...")
    if not os.path.exists(filepath):
        print(f"[!] Không tìm thấy tệp: {filepath}")
        return False

    with open(filepath, "r", encoding="utf-8") as f:
        sql_content = f.read()

    # Tách từng câu lệnh SQL theo dấu chấm phẩy
    statements = sql_content.split(";")
    count = 0
    for stmt in statements:
        stmt_clean = stmt.strip()
        if stmt_clean:
            cursor.execute(stmt_clean)
            count += 1
    print(f"[+] Thành công: {filename} ({count} câu lệnh đã thực thi)")
    return True

def get_connection():
    # Thử kết nối bằng pymysql trước, nếu không có thì thử mysql.connector
    try:
        import pymysql
        return pymysql.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            port=DB_PORT,
            autocommit=True
        )
    except ImportError:
        pass

    try:
        import mysql.connector
        conn = mysql.connector.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            port=DB_PORT
        )
        conn.autocommit = True
        return conn
    except ImportError:
        pass

    print("[!] Lỗi: Cần cài đặt driver kết nối MySQL (pymysql hoặc mysql-connector-python)")
    print("    Gợi ý lệnh cài đặt: pip install pymysql")
    sys.exit(1)

def main():
    action = sys.argv[1].lower() if len(sys.argv) > 1 else "all"

    print("=" * 65)
    print(" CÔNG CỤ QUẢN LÝ CƠ SỞ DỮ LIỆU TỰ ĐỘNG (Task: T06A65C)")
    print(f" Kết nối máy chủ: {DB_USER}@{DB_HOST}:{DB_PORT}")
    print("=" * 65)

    conn = get_connection()
    cursor = conn.cursor()

    try:
        if action == "reset":
            print("\n>> BƯỚC 1: XÓA VÀ KHỞI TẠO LẠI CSDL (+1 ĐIỂM THƯỞNG)...")
            execute_sql_file(cursor, get_script_path("00_reset_db.sql"))
            print("\n>> BƯỚC 2: TẠO CẤU TRÚC 8 BẢNG (MIGRATION)...")
            execute_sql_file(cursor, get_script_path("01_migration.sql"))
            print("\n>> BƯỚC 3: NẠP DỮ LIỆU MẪU (SEED)...")
            execute_sql_file(cursor, get_script_path("02_seed.sql"))
            print("\n" + "=" * 65)
            print("[SUCCESS] ĐÃ RESET + TẠO 8 BẢNG + SEED DỮ LIỆU THÀNH CÔNG!")
            print("=" * 65)
        elif action == "migrate":
            print("\n>> TẠO CẤU TRÚC 8 BẢNG (MIGRATION)...")
            execute_sql_file(cursor, get_script_path("01_migration.sql"))
            print("\n[SUCCESS] Đã khởi tạo cấu trúc 8 bảng thành công!")
        elif action == "seed":
            print("\n>> NẠP DỮ LIỆU MẪU (SEED)...")
            execute_sql_file(cursor, get_script_path("02_seed.sql"))
            print("\n[SUCCESS] Đã nạp dữ liệu mẫu thành công!")
        else:
            print("\n>> [1/2] KHỞI TẠO CẤU TRÚC 8 BẢNG (MIGRATION)...")
            execute_sql_file(cursor, get_script_path("01_migration.sql"))
            print("\n>> [2/2] NẠP DỮ LIỆU MẪU (SEED)...")
            execute_sql_file(cursor, get_script_path("02_seed.sql"))
            print("\n" + "=" * 65)
            print("[SUCCESS] HOÀN TẤT KHỞI TẠO CƠ SỞ DỮ LIỆU VÀ SEED DỮ LIỆU MẪU!")
            print("=" * 65)
    except Exception as e:
        print(f"\n[ERROR] Có lỗi phát sinh khi thực thi: {e}")
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    main()
