from typing import List, Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect, HTTPException, Query, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
import json

from app.core.database import get_db, SessionLocal
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
    summary="Lấy danh sách thông báo người dùng (FR-12 & Lưu trữ Offline)",
    description="Hỗ trợ lấy toàn bộ thông báo hoặc chỉ thông báo chưa đọc (để phục hồi thông báo khi người dùng offline quay lại)."
)
def get_notifications(
    unread_only: bool = Query(False, description="Chỉ lấy các thông báo chưa đọc"),
    limit: int = Query(50, ge=1, le=100, description="Số lượng thông báo tối đa"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    query = db.query(Notification).filter(Notification.recipient_id == current_user.user_id)
    if unread_only:
        query = query.filter(Notification.is_read == False)
    return query.order_by(Notification.created_at.desc()).limit(limit).all()

@router.get(
    "/notifications/unread-count",
    summary="Đếm số lượng thông báo chưa đọc",
    description="Dùng để hiển thị huy hiệu (Badge) số lượng thông báo chưa đọc trên giao diện Web."
)
def get_unread_notification_count(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    count = db.query(Notification).filter(
        Notification.recipient_id == current_user.user_id,
        Notification.is_read == False
    ).count()
    return {"unread_count": count}

@router.patch(
    "/notifications/{notification_id}/read",
    summary="Đánh dấu 1 thông báo là đã đọc (FR-12)"
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
    return {"message": "Đã đánh dấu thông báo là đã đọc", "status": "success", "notification_id": notification_id}

@router.patch(
    "/notifications/read-all",
    summary="Đánh dấu tất cả thông báo là đã đọc",
    description="Cập nhật toàn bộ thông báo chưa đọc của người dùng hiện tại sang trạng thái đã đọc."
)
def mark_all_notifications_as_read(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    updated = db.query(Notification).filter(
        Notification.recipient_id == current_user.user_id,
        Notification.is_read == False
    ).update({
        Notification.is_read: True,
        Notification.read_at: datetime.now()
    }, synchronize_session=False)
    db.commit()
    return {"message": f"Đã đánh dấu {updated} thông báo là đã đọc", "updated_count": updated, "status": "success"}

class TestNotificationRequest(BaseModel):
    title: str = Field("Thông báo kiểm thử Real-time", description="Tiêu đề thông báo")
    message: str = Field("Nội dung thông báo kiểm thử độ trễ WebSocket < 3s", description="Nội dung thông báo")
    notification_type: str = Field("SYSTEM_TEST", description="Loại thông báo")
    target_role: str = Field("MANAGER", description="Vai trò người nhận (MANAGER / STAFF)")

@router.post(
    "/notifications/test-broadcast",
    summary="Bắn thông báo thử nghiệm tới Role (Kiểm thử độ trễ & Lưu trữ Offline Task T06A664)",
    description="Lưu thông báo vào DB cho tất cả người dùng thuộc target_role, đồng thời phát qua WebSocket kèm timestamp để đo độ trễ."
)
async def test_broadcast_notification(
    payload: TestNotificationRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    users = db.query(User).join(User.role).filter(User.role.has(role_code=payload.target_role)).all()
    created_ids = []
    for u in users:
        notif = Notification(
            recipient_id=u.user_id,
            notification_type=payload.notification_type,
            title=payload.title,
            message=f"{payload.message} (Từ: {current_user.full_name})"
        )
        db.add(notif)
        db.flush()
        created_ids.append(notif.notification_id)
    db.commit()

    # Bắn qua WebSocket kèm server_timestamp
    delivered = await ws_manager.broadcast_to_role(payload.target_role, {
        "type": payload.notification_type,
        "title": payload.title,
        "message": f"{payload.message} (Từ: {current_user.full_name})",
        "sender_id": current_user.user_id,
        "sender_name": current_user.full_name,
        "server_timestamp": datetime.now(timezone.utc).isoformat()
    })

    return {
        "status": "success",
        "target_role": payload.target_role,
        "saved_to_db_count": len(created_ids),
        "delivered_live_ws_count": delivered,
        "server_timestamp": datetime.now(timezone.utc).isoformat()
    }

async def handle_websocket_connection(websocket: WebSocket, token: str):
    """Xử lý kết nối WebSocket tập trung với xác thực JWT và phản hồi sự kiện thời gian thực."""
    payload = decode_access_token(token)
    if not payload:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    try:
        user_id = int(payload.get("sub"))
    except (ValueError, TypeError):
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    role_code = payload.get("role", "STAFF")

    await ws_manager.connect(websocket, user_id, role_code)

    # Lấy số thông báo chưa đọc khi vừa kết nối (phục hồi dữ liệu offline)
    db = SessionLocal()
    try:
        unread_count = db.query(Notification).filter(
            Notification.recipient_id == user_id,
            Notification.is_read == False
        ).count()

        # Gửi thông điệp chào mừng kèm số thông báo chưa đọc
        await websocket.send_text(json.dumps({
            "type": "CONNECTION_ESTABLISHED",
            "message": "Kết nối WebSocket thông báo thời gian thực thành công!",
            "user_id": user_id,
            "role": role_code,
            "unread_count": unread_count,
            "server_timestamp": datetime.now(timezone.utc).isoformat()
        }, ensure_ascii=False))
    finally:
        db.close()

    try:
        while True:
            data = await websocket.receive_text()
            # Xử lý ping/pong giữ kết nối sống (Heartbeat)
            try:
                msg = json.loads(data)
                if msg.get("type") == "ping":
                    await websocket.send_text(json.dumps({
                        "type": "pong",
                        "client_time": msg.get("time"),
                        "server_timestamp": datetime.now(timezone.utc).isoformat()
                    }))
            except Exception:
                pass
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, user_id, role_code)

@router.websocket("/ws/notifications")
async def websocket_notifications_root(websocket: WebSocket, token: str):
    """Cổng kết nối WebSocket thời gian thực: ws://localhost:8000/ws/notifications?token=<JWT>"""
    await handle_websocket_connection(websocket, token)

@router.websocket("/notifications/ws")
async def websocket_notifications_alias(websocket: WebSocket, token: str):
    """Cổng kết nối WebSocket thời gian thực (alias): ws://localhost:8000/api/notifications/ws?token=<JWT>"""
    await handle_websocket_connection(websocket, token)
