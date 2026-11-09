from typing import List
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user, RoleGuard
from app.models.user import User
from app.schemas.approval import ApprovalSubmit, ApprovalAction, ApprovalResponse
from app.services.approval_service import ApprovalService

router = APIRouter(prefix="/posts", tags=["MOD-04: Approval Workflow"])

@router.post(
    "/{post_id}/submit",
    response_model=ApprovalResponse,
    summary="Gửi duyệt bài viết (FR-08)",
    description="Marketing Staff chuyển trạng thái Post từ DRAFT/REJECTED sang PENDING_APPROVAL."
)
async def submit_post(
    post_id: int,
    submit_in: ApprovalSubmit,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return await ApprovalService.submit_post(db, post_id, submit_in, current_user)

@router.post(
    "/{post_id}/approve",
    response_model=ApprovalResponse,
    summary="Phê duyệt bài viết (FR-09 & AC-10)",
    description="Chỉ Marketing Manager có quyền phê duyệt. Tự động đồng bộ lên Content Calendar với ACID transaction."
)
async def approve_post(
    post_id: int,
    current_user: User = Depends(RoleGuard(["MANAGER"])),
    db: Session = Depends(get_db)
):
    return await ApprovalService.approve_post(db, post_id, current_user)

@router.post(
    "/{post_id}/reject",
    response_model=ApprovalResponse,
    summary="Từ chối hoặc Yêu cầu sửa đổi (FR-10 & AC-09)",
    description="Chỉ Marketing Manager có quyền thực hiện. Bắt buộc nhập lý do."
)
async def reject_post(
    post_id: int,
    action_in: ApprovalAction,
    current_user: User = Depends(RoleGuard(["MANAGER"])),
    db: Session = Depends(get_db)
):
    return await ApprovalService.reject_post(db, post_id, action_in, current_user)

@router.get(
    "/{post_id}/approvals",
    response_model=List[ApprovalResponse],
    summary="Xem lịch sử kiểm duyệt của bài viết (BR-07)"
)
def get_approval_history(
    post_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return ApprovalService.get_approval_history(db, post_id)
