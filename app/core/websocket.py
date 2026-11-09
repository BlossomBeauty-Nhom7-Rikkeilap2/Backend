from typing import Dict, List, Set, Any
from fastapi import WebSocket
import json

class ConnectionManager:
    """
    Quản lý kết nối WebSocket thời gian thực (Real-time Gateway theo SDD 2.1).
    Hỗ trợ gửi thông báo theo từng người dùng (user_id) hoặc theo nhóm vai trò (role_code).
    """
    def __init__(self):
        # Lưu kết nối theo user_id: {user_id: [WebSocket, ...]}
        self.active_users: Dict[int, List[WebSocket]] = {}
        # Lưu kết nối theo vai trò: {"MANAGER": {WebSocket, ...}, "STAFF": {WebSocket, ...}}
        self.role_rooms: Dict[str, Set[WebSocket]] = {
            "MANAGER": set(),
            "STAFF": set()
        }

    async def connect(self, websocket: WebSocket, user_id: int, role_code: str):
        await websocket.accept()
        if user_id not in self.active_users:
            self.active_users[user_id] = []
        self.active_users[user_id].append(websocket)

        if role_code in self.role_rooms:
            self.role_rooms[role_code].add(websocket)

    def disconnect(self, websocket: WebSocket, user_id: int, role_code: str):
        if user_id in self.active_users:
            if websocket in self.active_users[user_id]:
                self.active_users[user_id].remove(websocket)
            if not self.active_users[user_id]:
                del self.active_users[user_id]

        if role_code in self.role_rooms:
            self.role_rooms[role_code].discard(websocket)

    async def send_to_user(self, user_id: int, message: Dict[str, Any]):
        """Gửi thông báo tới riêng một người dùng."""
        if user_id in self.active_users:
            payload = json.dumps(message, ensure_ascii=False)
            for connection in self.active_users[user_id]:
                try:
                    await connection.send_text(payload)
                except Exception:
                    pass

    async def broadcast_to_role(self, role_code: str, message: Dict[str, Any]):
        """Gửi thông báo tới toàn bộ người dùng thuộc một vai trò (ví dụ: tất cả MANAGER)."""
        if role_code in self.role_rooms:
            payload = json.dumps(message, ensure_ascii=False)
            for connection in list(self.role_rooms[role_code]):
                try:
                    await connection.send_text(payload)
                except Exception:
                    pass

manager = ConnectionManager()
