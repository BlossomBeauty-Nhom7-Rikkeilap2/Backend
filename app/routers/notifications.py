from typing import List
from datetime import datetime
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.security import decode_access_token
from app.core.websocket import manager as ws_manager
from app.models.user import User
from app.models.notification import Notification
from app.schemas.notification import NotificationResponse

router = APIRouter(tags=["Notifications & Real-time WebSocket"])

@router.get(
    "/notifications",
    response_model=List[NotificationResponse],
    summary="Lấy danh sách thông báo người dùng (FR-12)"
)
def get_notifications(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return (
        db.query(Notification)
        .filter(Notification.recipient_id == current_user.user_id)
        .order_by(Notification.created_at.desc())
        .limit(50)
        .all()
    )

@router.patch(
    "/notifications/{notification_id}/read",
    summary="Đánh dấu thông báo đã đọc (FR-12)"
)
def mark_notification_as_read(
    notification_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    notif = db.query(Notification).filter(
        Notification.notification_id == notification_id,
        Notification.recipient_id == current_user.user_id
    ).first()

    if not notif:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy thông báo")

    notif.is_read = True
    notif.read_at = datetime.now()
    db.commit()
    return {"message": "Đã đánh dấu thông báo là đã đọc", "status": "success"}

@router.websocket("/ws/notifications")
async def websocket_notifications_endpoint(websocket: WebSocket, token: str, db: Session = Depends(get_db)):
    """
    Cổng kết nối WebSocket thời gian thực (SDD 2.1 & FR-12).
    Xác thực token qua query parameter: ws://localhost:8000/ws/notifications?token=<JWT>
    """
    payload = decode_access_token(token)
    if not payload:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    user_id = payload.get("sub")
    role_code = payload.get("role", "STAFF")

    await ws_manager.connect(websocket, user_id, role_code)
    try:
        while True:
            # Lắng nghe ping/pong giữ kết nối
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, user_id, role_code)
