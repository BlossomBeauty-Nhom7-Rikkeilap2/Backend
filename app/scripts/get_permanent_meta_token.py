"""
Script hỗ trợ lấy Permanent Page Access Token (Token vĩnh viễn không bao giờ hết hạn) từ Meta.
Nguyên lý Meta Graph API:
  Short-lived User Token -> Đổi sang Long-lived User Token (60 ngày)
  Long-lived User Token -> Gọi /me/accounts -> Nhận Page Access Token VĨNH VIỄN (Expires: Never).
"""

import sys
import requests
from app.config import settings

def get_permanent_page_token(short_lived_user_token: str, target_page_id: str = None):
    app_id = settings.FACEBOOK_APP_ID
    app_secret = settings.FACEBOOK_APP_SECRET
    version = settings.FACEBOOK_GRAPH_VERSION or "v19.0"

    print("==================================================================")
    print("  TOOL SINH TOKEN VĨNH VIỄN (PERMANENT PAGE ACCESS TOKEN) CHO META")
    print("==================================================================")

    # Bước 1: Nâng cấp Short-lived User Token lên Long-lived User Token (60 ngày)
    print("\n[Bước 1/3] Đang nâng cấp lên Long-lived User Token (60 ngày)...")
    url_step1 = f"https://graph.facebook.com/{version}/oauth/access_token"
    params_step1 = {
        "grant_type": "fb_exchange_token",
        "client_id": app_id,
        "client_secret": app_secret,
        "fb_exchange_token": short_lived_user_token
    }
    res1 = requests.get(url_step1, params=params_step1, timeout=15)
    data1 = res1.json()

    if "error" in data1:
        print("[LỖI BƯỚC 1]:", data1["error"].get("message"))
        return None

    long_lived_user_token = data1.get("access_token")
    print("[THÀNH CÔNG] Đã nhận Long-lived User Token.")

    # Bước 2: Dùng Long-lived User Token để truy vấn danh sách Trang (/me/accounts)
    print("\n[Bước 2/3] Đang truy vấn danh sách Fanpage để trích xuất Permanent Page Token...")
    url_step2 = f"https://graph.facebook.com/{version}/me/accounts"
    params_step2 = {
        "access_token": long_lived_user_token
    }
    res2 = requests.get(url_step2, params=params_step2, timeout=15)
    data2 = res2.json()

    if "error" in data2:
        print("[LỖI BƯỚC 2]:", data2["error"].get("message"))
        return None

    pages = data2.get("data", [])
    if not pages:
        print("[CẢNH BÁO] Không tìm thấy Fanpage nào được quản lý bởi tài khoản này.")
        return None

    print(f"[THÀNH CÔNG] Tìm thấy {len(pages)} Fanpage:")
    selected_page_token = None
    target_pid = target_page_id or settings.FB_PAGE_ID

    for idx, page in enumerate(pages, 1):
        p_name = page.get("name")
        p_id = page.get("id")
        p_token = page.get("access_token")
        is_match = (str(p_id) == str(target_pid))
        marker = " <--- TRANG TRONG FILE .ENV" if is_match else ""
        print(f"  {idx}. {p_name} (ID: {p_id}){marker}")
        if is_match or selected_page_token is None:
            selected_page_token = p_token
            selected_page_name = p_name
            selected_page_id = p_id

    # Bước 3: Kiểm tra tính vĩnh viễn qua Debugger
    print("\n[Bước 3/3] Kiểm tra tính vĩnh viễn (Expiration check)...")
    url_debug = f"https://graph.facebook.com/{version}/debug_token"
    params_debug = {
        "input_token": selected_page_token,
        "access_token": f"{app_id}|{app_secret}"
    }
    res_debug = requests.get(url_debug, params=params_debug, timeout=15)
    debug_data = res_debug.json().get("data", {})
    expires_at = debug_data.get("expires_at")
    is_valid = debug_data.get("is_valid")

    print("------------------------------------------------------------------")
    print(f"Trang đã chọn: {selected_page_name} (ID: {selected_page_id})")
    print(f"Trạng thái Token hợp lệ: {is_valid}")
    if expires_at == 0 or expires_at is None:
        print("Thời hạn Token: VĨNH VIỄN (Expires: Never / Không bao giờ hết hạn)!")
    else:
        print(f"Thời hạn Token (timestamp): {expires_at}")
    print("------------------------------------------------------------------")
    print("\n>>> SAO CHÉP TOKEN VĨNH VIỄN DƯỚI ĐÂY DÁN VÀO FILE .ENV:")
    print(f"\nFB_PAGE_ACCESS_TOKEN={selected_page_token}\n")
    print("==================================================================")
    return selected_page_token

if __name__ == "__main__":
    if len(sys.argv) > 1:
        user_tok = sys.argv[1].strip()
        get_permanent_page_token(user_tok)
    else:
        print("Cách dùng:")
        print("  python -m app.scripts.get_permanent_meta_token <SHORT_LIVED_USER_TOKEN>")
        print("\nĐể lấy <SHORT_LIVED_USER_TOKEN>:")
        print("  1. Vào https://developers.facebook.com/tools/explorer/")
        print("  2. Chọn App của bạn, bấm 'Generate Access Token'")
        print("  3. Chạy lệnh: python -m app.scripts.get_permanent_meta_token <chuỗi_token_vừa_copy>")
