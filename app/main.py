import os
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse

from app.config import settings
from app.routers import (
    auth,
    users,
    posts,
    approvals,
    schedules,
    tracking,
    analytics,
    notifications,
    social,
)
from app.services.scheduler_worker import system_timer_worker

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Khởi chạy System Timer quét lịch ngầm
    timer_task = asyncio.create_task(system_timer_worker())
    # Đảm bảo thư mục uploads tồn tại
    os.makedirs(settings.LOCAL_UPLOAD_DIR, exist_ok=True)
    yield
    # Hủy background task khi tắt server
    timer_task.cancel()
    try:
        await timer_task
    except asyncio.CancelledError:
        pass

app = FastAPI(
    title=settings.APP_NAME,
    description="""
## Hệ thống Quản lý Truyền thông Đa kênh (Multi-Channel Communication Management System)
### Đơn vị thực hiện: Nhóm 7 RikkeiLab 2

Hệ thống cung cấp trọn bộ RESTful API phân tầng rõ ràng cho 7 Module nghiệp vụ cốt lõi:
* **MOD-01**: Xác thực & Phiên làm việc (Authentication & Session - JWT / HttpOnly Cookie / Brute-force lock)
* **MOD-02**: Quản lý Người dùng & Phân quyền vai trò (User & RBAC - Manager / Staff)
* **MOD-03**: Quản lý Nội dung & Tệp đa phương tiện (Content & Media Management)
* **MOD-04**: Quy trình Phê duyệt bài viết (Approval Workflow & State Machine)
* **MOD-05**: Lập lịch đăng bài & Content Calendar (Scheduling & System Timer)
* **MOD-06**: Theo dõi tiến độ & Xác nhận đăng bài (Progress Tracking)
* **MOD-07**: Thống kê & Báo cáo hiệu quả đa kênh (Analytics & Reporting)
    """,
    version="1.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

# Cấu hình CORS Middleware (cho phép Frontend React / Vue / HTML kết nối)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Phục vụ tệp tĩnh Media tải lên cục bộ
if os.path.exists(settings.LOCAL_UPLOAD_DIR):
    app.mount("/uploads", StaticFiles(directory=settings.LOCAL_UPLOAD_DIR), name="uploads")

# Đăng ký các Router nghiệp vụ
app.include_router(auth.router, prefix=settings.API_V1_PREFIX)
app.include_router(users.router, prefix=settings.API_V1_PREFIX)
app.include_router(posts.router, prefix=settings.API_V1_PREFIX)
app.include_router(approvals.router, prefix=settings.API_V1_PREFIX)
app.include_router(schedules.router, prefix=settings.API_V1_PREFIX)
app.include_router(tracking.router, prefix=settings.API_V1_PREFIX)
app.include_router(analytics.router, prefix=settings.API_V1_PREFIX)
app.include_router(notifications.router, prefix=settings.API_V1_PREFIX)
app.include_router(social.router, prefix=settings.API_V1_PREFIX)

@app.get("/", tags=["Health Check"])
def root_check():
    return {
        "app": settings.APP_NAME,
        "version": "1.1.0",
        "status": "online",
        "docs_url": "/docs",
        "redoc_url": "/redoc",
        "demo_notifications_url": "/demo/notifications"
    }

@app.get("/demo/notifications", response_class=HTMLResponse, tags=["Demo & Minh chứng"])
def demo_notifications_page():
    """Trang giao diện Demo Minh chứng WebSocket Real-time & Lưu trữ Offline (Task T06A664)."""
    template_path = os.path.join(os.path.dirname(__file__), "templates", "notification_demo.html")
    if os.path.exists(template_path):
        with open(template_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse(content="<h1>Template demo không tìm thấy</h1>", status_code=404)

@app.websocket("/ws/notifications")
async def root_websocket_notifications(websocket: WebSocket, token: str):
    """Cổng kết nối WebSocket tại root: ws://localhost:8000/ws/notifications?token=<JWT>"""
    from app.routers.notifications import handle_websocket_connection
    await handle_websocket_connection(websocket, token)
