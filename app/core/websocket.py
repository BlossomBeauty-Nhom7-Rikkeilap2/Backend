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
        uid = int(user_id)
        await websocket.accept()
        if uid not in self.active_users:
            self.active_users[uid] = []
        self.active_users[uid].append(websocket)

        if role_code in self.role_rooms:
            self.role_rooms[role_code].add(websocket)

    def disconnect(self, websocket: WebSocket, user_id: int, role_code: str):
        uid = int(user_id)
        if uid in self.active_users:
            if websocket in self.active_users[uid]:
                self.active_users[uid].remove(websocket)
            if not self.active_users[uid]:
                del self.active_users[uid]

        if role_code in self.role_rooms:
            self.role_rooms[role_code].discard(websocket)

    async def send_to_user(self, user_id: int, message: Dict[str, Any]):
        """Gửi thông báo tới riêng một người dùng."""
        uid = int(user_id)
        if uid not in self.active_users:
            return
        payload = json.dumps(message, ensure_ascii=False)
        dead_connections: List[WebSocket] = []
        for connection in list(self.active_users[uid]):
            try:
                await connection.send_text(payload)
            except Exception:
                dead_connections.append(connection)
        for conn in dead_connections:
            if uid in self.active_users and conn in self.active_users[uid]:
                self.active_users[uid].remove(conn)
            for room in self.role_rooms.values():
                room.discard(conn)
        if uid in self.active_users and not self.active_users[uid]:
            del self.active_users[uid]

    async def broadcast_to_role(self, role_code: str, message: Dict[str, Any]):
        """Gửi thông báo tới toàn bộ người dùng thuộc một vai trò (ví dụ: tất cả MANAGER)."""
        if role_code not in self.role_rooms:
            return
        payload = json.dumps(message, ensure_ascii=False)
        dead_connections: List[WebSocket] = []
        for connection in list(self.role_rooms[role_code]):
            try:
                await connection.send_text(payload)
            except Exception:
                dead_connections.append(connection)
        for conn in dead_connections:
            self.role_rooms[role_code].discard(conn)

manager = ConnectionManager()
