from datetime import datetime, timedelta
from typing import List
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.post import Post
from app.models.approval import Approval
from app.models.schedule import Schedule
from app.models.notification import Notification
from app.models.user import User
from app.schemas.approval import ApprovalSubmit, ApprovalAction
from app.core.websocket import manager as ws_manager

class ApprovalService:
    @staticmethod
    async def submit_post(db: Session, post_id: int, submit_in: ApprovalSubmit, current_user: User) -> Approval:
        """Gửi duyệt bài viết (Staff) - SDD 3.2.4 & FR-08."""
        post = db.query(Post).filter(Post.post_id == post_id, Post.deleted_at.is_(None)).first()
        if not post:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy bài viết")

        if post.author_id != current_user.user_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Chỉ tác giả mới được phép gửi duyệt bài viết này")

        if post.status not in ["DRAFT", "REVISION_REQUESTED", "REJECTED"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Không thể gửi duyệt bài viết đang ở trạng thái {post.status}"
            )

        action = "RESUBMITTED" if post.status in ["REVISION_REQUESTED", "REJECTED"] else "SUBMITTED"
        post.status = "PENDING_APPROVAL"

        approval = Approval(
            post_id=post_id,
            actor_id=current_user.user_id,
            action=action,
            comment=submit_in.comment
        )
        db.add(approval)

        # Tạo Notification cho Marketing Manager
        # Tìm tất cả Manager
        managers = db.query(User).join(User.role).filter(User.role.has(role_code="MANAGER")).all()
        for mgr in managers:
            notif = Notification(
                recipient_id=mgr.user_id,
                post_id=post.post_id,
                notification_type="APPROVAL_REQUEST",
                title="Yêu cầu phê duyệt bài viết mới",
                message=f"Nhân viên {current_user.full_name} đã gửi duyệt bài: '{post.title}'"
            )
            db.add(notif)

        db.commit()
        db.refresh(approval)

        # Phát thông báo WebSocket tới tất cả Manager
        await ws_manager.broadcast_to_role("MANAGER", {
            "type": "APPROVAL_REQUEST",
            "post_id": post.post_id,
            "title": post.title,
            "author": current_user.full_name
        })

        return approval

    @staticmethod
    async def approve_post(db: Session, post_id: int, current_user: User) -> Approval:
        """
        Phê duyệt bài viết (Chỉ Manager) với ACID Transaction (SDD 5.1 & AC-10).
        Tự động đồng bộ lên Content Calendar (bảng schedules).
        """
        post = db.query(Post).filter(Post.post_id == post_id, Post.deleted_at.is_(None)).first()
        if not post:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy bài viết")

        if post.status != "PENDING_APPROVAL":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Chỉ có thể phê duyệt bài viết đang ở trạng thái Chờ duyệt (PENDING_APPROVAL)"
            )

        try:
            # 1. Cập nhật trạng thái Post sang APPROVED
            post.status = "APPROVED"

            # 2. Ghi log lịch sử phê duyệt
            approval = Approval(
                post_id=post_id,
                actor_id=current_user.user_id,
                action="APPROVED",
                comment="Phê duyệt bài viết"
            )
            db.add(approval)

            # 3. Tự động đồng bộ hiển thị lên Content Calendar (bảng schedules - AC-10)
            scheduled_time = post.planned_publish_time or (datetime.now() + timedelta(days=1))
            schedule = db.query(Schedule).filter(Schedule.post_id == post_id).first()
            if schedule:
                schedule.scheduled_time = scheduled_time
                schedule.schedule_status = "ACTIVE"
            else:
                schedule = Schedule(
                    post_id=post_id,
                    scheduled_time=scheduled_time,
                    scheduled_by=current_user.user_id,
                    schedule_status="ACTIVE"
                )
                db.add(schedule)

            # 4. Gửi thông báo cho tác giả bài viết
            notif = Notification(
                recipient_id=post.author_id,
                post_id=post.post_id,
                notification_type="POST_APPROVED",
                title="Bài viết đã được phê duyệt!",
                message=f"Bài viết '{post.title}' của bạn đã được Quản lý {current_user.full_name} phê duyệt."
            )
            db.add(notif)

            db.commit()
            db.refresh(approval)

            # Đẩy Notification qua WebSocket
            await ws_manager.send_to_user(post.author_id, {
                "type": "POST_APPROVED",
                "post_id": post.post_id,
                "title": post.title
            })

            return approval
        except Exception as e:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Lỗi giao dịch khi phê duyệt bài viết: {str(e)}"
            )

    @staticmethod
    async def reject_post(db: Session, post_id: int, action_in: ApprovalAction, current_user: User) -> Approval:
        """
        Từ chối hoặc Yêu cầu sửa đổi (Chỉ Manager).
        BẮT BUỘC nhập lý do theo SDD FR-10 & BR-02.
        """
        if not action_in.comment or not action_in.comment.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Lý do từ chối hoặc yêu cầu chỉnh sửa là bắt buộc."
            )

        post = db.query(Post).filter(Post.post_id == post_id, Post.deleted_at.is_(None)).first()
        if not post:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy bài viết")

        if post.status != "PENDING_APPROVAL":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Bài viết không ở trạng thái Chờ duyệt")

        target_status = "REVISION_REQUESTED" if action_in.action == "REVISION_REQUESTED" else "REJECTED"
        post.status = target_status

        try:
            approval = Approval(
                post_id=post_id,
                actor_id=current_user.user_id,
                action=action_in.action,
                comment=action_in.comment.strip()
            )
            db.add(approval)

            # Nếu có lịch đăng, hủy bỏ lịch đăng (AC-09)
            schedule = db.query(Schedule).filter(Schedule.post_id == post_id).first()
            if schedule:
                schedule.schedule_status = "CANCELLED"

            # Gửi thông báo cho tác giả
            notif = Notification(
                recipient_id=post.author_id,
                post_id=post.post_id,
                notification_type="POST_REJECTED",
                title=f"Bài viết bị {('yêu cầu sửa' if target_status == 'REVISION_REQUESTED' else 'từ chối')}",
                message=f"Lý do từ Quản lý: {action_in.comment.strip()}"
            )
            db.add(notif)

            db.commit()
            db.refresh(approval)

            await ws_manager.send_to_user(post.author_id, {
                "type": "POST_REJECTED",
                "post_id": post.post_id,
                "status": target_status,
                "reason": action_in.comment.strip()
            })

            return approval
        except Exception as e:
            db.rollback()
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

    @staticmethod
    def get_approval_history(db: Session, post_id: int) -> List[Approval]:
        """Xem toàn bộ lịch sử duyệt bài của một Post (BR-07)."""
        return db.query(Approval).filter(Approval.post_id == post_id).order_by(Approval.created_at.desc()).all()
