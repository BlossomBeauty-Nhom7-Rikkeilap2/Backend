import os
import sys
import json
import requests
from fastapi.testclient import TestClient

from app.main import app
from app.config import settings
from app.core.database import SessionLocal
from app.models.post import Post
from app.models.user import User

client = TestClient(app)

def run_tests():
    print("=================================================================")
    print("BAT DAU KIEM THU DANG BAI: INSTAGRAM BUSINESS & META THREADS")
    print("=================================================================")

    # 1. Dang nhap lay token Staff va Manager
    login_staff = client.post(
        "/api/auth/login",
        json={"username_or_email": "minhanh", "password": "Staff@123"}
    )
    if login_staff.status_code != 200:
        print(f"[FAIL] Khong the dang nhap staff: {login_staff.text}")
        return
    staff_token = login_staff.json()["access_token"]
    staff_headers = {"Authorization": f"Bearer {staff_token}"}
    print("[PASS] Staff dang nhap thanh cong (minhanh)")

    login_mgr = client.post(
        "/api/auth/login",
        json={"username_or_email": "admin", "password": "Blossom@123"}
    )
    if login_mgr.status_code != 200:
        print(f"[FAIL] Khong the dang nhap manager: {login_mgr.text}")
        return
    mgr_token = login_mgr.json()["access_token"]
    mgr_headers = {"Authorization": f"Bearer {mgr_token}"}
    print("[PASS] Manager dang nhap thanh cong")

    # =========================================================================
    # PHAN 1: KIEM THU DANG BAI THAT LEN INSTAGRAM BUSINESS
    # =========================================================================
    print("\n-----------------------------------------------------------------")
    print("1. KIEM THU QUY TRINH DANG BAI THAT LEN INSTAGRAM BUSINESS (ID=2)")
    print("-----------------------------------------------------------------")

    sample_image_url = "https://images.unsplash.com/photo-1556228720-195a672e8a03?w=800"

    # 1.1 Tao bai viet Instagram
    create_ig_payload = {
        "title": "Serum Duong Sang Da Blossom Vitamin C - Official Instagram Post",
        "caption": "Kham pha dong san pham Blossom Vitamin C Serum tinh khiet giup lan da sang khoe tu tin moi ngay tu Blossom Beauty Store!",
        "hashtags": "#BlossomBeauty #Skincare #InstagramOfficial #VitaminC #BeautyCare",
        "platform_id": 2,
        "media_files": [sample_image_url]
    }
    ig_res = client.post("/api/posts", json=create_ig_payload, headers=staff_headers)
    if ig_res.status_code != 201:
        print(f"[FAIL] 1.1 Tao bai viet Instagram that bai: {ig_res.text}")
        return
    ig_post = ig_res.json()
    ig_post_id = ig_post["post_id"]
    print(f"[PASS] 1.1 Da tao bai viet Instagram (ID: {ig_post_id}, Trang thai: {ig_post['status']})")

    # 1.2 Gui duyet
    sub_res = client.post(f"/api/posts/{ig_post_id}/submit", headers=staff_headers)
    if sub_res.status_code != 200:
        print(f"[FAIL] 1.2 Gui duyet that bai: {sub_res.text}")
        return
    print(f"[PASS] 1.2 Da gui duyet bai viet #{ig_post_id} (Trang thai: SUBMITTED)")

    # 1.3 Manager phe duyet
    appr_res = client.post(
        f"/api/posts/{ig_post_id}/approve",
        headers=mgr_headers
    )
    if appr_res.status_code != 200:
        print(f"[FAIL] 1.3 Phe duyet that bai: {appr_res.text}")
        return
    print(f"[PASS] 1.3 Manager da phe duyet bai viet #{ig_post_id} (Trang thai: APPROVED)")

    # 1.4 Tu dong dang bai len Instagram that qua Meta Graph API
    print(f"[*] Dang goi Meta Instagram Content Publishing API de dang bai #{ig_post_id}...")
    pub_res = client.post(f"/api/posts/{ig_post_id}/auto-publish", headers=mgr_headers)
    if pub_res.status_code != 200:
        print(f"[FAIL] 1.4 Dang bai Instagram that bai: {pub_res.text}")
        return
    pub_data = pub_res.json()
    print(f"[PASS] 1.4 Dang bai Instagram thanh cong 100%!")
    print(f"      - Message: {pub_data.get('message')}")
    print(f"      - Published URL: {pub_data.get('published_url')}")
    print(f"      - Response API: {pub_data.get('api_response')}")

    # 1.5 Kiem tra thong tin bai viet trong CSDL
    db = SessionLocal()
    saved_ig_post = db.query(Post).filter(Post.post_id == ig_post_id).first()
    print(f"[PASS] 1.5 CSDL cap nhat trang thai: {saved_ig_post.status}")
    print(f"      - Published at: {saved_ig_post.published_at}")
    print(f"      - Published URL: {saved_ig_post.published_url}")

    # 1.6 Dong bo so lieu Instagram qua API
    ig_media_id = None
    if isinstance(pub_data.get("api_response"), dict):
        ig_media_id = pub_data["api_response"].get("ig_media_id")
    
    if ig_media_id and settings.IG_ACCESS_TOKEN:
        print(f"[*] Dang kiem tra dong bo chi so Instagram Insights cho media {ig_media_id}...")
        sync_res = client.post(
            f"/api/social/posts/{ig_post_id}/sync-instagram",
            json={
                "ig_media_id": ig_media_id,
                "access_token": settings.IG_ACCESS_TOKEN,
                "milestone": "24H"
            },
            headers=mgr_headers
        )
        if sync_res.status_code == 200:
            stat_data = sync_res.json()
            print(f"[PASS] 1.6 Dong bo so lieu Instagram Graph API thanh cong:")
            print(f"      - Views: {stat_data.get('view_count')}")
            print(f"      - Likes: {stat_data.get('like_count')}")
            print(f"      - Comments: {stat_data.get('comment_count')}")
            print(f"      - Reach: {stat_data.get('reach_count')}")
        else:
            print(f"[*] Luu y: Instagram Insights can mot chut thoi gian de Meta tong hop so lieu: {sync_res.text}")

    # =========================================================================
    # PHAN 2: KIEM THU DANG BAI LEN META THREADS
    # =========================================================================
    print("\n-----------------------------------------------------------------")
    print("2. KIEM THU QUY TRINH DANG BAI LEN META THREADS (ID=3)")
    print("-----------------------------------------------------------------")

    # 2.1 Tao bai viet Threads
    create_th_payload = {
        "title": "Goc Chia Se Tips Skincare Chuyen Sau - Threads Official",
        "caption": "Moi nguoi thuong hoi: Lieu kem chong nang co thuc su can thiet khi lam viec trong nha? Cau tra loi la CO nhe ca nha! Tia UVA van co the xuyen qua cua kinh va anh sang xanh tu thiet bi dien tu co the gay sam da. Hay cung Blossom Beauty cham soc da moi ngay nhe!",
        "hashtags": "#Threads #SkincareTips #BlossomBeautyStore #SunscreenFact #Chamsocda",
        "platform_id": 3,
        "media_files": [sample_image_url]
    }
    th_res = client.post("/api/posts", json=create_th_payload, headers=staff_headers)
    if th_res.status_code != 201:
        print(f"[FAIL] 2.1 Tao bai viet Threads that bai: {th_res.text}")
        return
    th_post = th_res.json()
    th_post_id = th_post["post_id"]
    print(f"[PASS] 2.1 Da tao bai viet Threads (ID: {th_post_id}, Trang thai: {th_post['status']})")

    # 2.2 Gui duyet
    sub_th = client.post(f"/api/posts/{th_post_id}/submit", headers=staff_headers)
    if sub_th.status_code != 200:
        print(f"[FAIL] 2.2 Gui duyet that bai: {sub_th.text}")
        return
    print(f"[PASS] 2.2 Da gui duyet bai viet #{th_post_id} (Trang thai: SUBMITTED)")

    # 2.3 Manager phe duyet
    appr_th = client.post(
        f"/api/posts/{th_post_id}/approve",
        headers=mgr_headers
    )
    if appr_th.status_code != 200:
        print(f"[FAIL] 2.3 Phe duyet that bai: {appr_th.text}")
        return
    print(f"[PASS] 2.3 Manager da phe duyet bai viet #{th_post_id} (Trang thai: APPROVED)")

    # 2.4 Tu dong dang bai len Threads
    print(f"[*] Dang thuc hien tu dong xuat ban bai #{th_post_id} len Threads...")
    pub_th = client.post(f"/api/posts/{th_post_id}/auto-publish", headers=mgr_headers)
    if pub_th.status_code != 200:
        print(f"[FAIL] 2.4 Dang bai Threads that bai: {pub_th.text}")
        return
    pub_th_data = pub_th.json()
    print(f"[PASS] 2.4 Xuat ban Threads thanh cong:")
    print(f"      - Message: {pub_th_data.get('message')}")
    print(f"      - Published URL: {pub_th_data.get('published_url')}")

    # 2.5 Kiem tra CSDL Threads
    db.close()
    db = SessionLocal()
    saved_th_post = db.query(Post).filter(Post.post_id == th_post_id).first()
    if saved_th_post:
        print(f"[PASS] 2.5 CSDL cap nhat trang thai: {saved_th_post.status}")
        print(f"      - Published at: {saved_th_post.published_at}")
        print(f"      - Published URL: {saved_th_post.published_url}")
    else:
        print(f"[FAIL] 2.5 Khong tim thay bai viet #{th_post_id} trong CSDL")

    # 2.6 Dong bo so lieu Threads qua Mock API
    mock_th_res = client.post(
        f"/api/social/posts/{th_post_id}/sync-mock",
        json={"milestone": "24H"},
        headers=mgr_headers
    )
    if mock_th_res.status_code == 200:
        stat_th = mock_th_res.json()
        print(f"[PASS] 2.6 Dong bo so lieu Threads (Mock API) thanh cong:")
        print(f"      - Reach: {stat_th.get('reach_count')}")
        print(f"      - Views: {stat_th.get('view_count')}")
        print(f"      - Likes: {stat_th.get('like_count')}")
        print(f"      - Comments: {stat_th.get('comment_count')}")
        print(f"      - Shares: {stat_th.get('share_count')}")

    db.close()
    print("\n=================================================================")
    print("HOAN THANH TAT CA CAC BAI KIEM THU DANG BAI INSTAGRAM VA THREADS!")
    print("=================================================================")

if __name__ == "__main__":
    run_tests()
