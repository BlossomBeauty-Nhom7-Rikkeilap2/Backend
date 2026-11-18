import sys
import os
from datetime import datetime, timedelta

# Cau hinh UTF-8 tranh loi charmap UnicodeEncodeError tren Windows console
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from app.core.database import SessionLocal
from app.models.user import User
from app.models.post import Post
from app.models.post_statistic import PostStatistic
from app.schemas.analytics import PostStatisticCreate, MockSyncRequest
from app.services.analytics_service import AnalyticsService

def run_stats_demo():
    print("=" * 85)
    print("   DEMO THUC TE: CAP NHAT SO LIEU THONG KE & DONG BO API (FR-14 / TASK T06A66B)")
    print("=" * 85)

    db = SessionLocal()
    try:
        # Tim nguoi dung thao tac
        staff = db.query(User).filter(User.username == "staff1").first()
        if not staff:
            staff = db.query(User).first()
        print(f"Nguoi dung thuc hien: {staff.full_name} (ID: {staff.user_id})")

        # Tim bai viet da PUBLISHED de thuc hien cap nhat
        published_post = db.query(Post).filter(Post.status == "PUBLISHED", Post.deleted_at.is_(None)).first()
        if not published_post:
            print("Chua co bai viet PUBLISHED trong CSDL. Vui long chay init_db.py truoc.")
            return

        print(f"Bai viet duoc chon: #{published_post.post_id} - '{published_post.title}'")
        print(f"Trang thai bai viet: {published_post.status}")
        print(f"Ngay xuat ban: {published_post.published_at}")

        # ----------------------------------------------------------------------
        # 1. KIEM THU NHAP TAY SO LIEU (MANUAL INPUT - SO NGUYEN >= 0)
        # ----------------------------------------------------------------------
        print("\n" + "-" * 85)
        print("[BUOC 1] NHAP TAY SO LIEU THONG KE (SOURCE = MANUAL, CHI SO >= 0):")
        manual_data = PostStatisticCreate(
            reach_count=18500,
            view_count=14200,
            like_count=1050,
            comment_count=180,
            share_count=65,
            source_type="MANUAL",
            milestone="24H"
        )
        stat1 = AnalyticsService.record_statistics(db, published_post.post_id, manual_data, staff)
        print(f"  -> Da ghi nhan thanh cong ban ghi ID #{stat1.stat_id}")
        print(f"     Nguon: {stat1.source_type} | Moc: {stat1.milestone}")
        print(f"     Reach: {stat1.reach_count:,} | Views: {stat1.view_count:,}")
        print(f"     Likes: {stat1.like_count:,} | Comments: {stat1.comment_count:,} | Shares: {stat1.share_count:,}")
        print(f"     Thoi diem ghi nhan: {stat1.recorded_at}")

        # ----------------------------------------------------------------------
        # 2. KIEM THU BAT LOI KHI NHAP SO AM (< 0)
        # ----------------------------------------------------------------------
        print("\n" + "-" * 85)
        print("[BUOC 2] KIEM THU RANG BUOC TOAN VEN: CHIEU CHUAN SO NGUYEN >= 0:")
        try:
            AnalyticsService._validate_integer_metrics(-50, 100, 10, 5, 2)
            print("  [LOI]: He thong khong chan duoc so am!")
        except Exception as e:
            print(f"  -> He thong da chan thanh cong so am hop le: {getattr(e, 'detail', str(e))}")

        # ----------------------------------------------------------------------
        # 3. KIEM THU BAT LOI KHI NHAP CHO BAI VIET CHUA PUBLISHED (BR-08)
        # ----------------------------------------------------------------------
        print("\n" + "-" * 85)
        print("[BUOC 3] KIEM THU QUY TAC NGHIEP VU BR-08 (CHI CHO PHEP BAI PUBLISHED):")
        draft_post = db.query(Post).filter(Post.status != "PUBLISHED", Post.deleted_at.is_(None)).first()
        if draft_post:
            try:
                AnalyticsService.record_statistics(db, draft_post.post_id, manual_data, staff)
                print(f"  [LOI]: Bai #{draft_post.post_id} co trang thai {draft_post.status} van duoc ghi nhan!")
            except Exception as e:
                print(f"  -> Chan thanh cong bai viet trang thai '{draft_post.status}': {getattr(e, 'detail', str(e))}")
        else:
            print("  -> Khong co bai DRAFT/PENDING de kiem tra, bo qua buoc nay.")

        # ----------------------------------------------------------------------
        # 4. KIEM THU DONG BO QUA MOCK API (BONUS +1 - SOURCE = API)
        # ----------------------------------------------------------------------
        print("\n" + "-" * 85)
        print("[BUOC 4] DONG BO SO LIEU QUA MOCK API (GOI Y THUONG +1, SOURCE = API):")
        mock_req = MockSyncRequest(
            milestone="7D",
            reach_count=35000,
            view_count=28500,
            like_count=2100,
            comment_count=320,
            share_count=110
        )
        stat_mock = AnalyticsService.sync_mock_statistics(db, published_post.post_id, staff, mock_req)
        print(f"  -> Da dong bo Mock API thanh cong: Ban ghi ID #{stat_mock.stat_id}")
        print(f"     Nguon: {stat_mock.source_type} | Moc: {stat_mock.milestone}")
        print(f"     Reach: {stat_mock.reach_count:,} | Views: {stat_mock.view_count:,}")
        print(f"     Likes: {stat_mock.like_count:,} | Comments: {stat_mock.comment_count:,} | Shares: {stat_mock.share_count:,}")

        # ----------------------------------------------------------------------
        # 5. TAO BO 3 MOC CHUAN (24H, 7D, 30D)
        # ----------------------------------------------------------------------
        print("\n" + "-" * 85)
        print("[BUOC 5] TAO BO 3 MOC THOI GIAN CHUAN (24H, 7D, 30D) PHUC VU DEMO BIEU DO:")
        sim_stats = AnalyticsService.simulate_milestones(db, published_post.post_id, staff)
        print(f"  -> Da tao thanh cong {len(sim_stats)} moc chuan:")
        for s in sim_stats:
            print(f"     * Moc {s.milestone}: Reach = {s.reach_count:,} | Views = {s.view_count:,} | Engagement = {s.like_count + s.comment_count + s.share_count:,} | Thoi diem = {s.recorded_at}")

        # ----------------------------------------------------------------------
        # 6. TRUY VAN LICH SU VA TY LE TANG TRUONG
        # ----------------------------------------------------------------------
        print("\n" + "-" * 85)
        print("[BUOC 6] TRUY VAN LICH SU SO LIEU VA TINH TY LE TANG TRUONG GIUA CAC MOC:")
        history = AnalyticsService.get_post_statistics_history(db, published_post.post_id)
        print(f"  Tong so ban ghi lich su: {history.total_records}")
        print("  Chi tiet cac ban ghi:")
        for idx, h in enumerate(history.history, 1):
            print(f"    [{idx}] ID: #{h.stat_id} | Moc: {h.milestone or 'N/A':<6} | Nguon: {h.source_type:<6} | Reach: {h.reach_count:<8,} | Views: {h.view_count:<8,} | Tong tuong tac: {h.total_engagement:<6,} | Ty le: {h.engagement_rate}%")

        print("\n  So sanh ty le tang truong (% Growth Rate):")
        if history.growth_rate.m24h_to_m7d:
            g1 = history.growth_rate.m24h_to_m7d
            def fmt_pct(val):
                return f"+{val}%" if val >= 0 else f"{val}%"
            print(f"    * Tang truong tu moc 24h len moc 7 ngay:")
            print(f"      + Reach tang:      {fmt_pct(g1['reach_growth_pct'])}")
            print(f"      + Views tang:      {fmt_pct(g1['views_growth_pct'])}")
            print(f"      + Engagement tang: {fmt_pct(g1['engagement_growth_pct'])}")
        if history.growth_rate.m7d_to_m30d:
            g2 = history.growth_rate.m7d_to_m30d
            def fmt_pct(val):
                return f"+{val}%" if val >= 0 else f"{val}%"
            print(f"    * Tang truong tu moc 7 ngay len moc 30 ngay:")
            print(f"      + Reach tang:      {fmt_pct(g2['reach_growth_pct'])}")
            print(f"      + Views tang:      {fmt_pct(g2['views_growth_pct'])}")
            print(f"      + Engagement tang: {fmt_pct(g2['engagement_growth_pct'])}")

        # ----------------------------------------------------------------------
        # 7. BO LOC THEO TIMEFRAME GAN DAY (24h, 7d, 30d)
        # ----------------------------------------------------------------------
        print("\n" + "-" * 85)
        print("[BUOC 7] BO LOC THEO TIMEFRAME (24h / 7d / 30d / all):")
        for tf in ["24h", "7d", "30d", "all"]:
            tf_res = AnalyticsService.get_post_statistics_history(db, published_post.post_id, timeframe=tf)
            print(f"  -> Timeframe = '{tf}': tim thay {tf_res.total_records} ban ghi phu hop")

        print("\n" + "=" * 85)
        print("   HOAN TAT KIEM THU DEMO FR-14 THANH CONG MIEN MAN!")
        print("=" * 85)

    finally:
        db.close()

if __name__ == "__main__":
    run_stats_demo()
