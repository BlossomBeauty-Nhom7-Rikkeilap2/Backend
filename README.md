# HỆ THỐNG QUẢN LÝ TRUYỀN THÔNG ĐA KÊNH
## (MULTI-CHANNEL COMMUNICATION MANAGEMENT SYSTEM)

[![Python Version](https://img.shields.io/badge/Python-3.10%2B-blue.svg?logo=python)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110%2B-009688.svg?logo=fastapi)](https://fastapi.tiangolo.com/)
[![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.0%2B-red.svg?logo=sqlalchemy)](https://www.sqlalchemy.org/)
[![MySQL](https://img.shields.io/badge/MySQL-8.0%2B-orange.svg?logo=mysql)](https://www.mysql.com/)
[![Swagger](https://img.shields.io/badge/OpenAPI-3.0%20(Swagger%20UI)-green.svg?logo=swagger)](http://localhost:8000/docs)

> **Dự án Thực tập:** RikkeiLab 2  
> **Nhóm thực hiện:** Nhóm 7  
> **Khách hàng giả định:** Công ty Mỹ phẩm Hàn Quốc  
> **Tài liệu tham chiếu:** Tài liệu Thiết kế Hệ thống & Cơ sở Dữ liệu (System Design Document - SDD v1.1)

---

## 📖 MỤC LỤC
1. [Giới thiệu dự án](#1-giới-thiệu-dự-án)
2. [Cấu trúc thư mục Backend](#2-cấu-trúc-thư-mục-backend)
3. [Yêu cầu môi trường (Prerequisites)](#3-yêu-cầu-môi-trường-prerequisites)
4. [Hướng dẫn cài đặt & Chạy cục bộ (Local Setup)](#4-hướng-dẫn-cài-đặt--chạy-cục-bộ-local-setup)
   - [Cách 1: Chạy trực tiếp bằng Python Virtual Environment (Khuyên dùng)](#cách-1-chạy-trực-tiếp-bằng-python-virtualenv)
   - [Cách 2: Chạy tự động hóa với Docker Compose](#cách-2-chạy-nhanh-bằng-docker-compose)
5. [Tài liệu API & Swagger UI](#5-tài-liệu-api--swagger-ui)
6. [Tài khoản kiểm thử mặc định (Demo Credentials)](#6-tài-khoản-kiểm-thử-mặc-định)
7. [Quy ước Git Workflow & Pull Request (PR)](#7-quy-ước-git-workflow--pull-request-pr)
8. [Thành viên nhóm thực hiện](#8-thành-viên-nhóm-thực-hiện)

---

## 1. GIỚI THIỆU DỰ ÁN

Hệ thống Quản lý Truyền thông Đa kênh được xây dựng nhằm giải quyết bài toán quản trị tập trung chiến dịch truyền thông trên **3 nền tảng chính: Facebook Fanpage, Instagram Business và TikTok Official**. 

Hệ thống được thiết kế theo kiến trúc phân tầng chuẩn (**Layered & API-Driven Architecture**), đáp ứng đầy đủ 7 Module nghiệp vụ:
* **MOD-01: Authentication & Session**: Xác thực JWT kết hợp HttpOnly Cookie, bảo vệ Brute-force (khóa tài khoản 15 phút sau 5 lần nhập sai).
* **MOD-02: User & RBAC Management**: Phân quyền 2 vai trò cố định (`MANAGER` và `STAFF`), khóa tài khoản mềm (`DEACTIVATED`) bảo toàn lịch sử.
* **MOD-03: Content & Media Management**: Vòng đời bài viết (Draft $\rightarrow$ Pending $\rightarrow$ Approved $\rightarrow$ Scheduled $\rightarrow$ Published), kiểm tra kích thước ảnh $\le$ 10MB và video ngắn $\le$ 50MB.
* **MOD-04: Approval Workflow**: Quy trình phê duyệt nghiêm ngặt với giao dịch toàn vẹn ACID, tự động đồng bộ bài viết đạt trạng thái `Approved` lên Content Calendar.
* **MOD-05: Scheduling & Notification**: Quản trị Content Calendar trực quan, bộ định thời ngầm (System Timer) quét lịch mỗi phút và phát WebSocket nhắc nhở trước 30 phút, 10 phút.
* **MOD-06: Progress Tracking**: Theo dõi trạng thái tiến độ, xác nhận đã đăng bài thủ công kèm kiểm tra hợp lệ của URL nền tảng đích.
* **MOD-07: Analytics & Reporting**: Nhập liệu hoặc đồng bộ chỉ số đo lường (Reach, Views, Likes, Comments, Shares), cung cấp báo cáo tổng hợp dưới 5 giây.

---

## 2. CẤU TRÚC THƯ MỤC BACKEND

Mã nguồn được tổ chức theo mô hình **Phân tầng 3 lớp (Layered Architecture)**, tách biệt hoàn toàn giữa Router (Controller), Service (Nghiệp vụ), Model (CSDL) và Schema (DTO Validation):

```
Backend/
├── .github/
│   └── pull_request_template.md        # Biểu mẫu kiểm duyệt Pull Request chuẩn
├── app/
│   ├── __init__.py
│   ├── main.py                         # Khởi tạo ứng dụng FastAPI, CORS, Lifespan System Timer
│   ├── config.py                       # Quản lý biến môi trường qua Pydantic Settings
│   ├── core/                           # Các thành phần cốt lõi của hệ thống
│   │   ├── __init__.py
│   │   ├── database.py                 # Cấu hình SQLAlchemy Engine, SessionLocal, Connection Pool
│   │   ├── security.py                 # Băm mật khẩu Bcrypt, mã hóa/giải mã JWT Token
│   │   ├── dependencies.py             # AuthMiddleware, RoleGuard (MANAGER / STAFF)
│   │   └── websocket.py                # Real-time WebSocket Gateway quản lý rooms theo user & role
│   ├── models/                         # 8 Thực thể CSDL quan hệ (SQLAlchemy ORM) theo SDD Bảng 17
│   │   ├── __init__.py
│   │   ├── role.py                     # Bảng roles
│   │   ├── user.py                     # Bảng users
│   │   ├── platform.py                 # Bảng platforms (Facebook, Instagram, TikTok)
│   │   ├── post.py                     # Bảng posts (Quản lý trạng thái vòng đời bài viết)
│   │   ├── approval.py                 # Bảng approvals (Lịch sử quy trình phê duyệt)
│   │   ├── schedule.py                 # Bảng schedules (Lịch đăng bài Content Calendar)
│   │   ├── notification.py             # Bảng notifications (Thông báo thời gian thực)
│   │   └── post_statistic.py           # Bảng post_statistics (Chỉ số đo lường hiệu quả)
│   ├── schemas/                        # Pydantic Schemas (DTO) kiểm tra dữ liệu vào/ra
│   │   ├── __init__.py
│   │   ├── auth.py                     # DTO Đăng nhập, Token, Hồ sơ
│   │   ├── user.py                     # DTO Quản lý người dùng & phân quyền
│   │   ├── post.py                     # DTO Bài viết, bộ lọc tìm kiếm
│   │   ├── approval.py                 # DTO Gửi duyệt, Phê duyệt, Từ chối
│   │   ├── schedule.py                 # DTO Lịch Content Calendar
│   │   ├── notification.py             # DTO Thông báo
│   │   └── analytics.py                # DTO Chỉ số thống kê & Báo cáo
│   ├── routers/                        # Tầng API Controller (Định tuyến 7 Module)
│   │   ├── __init__.py
│   │   ├── auth.py                     # POST /api/auth/login, /logout, GET /me
│   │   ├── users.py                    # GET, POST, PUT, PATCH /api/users
│   │   ├── posts.py                    # CRUD /api/posts, POST /api/posts/upload-media
│   │   ├── approvals.py                # POST /submit, /approve, /reject, GET /approvals
│   │   ├── schedules.py                # GET /calendar, PUT /:postId
│   │   ├── tracking.py                 # PATCH /api/posts/:id/publish
│   │   ├── notifications.py            # GET /notifications, PATCH /:id/read, WS /ws/notifications
│   │   └── analytics.py                # POST /statistics, GET /dashboard, GET /export
│   ├── services/                       # Tầng Xử lý Nghiệp vụ (Business Logic Layer)
│   │   ├── __init__.py
│   │   ├── auth_service.py             # Logic xác thực, khóa chống Brute-force
│   │   ├── user_service.py             # Logic RBAC, khóa tài khoản mềm
│   │   ├── post_service.py             # Logic vòng đời bài viết, máy trạng thái State Machine
│   │   ├── approval_service.py         # Logic phê duyệt giao dịch ACID (AC-10)
│   │   ├── schedule_service.py         # Quản trị Content Calendar
│   │   ├── tracking_service.py         # Kiểm tra tên miền URL bài đăng thực tế
│   │   ├── analytics_service.py        # Tính toán tổng hợp chỉ số đa kênh
│   │   ├── media_service.py            # Kiểm tra định dạng & dung lượng Media (10MB/50MB)
│   │   └── scheduler_worker.py         # Background Task quét lịch gửi thông báo định kỳ
│   └── scripts/
│       ├── __init__.py
│       ├── schema.sql                  # Kịch bản SQL DDL & Seed Data chuẩn chỉnh từ SDD
│       └── init_db.py                  # Script Python tự động khởi tạo CSDL & Seed tài khoản
├── uploads/                            # Thư mục lưu trữ media cục bộ
├── .env.example                        # File cấu hình mẫu đầy đủ biến môi trường
├── .gitignore                          # Loại trừ các file rác, bytecode, venv và .env
├── GIT_CONVENTION.md                   # Quy ước Git Branch, Commit và PR Workflow chi tiết
├── requirements.txt                    # Danh sách các thư viện Python cần thiết
├── Dockerfile                          # Cấu hình đóng gói Docker container cho backend
├── docker-compose.yml                  # Khởi chạy một chạm cụm FastAPI + MySQL 8.0
└── README.md                           # Tài liệu tổng thể dự án và hướng dẫn chạy local
```

---

## 3. YÊU CẦU MÔI TRƯỜNG (PREREQUISITES)

Trước khi chạy dự án, máy tính của bạn cần cài đặt sẵn:
* **Python**: Phiên bản `3.10` trở lên (Khuyến nghị Python 3.11 hoặc 3.12).
* **MySQL Server**: Phiên bản `8.0` trở lên (hoặc MariaDB 10.6+).
* **Git**: Công cụ quản lý mã nguồn.
* *(Tùy chọn)* **Docker & Docker Compose**: Nếu bạn muốn chạy bằng container mà không cần cài MySQL trên máy.

---

## 4. HƯỚNG DẪN CÀI ĐẶT & CHẠY CỤC BỘ (LOCAL SETUP)

### Cách 1: Chạy trực tiếp bằng Python Virtualenv

#### Bước 1: Di chuyển vào thư mục Backend
```bash
cd Backend
```

#### Bước 2: Tạo và kích hoạt môi trường ảo (Virtual Environment)
* **Trên Windows (PowerShell / Command Prompt):**
  ```powershell
  python -m venv venv
  .\venv\Scripts\activate
  ```
* **Trên Linux / macOS:**
  ```bash
  python3 -m venv venv
  source venv/bin/activate
  ```

#### Bước 3: Cài đặt các thư viện phụ thuộc
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

#### Bước 4: Thiết lập file cấu hình môi trường `.env`
Sao chép từ file mẫu `.env.example`:
```bash
# Trên Windows
copy .env.example .env

# Trên Linux/macOS
cp .env.example .env
```
Mở file `.env` vừa tạo và chỉnh sửa thông tin kết nối MySQL tương ứng với máy của bạn:
```ini
DB_HOST="localhost"
DB_PORT=3306
DB_NAME="multichannel_cms"
DB_USER="root"
DB_PASSWORD="your_mysql_password"
DATABASE_URL="mysql+pymysql://root:your_mysql_password@localhost:3306/multichannel_cms?charset=utf8mb4"
```

#### Bước 5: Khởi tạo Cơ sở Dữ liệu & Dữ liệu mẫu (Seed Data)
Đảm bảo dịch vụ MySQL đang chạy, sau đó chạy script tự động:
```bash
python app/scripts/init_db.py
```
*(Hoặc bạn có thể mở công cụ quản lý như MySQL Workbench, DBeaver, phpMyAdmin và import trực tiếp tệp `app/scripts/schema.sql`).*

#### Bước 6: Khởi động máy chủ Backend FastAPI
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```
Server sẽ chạy tại địa chỉ: **`http://localhost:8000`**

---

### Cách 2: Chạy nhanh bằng Docker Compose

Nếu máy bạn đã cài sẵn Docker Desktop, bạn chỉ cần chạy **1 câu lệnh duy nhất** để khởi động toàn bộ cụm gồm cả MySQL 8.0 và FastAPI:

```bash
docker compose up -d --build
```
Hệ thống sẽ tự động:
1. Kéo image `mysql:8.0` và khởi chạy trên cổng `3306`.
2. Tự động nạp kịch bản `schema.sql` vào CSDL `multichannel_cms`.
3. Build container Backend Python và khởi chạy server tại cổng `8000`.

Xem logs hoạt động của hệ thống:
```bash
docker compose logs -f backend
```

Để dừng cụm container:
```bash
docker compose down
```

---

## 5. TÀI LIỆU API & SWAGGER UI

FastAPI tích hợp sẵn cơ chế sinh tài liệu tự động chuẩn **OpenAPI 3.0** (đáp ứng tiêu chí NFR-06 trong SDD). Sau khi khởi động server, bạn hãy mở trình duyệt và truy cập:

* **Swagger UI (Khuyên dùng để test trực tiếp):**  
  👉 **`http://localhost:8000/docs`**
* **ReDoc (Giao diện tài liệu chuyên sâu):**  
  👉 **`http://localhost:8000/redoc`**

### Hướng dẫn test nhanh trên Swagger UI:
1. Truy cập `http://localhost:8000/docs`.
2. Mở endpoint `POST /api/auth/login`, nhấn **Try it out** và đăng nhập với tài khoản Manager.
3. Sao chép chuỗi `access_token` từ kết quả trả về.
4. Cuộn lên đầu trang, nhấn nút **Authorize 🔓**, dán token vào ô `Value` và nhấn **Authorize**.
5. Bây giờ bạn có thể thử nghiệm toàn bộ các API quản lý người dùng, tạo bài, duyệt bài và xem báo cáo ngay trên trình duyệt!

---

## 6. TÀI KHOẢN KIỂM THỬ MẶC ĐỊNH

Khi chạy `init_db.py`, hệ thống đã khởi tạo sẵn 2 tài khoản thử nghiệm với mật khẩu băm Bcrypt:

| Vai trò | Username | Email | Mật khẩu mặc định | Quyền hạn chính |
| :--- | :--- | :--- | :--- | :--- |
| **Marketing Manager** | `manager` | `manager@rikkeilab.vn` | `Manager@123` | Toàn quyền quản trị, duyệt bài (`Approved`), từ chối (`Rejected`), xem báo cáo phân tích |
| **Marketing Staff** | `staff1` | `staff1@rikkeilab.vn` | `Staff@123` | Tạo bài nháp (`Draft`), gửi duyệt (`Submit`), xem lịch đăng và xác nhận đã đăng bài (`Published`) |

---

## 7. QUY ƯỚC GIT WORKFLOW & PULL REQUEST (PR)

Dự án áp dụng mô hình **Git Flow tinh gọn** và chuẩn **Conventional Commits**:

### 7.1. Cấu trúc nhánh chính
* **`main`**: Nhánh phát hành ổn định (Production). Không commit trực tiếp.
* **`develop`**: Nhánh tích hợp tính năng chung của cả nhóm.
* **`feature/<MOD-XX>-<ten-tinh-nang>`**: Nhánh làm việc riêng theo từng Module.

### 7.2. Quy tắc Commit:
```
<type>(<scope>): <mô tả ngắn>
```
*Ví dụ:*
* `feat(MOD-01): implement brute force login protection`
* `feat(MOD-04): add acid transaction for post approval`
* `fix(MOD-03): fix video size validation limit`

👉 Chi tiết về quy trình review, checklist trước khi merge PR xem tại: **[GIT_CONVENTION.md](./GIT_CONVENTION.md)**.

---

## 8. THÀNH VIÊN NHÓM THỰC HIỆN

**Dự án Thực tập Nhóm 7 - RikkeiLab 2:**

| STT | Họ và Tên | Vai trò chính | Nhiệm vụ đảm nhiệm |
| :---: | :--- | :---: | :--- |
| 1 | **Doãn Thị Minh Anh** | BA / Project Lead | Đối chiếu yêu cầu SRS, kiểm soát quy trình và phân rã Module |
| 2 | **Trịnh Trần Công Huy** | BA / Logic Designer | Thiết kế luồng xử lý nghiệp vụ, Máy trạng thái Post State Machine |
| 3 | **Nguyễn Phát Đạt** | BA / UI-UX | Thiết kế giao diện Frontend, điều hướng luồng màn hình |
| 4 | **Phan Hoàng Sơn** | Backend / Documentation | Thiết kế CSDL (ERD, DDL), xây dựng kiến trúc RESTful API FastAPI & chuẩn hóa SDD |

---

## 9. SẢN PHẨM NỘP BÀI (DELIVERABLES)
1. **Link Repository:** Được lưu trữ trên GitHub/GitLab của nhóm.
2. **Tài liệu README:** File `README.md` này cung cấp đầy đủ thông tin kiến trúc và cách vận hành.
