import os
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

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

@app.get("/", tags=["Health Check"])
def root_check():
    return {
        "app": settings.APP_NAME,
        "version": "1.1.0",
        "status": "online",
        "docs_url": "/docs",
        "redoc_url": "/redoc"
    }
