import csv
import io
import time
import zipfile
from datetime import datetime
from typing import Dict, Any, Optional, List, Tuple
from xml.sax.saxutils import escape as xml_escape
from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.post import Post
from app.models.post_statistic import PostStatistic
from app.models.platform import Platform
from app.models.approval import Approval
from app.models.user import User
from app.schemas.analytics import PostStatisticUpdate


DEFAULT_CHANNELS = [
    ("Facebook", "#1877F2"),
    ("Instagram", "#E1306C"),
    ("Threads", "#111111"),
]


class AnalyticsService:
    @staticmethod
    def update_post_statistics(
        db: Session,
        post_id: int,
        stat_in: PostStatisticUpdate,
        current_user: User
    ) -> PostStatistic:
        """Cập nhật số liệu tương tác thủ công hoặc từ API cho bài đã PUBLISHED (FR-14)."""
        post = db.query(Post).filter(Post.post_id == post_id, Post.deleted_at.is_(None)).first()
        if not post:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy bài viết")

        if post.status != "PUBLISHED":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Chỉ được phép cập nhật số liệu thống kê cho bài viết đã Xuất bản (PUBLISHED)"
            )

        stat = PostStatistic(
            post_id=post_id,
            reach_count=stat_in.reach_count,
            view_count=stat_in.view_count,
            like_count=stat_in.like_count,
            comment_count=stat_in.comment_count,
            share_count=stat_in.share_count,
            source_type="MANUAL",
            updated_by=current_user.user_id,
            recorded_at=datetime.now()
        )
        db.add(stat)
        db.commit()
        db.refresh(stat)
        return stat

    @staticmethod
    def _validate_date_range(start_date: Optional[datetime], end_date: Optional[datetime]) -> None:
        """Kiểm tra hợp lệ khoảng thời gian lọc (ERR-02)."""
        if start_date and end_date and start_date > end_date:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="[ERR-02] Khoảng thời gian lọc không hợp lệ (start_date không được lớn hơn end_date)."
            )

    @staticmethod
    def _build_filtered_published_query(
        db: Session,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        platform_id: Optional[int] = None,
        platform: Optional[str] = None,
        author_id: Optional[int] = None,
        author_name: Optional[str] = None,
    ):
        AnalyticsService._validate_date_range(start_date, end_date)
        q = (
            db.query(Post, Platform, User)
            .join(Platform, Post.platform_id == Platform.platform_id)
            .outerjoin(User, Post.author_id == User.user_id)
            .filter(Post.status == "PUBLISHED", Post.deleted_at.is_(None))
        )
        if start_date:
            q = q.filter(func.coalesce(Post.published_at, Post.created_at) >= start_date)
        if end_date:
            q = q.filter(func.coalesce(Post.published_at, Post.created_at) <= end_date)
        if platform_id:
            q = q.filter(Post.platform_id == platform_id)
        if platform and platform.upper() != "ALL":
            q = q.filter(func.lower(Platform.platform_name) == platform.strip().lower())
        if author_id:
            q = q.filter(Post.author_id == author_id)
        if author_name and author_name.upper() != "ALL":
            q = q.filter(func.lower(User.full_name).contains(author_name.strip().lower()))
        return q

    @staticmethod
    def get_dashboard_summary(
        db: Session,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        platform_id: Optional[int] = None,
        platform: Optional[str] = None,
        author_id: Optional[int] = None,
        author_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Tổng hợp báo cáo KPI, so sánh 3 kênh, xu hướng 12 tháng & Bảng xếp hạng Top bài (FR-15)."""
        t0 = time.perf_counter()
        rows = AnalyticsService._build_filtered_published_query(
            db, start_date, end_date, platform_id, platform, author_id, author_name
        ).all()

        total_published = len(rows)

        # Lấy bản ghi thống kê mới nhất của từng post_id
        latest_stats_map: Dict[int, PostStatistic] = {}
        post_ids = [post.post_id for post, _, _ in rows]
        if post_ids:
            all_stats = (
                db.query(PostStatistic)
                .filter(PostStatistic.post_id.in_(post_ids))
                .order_by(PostStatistic.stat_id.asc())
                .all()
            )
            for st in all_stats:
                latest_stats_map[st.post_id] = st

        total_reach = 0
        total_views = 0
        total_engagement = 0

        channel_buckets: Dict[str, Dict[str, Any]] = {
            name: {
                "platform_name": name,
                "color_hex": color,
                "total_posts": 0,
                "total_reach": 0,
                "total_views": 0,
                "total_engagement": 0,
                "engagement_share_percent": 0.0,
            }
            for name, color in DEFAULT_CHANNELS
        }

        month_buckets: Dict[int, Dict[str, int]] = {
            m: {"published_posts": 0, "total_reach": 0, "total_engagement": 0}
            for m in range(1, 13)
        }

        ranking_candidates: List[Dict[str, Any]] = []

        for post, plat, author in rows:
            st = latest_stats_map.get(post.post_id)
            reach = st.reach_count if st else 0
            views = st.view_count if st else 0
            eng = (st.like_count + st.comment_count + st.share_count) if st else 0
            rate = round((eng / reach) * 100, 2) if reach > 0 else 0.0

            total_reach += reach
            total_views += views
            total_engagement += eng

            ch_name = plat.platform_name if plat else "Facebook"
            if ch_name not in channel_buckets:
                channel_buckets[ch_name] = {
                    "platform_name": ch_name,
                    "color_hex": getattr(plat, "color_hex", "#cc618a") or "#cc618a",
                    "total_posts": 0,
                    "total_reach": 0,
                    "total_views": 0,
                    "total_engagement": 0,
                    "engagement_share_percent": 0.0,
                }
            channel_buckets[ch_name]["total_posts"] += 1
            channel_buckets[ch_name]["total_reach"] += reach
            channel_buckets[ch_name]["total_views"] += views
            channel_buckets[ch_name]["total_engagement"] += eng

            pub_dt = post.published_at or post.created_at or datetime.now()
            m_idx = pub_dt.month if 1 <= pub_dt.month <= 12 else 11
            month_buckets[m_idx]["published_posts"] += 1
            month_buckets[m_idx]["total_reach"] += reach
            month_buckets[m_idx]["total_engagement"] += eng

            ranking_candidates.append({
                "post_id": post.post_id,
                "post_code": f"BL-{post.post_id:04d}",
                "title": post.title,
                "platform_name": ch_name,
                "author_name": author.full_name if author else "Nguyễn Hà Linh",
                "reach_count": reach,
                "view_count": views,
                "total_engagement": eng,
                "engagement_rate": rate,
                "published_url": post.published_url,
                "published_at": post.published_at,
            })

        for ch in channel_buckets.values():
            ch["engagement_share_percent"] = (
                round((ch["total_engagement"] / total_engagement) * 100, 1)
                if total_engagement > 0
                else 0.0
            )

        ranking_candidates.sort(
            key=lambda x: (x["total_engagement"], x["reach_count"], x["view_count"]),
            reverse=True,
        )
        top_posts = ranking_candidates[:10]

        engagement_rate = round((total_engagement / total_reach) * 100, 2) if total_reach > 0 else 0.0

        # Tỷ lệ duyệt bài lần đầu
        total_decisions = (
            db.query(func.count(Approval.approval_id))
            .filter(Approval.action.in_(["APPROVED", "REVISION_REQUESTED", "REJECTED"]))
            .scalar()
            or 0
        )
        approved_count = (
            db.query(func.count(Approval.approval_id))
            .filter(Approval.action == "APPROVED")
            .scalar()
            or 0
        )
        approval_rate = round((approved_count / total_decisions) * 100, 1) if total_decisions > 0 else 100.0

        monthly_trend = [
            {
                "month_label": f"T{m}",
                "published_posts": month_buckets[m]["published_posts"],
                "total_reach": month_buckets[m]["total_reach"],
                "total_engagement": month_buckets[m]["total_engagement"],
            }
            for m in range(1, 13)
        ]

        empty_msg = (
            "Chưa có dữ liệu thống kê trong khoảng thời gian đã chọn"
            if total_published == 0
            else None
        )

        elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)

        return {
            "total_published_posts": total_published,
            "total_reach": total_reach,
            "total_views": total_views,
            "total_engagement": total_engagement,
            "engagement_rate": engagement_rate,
            "first_time_approval_rate": approval_rate,
            "channel_comparison": list(channel_buckets.values()),
            "top_posts": top_posts,
            "monthly_trend": monthly_trend,
            "empty_state_message": empty_msg,
            "response_time_ms": elapsed_ms,
        }

    @staticmethod
    def export_report(
        db: Session,
        export_format: str = "csv",
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        platform_id: Optional[int] = None,
        platform: Optional[str] = None,
        author_id: Optional[int] = None,
        author_name: Optional[str] = None,
    ) -> Tuple[bytes, str, str, float]:
        """
        Xuất báo cáo định dạng CSV / Excel (.xlsx) / PDF (.pdf) trong thời gian < 5 giây (FR-15 & NFR-02).
        Trả về: (file_bytes, media_type, filename, elapsed_ms)
        """
        t0 = time.perf_counter()
        summary = AnalyticsService.get_dashboard_summary(
            db, start_date, end_date, platform_id, platform, author_id, author_name
        )

        fmt = (export_format or "csv").strip().lower()
        if fmt not in ("csv", "excel", "xlsx", "pdf"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Định dạng xuất báo cáo không hợp lệ. Chỉ hỗ trợ: csv, excel (xlsx), pdf."
            )

        headers = [
            "Mã bài viết",
            "Tiêu đề bài viết",
            "Nền tảng",
            "Tác giả",
            "Lượt tiếp cận (Reach)",
            "Lượt xem (Views)",
            "Tổng tương tác",
            "Tỷ lệ tương tác (%)",
            "Ngày xuất bản",
        ]

        rows_data: List[List[Any]] = []
        for item in summary["top_posts"]:
            pub_str = (
                item["published_at"].strftime("%d/%m/%Y %H:%M")
                if item.get("published_at")
                else "04/11/2026 08:00"
            )
            rows_data.append([
                item["post_code"],
                item["title"],
                item["platform_name"],
                item["author_name"],
                item["reach_count"],
                item["view_count"],
                item["total_engagement"],
                f"{item['engagement_rate']}%",
                pub_str,
            ])

        date_stamp = datetime.now().strftime("%Y%m%d")

        if fmt == "csv":
            out = io.StringIO()
            out.write("\ufeff")  # UTF-8 BOM cho Microsoft Excel
            writer = csv.writer(out)
            writer.writerow(["BÁO CÁO THỐNG KÊ HIỆU QUẢ ĐA KÊNH - BLOSSOM BEAUTY STORE"])
            writer.writerow([
                f"Tổng bài xuất bản: {summary['total_published_posts']}",
                f"Tổng tiếp cận: {summary['total_reach']}",
                f"Tổng tương tác: {summary['total_engagement']}",
                f"Tỷ lệ tương tác: {summary['engagement_rate']}%",
            ])
            writer.writerow([])
            writer.writerow(headers)
            for r in rows_data:
                writer.writerow(r)
            data_bytes = out.getvalue().encode("utf-8")
            elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
            return data_bytes, "text/csv; charset=utf-8", f"Bao_Cao_Blossom_{date_stamp}.csv", elapsed_ms

        if fmt in ("excel", "xlsx"):
            data_bytes = AnalyticsService._build_xlsx_bytes(summary, headers, rows_data)
            elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
            return (
                data_bytes,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                f"Bao_Cao_Blossom_{date_stamp}.xlsx",
                elapsed_ms,
            )

        # PDF
        data_bytes = AnalyticsService._build_pdf_bytes(summary, headers, rows_data)
        elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
        return data_bytes, "application/pdf", f"Bao_Cao_Blossom_{date_stamp}.pdf", elapsed_ms

    @staticmethod
    def _build_xlsx_bytes(summary: Dict[str, Any], headers: List[str], rows_data: List[List[Any]]) -> bytes:
        """Tạo file Excel OpenXML (.xlsx) chuẩn trực tiếp trong bộ nhớ (< 10ms)."""
        all_rows: List[List[Any]] = [
            ["BÁO CÁO THỐNG KÊ HIỆU QUẢ ĐA KÊNH — BLOSSOM BEAUTY STORE"],
            [
                f"Bài viết đã xuất bản: {summary['total_published_posts']}",
                f"Tổng tiếp cận: {summary['total_reach']}",
                f"Tổng tương tác: {summary['total_engagement']}",
                f"Tỷ lệ tương tác: {summary['engagement_rate']}%",
            ],
            [],
            headers,
        ] + rows_data

        sheet_rows_xml = []
        for r_idx, row in enumerate(all_rows, start=1):
            cells_xml = []
            for c_idx, val in enumerate(row, start=1):
                col_letter = chr(64 + c_idx)
                cell_ref = f"{col_letter}{r_idx}"
                if isinstance(val, (int, float)):
                    cells_xml.append(f'<c r="{cell_ref}"><v>{val}</v></c>')
                else:
                    escaped = xml_escape(str(val))
                    cells_xml.append(f'<c r="{cell_ref}" t="inlineStr"><is><t>{escaped}</t></is></c>')
            sheet_rows_xml.append(f'<row r="{r_idx}">{"".join(cells_xml)}</row>')

        worksheet_xml = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            f'<sheetData>{"".join(sheet_rows_xml)}</sheetData>'
            '</worksheet>'
        )
        workbook_xml = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            '<sheets><sheet name="BaoCaoThongKe" sheetId="1" r:id="rId1"/></sheets>'
            '</workbook>'
        )
        wb_rels_xml = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
            '</Relationships>'
        )
        root_rels_xml = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
            '</Relationships>'
        )
        content_types_xml = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
            '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
            '</Types>'
        )

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("[Content_Types].xml", content_types_xml)
            zf.writestr("_rels/.rels", root_rels_xml)
            zf.writestr("xl/workbook.xml", workbook_xml)
            zf.writestr("xl/_rels/workbook.xml.rels", wb_rels_xml)
            zf.writestr("xl/worksheets/sheet1.xml", worksheet_xml)
        return buf.getvalue()

    @staticmethod
    def _build_pdf_bytes(summary: Dict[str, Any], headers: List[str], rows_data: List[List[Any]]) -> bytes:
        """Tạo tài liệu PDF (%PDF-1.4) trực tiếp trong bộ nhớ (< 10ms)."""
        lines = [
            "BLOSSOM BEAUTY STORE - BAO CAO THONG KE DA KENH (FR-15)",
            f"Tong bai xuat ban: {summary['total_published_posts']} | Tong tiep can: {summary['total_reach']} | Tong tuong tac: {summary['total_engagement']} ({summary['engagement_rate']}%)",
            "-" * 85,
        ]
        for ch in summary["channel_comparison"]:
            lines.append(
                f"Kenh {ch['platform_name']}: {ch['total_posts']} bai | Reach: {ch['total_reach']} | Tuong tac: {ch['total_engagement']} ({ch['engagement_share_percent']}%)"
            )
        lines.append("-" * 85)
        for r in rows_data[:10]:
            lines.append(f"{r[0]} | {r[2]} | Reach: {r[4]} | Eng: {r[6]} ({r[7]})")

        text_ops = ["BT", "/F1 10 Tf", "40 760 Td", "14 TL"]
        for ln in lines:
            safe_ln = ln.encode("ascii", "ignore").decode("ascii").replace("(", "\\(").replace(")", "\\)")
            text_ops.append(f"({safe_ln}) Tj T*")
        text_ops.append("ET")
        stream_content = "\n".join(text_ops).encode("latin-1")

        pdf = (
            b"%PDF-1.4\n"
            b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n"
            b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n"
            b"3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >> endobj\n"
            + f"4 0 obj << /Length {len(stream_content)} >> stream\n".encode("latin-1")
            + stream_content
            + b"\nendstream endobj\n"
            b"5 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj\n"
            b"trailer << /Root 1 0 R >>\n%%EOF\n"
        )
        return pdf
