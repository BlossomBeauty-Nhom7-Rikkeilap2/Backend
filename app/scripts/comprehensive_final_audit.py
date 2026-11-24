import sys
import io
from fastapi.testclient import TestClient
from datetime import datetime, timedelta
from app.main import app

client = TestClient(app)

def run_comprehensive_audit():
    print("================================================================")
    print("   BLOSSOM BEAUTY STORE - COMPREHENSIVE FINAL AUDIT (MOD-01..07)")
    print("================================================================")

    # -------------------------------------------------------------
    # MOD-01: Authentication & Session
    # -------------------------------------------------------------
    print("\n--- [MOD-01: Authentication & Session] ---")
    
    # 1.1 Dang nhap Manager hop le
    r_mgr = client.post("/api/auth/login", json={"username_or_email": "admin", "password": "Blossom@123"})
    assert r_mgr.status_code == 200, f"Manager login failed: {r_mgr.text}"
    mgr_data = r_mgr.json()
    mgr_token = mgr_data["access_token"]
    mgr_headers = {"Authorization": f"Bearer {mgr_token}"}
    print(f"  [PASS] 1.1 Manager login (User: {mgr_data['user']['username']}, Role: {mgr_data['user']['role_code']})")

    # 1.2 Dang nhap Staff hop le
    r_staff = client.post("/api/auth/login", json={"username_or_email": "minhanh", "password": "Staff@123"})
    assert r_staff.status_code == 200, f"Staff login failed: {r_staff.text}"
    staff_data = r_staff.json()
    staff_token = staff_data["access_token"]
    staff_headers = {"Authorization": f"Bearer {staff_token}"}
    staff_uid = staff_data["user"]["user_id"]
    print(f"  [PASS] 1.2 Staff login (User: {staff_data['user']['username']}, Role: {staff_data['user']['role_code']}, ID: {staff_uid})")

    # 1.3 Dang nhap sai mat khau
    r_bad_pw = client.post("/api/auth/login", json={"username_or_email": "admin", "password": "WrongPassword"})
    assert r_bad_pw.status_code == 401, f"Expected 401 on wrong password, got {r_bad_pw.status_code}"
    print("  [PASS] 1.3 Wrong password rejected with 401 Unauthorized")

    # 1.4 Get /auth/me
    r_me = client.get("/api/auth/me", headers=mgr_headers)
    assert r_me.status_code == 200 and r_me.json()["username"] == "admin"
    print(f"  [PASS] 1.4 /auth/me returns current user ({r_me.json()['email']})")

    # 1.5 Change password
    r_chg_bad = client.post("/api/auth/change-password", headers=staff_headers, json={
        "current_password": "WrongPassword", "new_password": "NewStaffPass@123"
    })
    assert r_chg_bad.status_code == 400
    print("  [PASS] 1.5 /auth/change-password rejects wrong current password")

    # 1.6 Logout
    r_logout = client.post("/api/auth/logout", headers=mgr_headers)
    assert r_logout.status_code == 200
    print("  [PASS] 1.6 /auth/logout clears session")

    # -------------------------------------------------------------
    # MOD-02: User & RBAC Management
    # -------------------------------------------------------------
    print("\n--- [MOD-02: User & RBAC Management] ---")

    # 2.1 Staff goi /users bi 403 Forbidden
    r_forbidden_users = client.get("/api/users", headers=staff_headers)
    assert r_forbidden_users.status_code == 403, f"Expected 403 for Staff on /users, got {r_forbidden_users.status_code}"
    print("  [PASS] 2.1 RoleGuard correctly blocks Staff from GET /users with 403")

    # 2.2 Manager goi /users thanh cong
    r_users = client.get("/api/users", headers=mgr_headers)
    assert r_users.status_code == 200
    user_list = r_users.json()
    assert len(user_list) >= 2
    print(f"  [PASS] 2.2 Manager accesses GET /users ({len(user_list)} active accounts)")

    # 2.3 Cap nhat ho so ca nhan PUT /users/me
    r_update_me = client.put("/api/users/me", headers=staff_headers, json={
        "full_name": "Doan Thi Minh Anh (Final Audit)"
    })
    assert r_update_me.status_code == 200
    assert r_update_me.json()["full_name"] == "Doan Thi Minh Anh (Final Audit)"
    print("  [PASS] 2.3 PUT /users/me updates profile name")

    # -------------------------------------------------------------
    # MOD-03: Content & Media Management
    # -------------------------------------------------------------
    print("\n--- [MOD-03: Content & Media Management] ---")

    # 3.1 Upload Media (Fake image)
    fake_img = io.BytesIO(b"GIF89a\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff\x00\x00\x00!\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;")
    r_upload = client.post("/api/posts/upload-media", headers=staff_headers, files={"file": ("audit_sample.png", fake_img, "image/png")})
    assert r_upload.status_code == 200, f"Upload failed: {r_upload.text}"
    uploaded_url = r_upload.json()["file_url"]
    print(f"  [PASS] 3.1 Media upload successful (URL: {uploaded_url})")

    # 3.2 Tao bai viet moi (DRAFT) tren nen tang Threads (platform_id=3)
    post_payload = {
        "title": "Bo Duong Da Mua Dong 2026 - Threads Official",
        "caption": "Cham soc lan da min mang trong mua gio lanh voi kem duong hoa tra Blossom.",
        "hashtags": "#BlossomBeauty #Skincare2026 #Threads",
        "platform_id": 3,
        "media_type": "IMAGE",
        "media_files": [uploaded_url],
        "total_media_size_bytes": 1024,
        "planned_publish_time": (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%dT09:00:00")
    }
    r_create_post = client.post("/api/posts", headers=staff_headers, json=post_payload)
    assert r_create_post.status_code == 201, f"Create post failed: {r_create_post.text}"
    created_post = r_create_post.json()
    post_id = created_post["post_id"]
    assert created_post["status"] == "DRAFT"
    print(f"  [PASS] 3.2 Post created in DRAFT (ID: {post_id}, Platform: Threads/ID=3)")

    # 3.3 Autosave bai viet
    r_autosave = client.post("/api/posts/autosave", headers=staff_headers, json={
        "post_id": post_id,
        "title": "Bo Duong Da Mua Dong 2026 - Threads Official (Autosaved)",
        "caption": "Cap nhat noi dung tu dong luu dinh ky 30 giay."
    })
    assert r_autosave.status_code == 200 and r_autosave.json()["status"] == "saved"
    print("  [PASS] 3.3 Autosave endpoint verified")

    # 3.4 Kiem tra Data Scope Isolation
    r_staff_posts = client.get("/api/posts", headers=staff_headers)
    for p in r_staff_posts.json():
        assert p["author_id"] == staff_uid, f"Data isolation breach: post {p['post_id']} belongs to author {p['author_id']}"
    print(f"  [PASS] 3.4 Staff data isolation strictly enforced (Only owns {len(r_staff_posts.json())} posts)")

    # -------------------------------------------------------------
    # MOD-04: Approval Workflow
    # -------------------------------------------------------------
    print("\n--- [MOD-04: Approval Workflow] ---")

    # 4.1 Gui duyet (Staff submit -> PENDING_APPROVAL)
    r_submit = client.post(f"/api/posts/{post_id}/submit", headers=staff_headers)
    assert r_submit.status_code == 200 and r_submit.json()["action"] == "SUBMITTED"
    post_check1 = client.get(f"/api/posts/{post_id}", headers=mgr_headers).json()
    assert post_check1["status"] == "PENDING_APPROVAL"
    print(f"  [PASS] 4.1 Submit approval (Post #{post_id} -> PENDING_APPROVAL)")

    # 4.2 Yeu cau sua (Manager request revision)
    r_revision = client.post(f"/api/posts/{post_id}/reject", headers=mgr_headers, json={
        "action": "REVISION_REQUESTED",
        "comment": "Vui long bo sung them cam ket thuan chay vao cuoi caption."
    })
    assert r_revision.status_code == 200 and r_revision.json()["action"] == "REVISION_REQUESTED"
    post_check2 = client.get(f"/api/posts/{post_id}", headers=mgr_headers).json()
    assert post_check2["status"] == "REVISION_REQUESTED"
    print(f"  [PASS] 4.2 Request revision (Post #{post_id} -> REVISION_REQUESTED)")

    # 4.3 Staff cap nhat va gui lai
    r_update_rev = client.put(f"/api/posts/{post_id}", headers=staff_headers, json={
        "caption": "Cham soc lan da min mang trong mua gio lanh voi kem duong hoa tra Blossom. San pham 100% thuan chay."
    })
    assert r_update_rev.status_code == 200
    r_resubmit = client.post(f"/api/posts/{post_id}/submit", headers=staff_headers)
    assert r_resubmit.status_code == 200 and r_resubmit.json()["action"] == "RESUBMITTED"
    post_check3 = client.get(f"/api/posts/{post_id}", headers=mgr_headers).json()
    assert post_check3["status"] == "PENDING_APPROVAL"
    print(f"  [PASS] 4.3 Update & re-submit (Post #{post_id} -> PENDING_APPROVAL)")

    # 4.4 Phe duyet (Manager approve -> APPROVED)
    r_approve = client.post(f"/api/posts/{post_id}/approve", headers=mgr_headers)
    assert r_approve.status_code == 200 and r_approve.json()["action"] == "APPROVED"
    post_check4 = client.get(f"/api/posts/{post_id}", headers=mgr_headers).json()
    assert post_check4["status"] == "APPROVED"
    print(f"  [PASS] 4.4 Approve post (Post #{post_id} -> APPROVED)")

    # -------------------------------------------------------------
    # MOD-05: Scheduling & Notification
    # -------------------------------------------------------------
    print("\n--- [MOD-05: Scheduling & Notification] ---")

    # 5.1 Kiem tra Calendar da co su kien dong bo tu Post vua APPROVED
    r_cal = client.get("/api/schedules/calendar", headers=mgr_headers)
    assert r_cal.status_code == 200
    cal_events = r_cal.json()
    post_event = next((ev for ev in cal_events if ev["post_id"] == post_id), None)
    assert post_event is not None, f"Post #{post_id} not found in calendar events!"
    print(f"  [PASS] 5.1 Schedule auto-created on calendar (Schedule ID: {post_event['schedule_id']}, Time: {post_event['scheduled_time']})")

    # 5.2 Cap nhat gio tren lich PUT /schedules/{post_id}
    new_time = (datetime.now() + timedelta(days=3)).strftime("%Y-%m-%dT10:30:00")
    r_update_sched = client.put(f"/api/schedules/{post_id}", headers=mgr_headers, json={"scheduled_time": new_time, "remind_before_minutes": 30})
    assert r_update_sched.status_code == 200
    print(f"  [PASS] 5.2 Schedule updated to new time: {new_time}")

    # 5.3 Kiem tra thong bao va doc het
    r_read_all = client.patch("/api/notifications/read-all", headers=staff_headers)
    assert r_read_all.status_code == 200
    print("  [PASS] 5.3 PATCH /notifications/read-all succeeded")

    # -------------------------------------------------------------
    # MOD-06: Progress Tracking
    # -------------------------------------------------------------
    print("\n--- [MOD-06: Progress Tracking] ---")

    # 6.1 Xac nhan dang bai thu cong voi URL sai nen tang -> bi chan
    r_bad_url = client.patch(f"/api/posts/{post_id}/publish", headers=mgr_headers, json={
        "published_url": "https://unknown-domain.com/p/123"
    })
    assert r_bad_url.status_code == 400
    print("  [PASS] 6.1 Invalid platform domain correctly rejected (400 Bad Request)")

    # 6.2 Xac nhan dang bai voi URL Threads hop le
    r_confirm_pub = client.patch(f"/api/posts/{post_id}/publish", headers=mgr_headers, json={
        "published_url": f"https://www.threads.net/@blossombeautystore/post/{post_id}"
    })
    assert r_confirm_pub.status_code == 200 and r_confirm_pub.json()["status"] == "PUBLISHED"
    print(f"  [PASS] 6.2 Post confirmed published (Status: PUBLISHED, URL: https://www.threads.net/@blossombeautystore/post/{post_id})")

    # -------------------------------------------------------------
    # MOD-07: Analytics & Reporting
    # -------------------------------------------------------------
    print("\n--- [MOD-07: Analytics & Reporting] ---")

    # 7.1 Ghi nhan so lieu tuong tac (Reach, Views, Likes, Comments, Shares)
    r_record_stats = client.post(f"/api/posts/{post_id}/statistics", headers=mgr_headers, json={
        "reach_count": 9800,
        "view_count": 12500,
        "like_count": 650,
        "comment_count": 78,
        "share_count": 34,
        "source_type": "MANUAL",
        "milestone": "CUSTOM"
    })
    assert r_record_stats.status_code == 201, f"Record stats failed: {r_record_stats.text}"
    print(f"  [PASS] 7.1 Interaction statistics recorded (Reach: 9800, Likes: 650, Comments: 78)")

    # 7.2 Lay lich su chi so bai viet
    r_stats_hist = client.get(f"/api/posts/{post_id}/statistics/history", headers=mgr_headers)
    assert r_stats_hist.status_code == 200 and len(r_stats_hist.json()["history"]) > 0
    print(f"  [PASS] 7.2 Post statistics history retrieved ({len(r_stats_hist.json()['history'])} snapshots)")

    # 7.3 Lay Dashboard Analytics
    r_dash = client.get("/api/analytics/dashboard", headers=mgr_headers)
    assert r_dash.status_code == 200
    dash_data = r_dash.json()
    assert "total_published_posts" in dash_data and "total_reach" in dash_data
    print(f"  [PASS] 7.3 Dashboard Analytics loaded (Published posts: {dash_data['total_published_posts']}, Total reach: {dash_data['total_reach']})")

    # 7.4 Xuat bao cao
    r_export = client.get("/api/analytics/export", headers=mgr_headers)
    assert r_export.status_code == 200 and isinstance(r_export.json(), list)
    print(f"  [PASS] 7.4 Analytics report export data generated ({len(r_export.json())} published post rows)")

    print("\n================================================================")
    print("   100% MODULES MOD-01..07 HOAN TOAN KET NOI DONG BO VA HOP LE")
    print("================================================================")

if __name__ == "__main__":
    run_comprehensive_audit()
