from typing import Dict, List, Set, Any
from datetime import datetime, timezone
from fastapi import WebSocket
import json

class ConnectionManager:
    """
    Quản lý kết nối WebSocket thời gian thực (Real-time Gateway theo SDD 2.1 & Task T06A664).
    Hỗ trợ gửi thông báo tức thời tới từng người dùng (user_id) hoặc broadcast theo vai trò (role_code).
    Đáp ứng yêu cầu phi chức năng: độ trễ đẩy sự kiện < 3 giây.
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

    def is_user_online(self, user_id: int) -> bool:
        """Kiểm tra người dùng hiện có kết nối WebSocket online hay không."""
        return user_id in self.active_users and len(self.active_users[user_id]) > 0

    async def send_to_user(self, user_id: int, message: Dict[str, Any]) -> bool:
        """
        Gửi thông báo tới riêng một người dùng.
        Tự động đính kèm server_timestamp để đo đạc độ trễ (< 3 giây).
        Trả về True nếu gửi thành công tới ít nhất 1 client đang online.
        """
        if "server_timestamp" not in message:
            message["server_timestamp"] = datetime.now(timezone.utc).isoformat()

        if user_id in self.active_users:
            payload = json.dumps(message, ensure_ascii=False)
            dead_connections = []
            for connection in self.active_users[user_id]:
                try:
                    await connection.send_text(payload)
                except Exception:
                    dead_connections.append(connection)

            for dead in dead_connections:
                if dead in self.active_users[user_id]:
                    self.active_users[user_id].remove(dead)
            return True
        return False

    async def broadcast_to_role(self, role_code: str, message: Dict[str, Any]) -> int:
        """
        Gửi thông báo tới toàn bộ người dùng thuộc một vai trò (ví dụ: tất cả MANAGER).
        Trả về số lượng kết nối đã nhận thông báo thành công.
        """
        if "server_timestamp" not in message:
            message["server_timestamp"] = datetime.now(timezone.utc).isoformat()

        delivered_count = 0
        if role_code in self.role_rooms:
            payload = json.dumps(message, ensure_ascii=False)
            dead_connections = []
            for connection in list(self.role_rooms[role_code]):
                try:
                    await connection.send_text(payload)
                    delivered_count += 1
                except Exception:
                    dead_connections.append(connection)

            for dead in dead_connections:
                self.role_rooms[role_code].discard(dead)
        return delivered_count

manager = ConnectionManager()
