import sys
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_remediation():
    print("=== BAT DAU KIEM THU REMEDIATION ===")

    # 1. Dang nhap Manager & Staff
    res_mgr = client.post("/api/auth/login", json={"username_or_email": "admin", "password": "Blossom@123"})
    assert res_mgr.status_code == 200, f"Manager login failed: {res_mgr.text}"
    mgr_token = res_mgr.json()["access_token"]
    mgr_headers = {"Authorization": f"Bearer {mgr_token}"}
    print("[PASS] Manager login")

    res_staff = client.post("/api/auth/login", json={"username_or_email": "minhanh", "password": "Staff@123"})
    assert res_staff.status_code == 200, f"Staff login failed: {res_staff.text}"
    staff_token = res_staff.json()["access_token"]
    staff_headers = {"Authorization": f"Bearer {staff_token}"}
    staff_user_id = res_staff.json()["user"]["user_id"]
    print(f"[PASS] Staff login (user_id={staff_user_id})")

    # 2. Kiem thu Doi mat khau (POST /api/auth/change-password)
    # 2a. Sai mat khau hien tai -> 400
    res_bad_curr = client.post("/api/auth/change-password", headers=staff_headers, json={
        "current_password": "WrongPassword123",
        "new_password": "NewStaffPassword@123"
    })
    assert res_bad_curr.status_code == 400, f"Expected 400 on wrong current password, got {res_bad_curr.status_code}"
    print("[PASS] Change password rejects wrong current password")

    # 2b. Mat khau moi qua ngan (< 8 ky tu) -> 400
    res_short = client.post("/api/auth/change-password", headers=staff_headers, json={
        "current_password": "Staff@123",
        "new_password": "123"
    })
    assert res_short.status_code == 400, f"Expected 400 on short password, got {res_short.status_code}"
    print("[PASS] Change password rejects short new password")

    # 2c. Doi thanh cong -> doi ve lai Staff@123 de bao toan tai khoan
    res_chg = client.post("/api/auth/change-password", headers=staff_headers, json={
        "current_password": "Staff@123",
        "new_password": "TemporaryPassword@123"
    })
    assert res_chg.status_code == 200, f"Expected 200 on change password, got {res_chg.text}"
    
    # Kiem tra dang nhap voi mat khau moi
    res_login_new = client.post("/api/auth/login", json={"username_or_email": "minhanh", "password": "TemporaryPassword@123"})
    assert res_login_new.status_code == 200, f"Login with new password failed: {res_login_new.text}"
    new_token = res_login_new.json()["access_token"]
    new_headers = {"Authorization": f"Bearer {new_token}"}

    # Restore ve Staff@123
    res_restore = client.post("/api/auth/change-password", headers=new_headers, json={
        "current_password": "TemporaryPassword@123",
        "new_password": "Staff@123"
    })
    assert res_restore.status_code == 200, f"Restore password failed: {res_restore.text}"
    print("[PASS] Change password and restore verified")

    # 3. Kiem thu Profile Update (PUT /api/users/me)
    res_prof = client.put("/api/users/me", headers=staff_headers, json={
        "full_name": "Doan Thi Minh Anh (Updated)",
        "avatar_url": "https://example.com/avatar.jpg"
    })
    assert res_prof.status_code == 200, f"Profile update failed: {res_prof.text}"
    assert res_prof.json()["full_name"] == "Doan Thi Minh Anh (Updated)"
    print("[PASS] Profile update (PUT /api/users/me)")

    # 4. Kiem thu Data Scope trong Posts (GET /api/posts & GET /api/posts/{id})
    # Lay danh sach bai viet voi Manager (thay tat ca)
    res_mgr_posts = client.get("/api/posts?page=1&page_size=50", headers=mgr_headers)
    assert res_mgr_posts.status_code == 200
    all_posts = res_mgr_posts.json()
    print(f"[PASS] Manager sees all posts ({len(all_posts)} posts)")

    # Lay danh sach bai viet voi Staff (chi thay bai cua minhanh)
    res_staff_posts = client.get("/api/posts?page=1&page_size=50", headers=staff_headers)
    assert res_staff_posts.status_code == 200
    staff_posts = res_staff_posts.json()
    for p in staff_posts:
        assert p["author_id"] == staff_user_id, f"Data leak! Post {p['post_id']} author {p['author_id']} != staff {staff_user_id}"
    print(f"[PASS] Staff data scope strictly isolated ({len(staff_posts)} posts owned by staff)")

    # Tim 1 post cua author khac de kiem thu GET /api/posts/{id} bi chan 403
    other_post = next((p for p in all_posts if p["author_id"] != staff_user_id), None)
    if other_post:
        res_forbidden = client.get(f"/api/posts/{other_post['post_id']}", headers=staff_headers)
        assert res_forbidden.status_code == 403, f"Expected 403 Forbidden for other post, got {res_forbidden.status_code}"
        print(f"[PASS] Direct GET /api/posts/{other_post['post_id']} correctly blocked with 403 Forbidden for non-owner Staff")

    # 5. Kiem thu Notifications (PATCH /api/notifications/read-all & DELETE /api/notifications/{id})
    res_read_all = client.patch("/api/notifications/read-all", headers=mgr_headers)
    assert res_read_all.status_code == 200, f"Read all failed: {res_read_all.text}"
    print(f"[PASS] Mark all notifications as read: {res_read_all.json()}")

    # Lay danh sach notifications
    res_notifs = client.get("/api/notifications", headers=mgr_headers)
    assert res_notifs.status_code == 200
    notifs = res_notifs.json()
    if notifs:
        target_id = notifs[0]["notification_id"]
        res_del = client.delete(f"/api/notifications/{target_id}", headers=mgr_headers)
        assert res_del.status_code == 200, f"Delete notification failed: {res_del.text}"
        print(f"[PASS] Delete notification #{target_id} successfully")

    print("=== TAT CA CAC TINH NANG KIEM THU DEU DAT CHUAN 100% ===")

if __name__ == "__main__":
    test_remediation()
