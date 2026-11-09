# QUY ƯỚC QUẢN LÝ MÃ NGUỒN VÀ QUY TRÌNH GIT (GIT CONVENTIONS & WORKFLOW)
**Dự án:** Hệ thống Quản lý Truyền thông Đa kênh (Multi-Channel Communication Management System)  
**Đơn vị thực hiện:** Nhóm 7 RikkeiLab 2  

---

## 1. MÔ HÌNH NHÁNH (BRANCHING STRATEGY)

Dự án áp dụng mô hình **Git Flow tinh gọn (Simplified Git Flow)** để đảm bảo sự ổn định của sản phẩm và khả năng cộng tác nhóm mượt mà.

```
(main)        ───●──────────────────────────●────── (Production Release)
                 \                         /
(develop)     ────●──────●─────────●──────●──────── (Integration)
                   \    /           \    /
(feature/MOD)       └──●─────────────└──●          (Module Development)
```

### 1.1. Các nhánh cố định (Permanent Branches)
* **`main`**:
  * Nhánh lưu trữ mã nguồn môi trường Production (đã kiểm thử, sẵn sàng nghiệm thu/demo).
  * **Quy tắc nghiêm ngặt**: Tuyệt đối **KHÔNG commit trực tiếp** lên nhánh `main`. Mọi thay đổi bắt buộc phải thông qua Pull Request (PR) được duyệt từ nhánh `develop` hoặc `hotfix`.
* **`develop`**:
  * Nhánh tích hợp chính của nhóm.
  * Toàn bộ các tính năng sau khi hoàn thành và vượt qua kiểm thử cục bộ sẽ được tạo PR vào nhánh này.

---

### 1.2. Các nhánh tạm thời (Supporting Branches)

| Loại nhánh | Mục đích | Nguồn tạo nhánh | Đích merge vào | Định dạng tên nhánh |
| :--- | :--- | :--- | :--- | :--- |
| **`feature`** | Phát triển tính năng mới theo từng Module | `develop` | `develop` | `feature/<MOD-XX>-<ten-ngan-gon>` |
| **`bugfix`** | Sửa lỗi phát hiện trong quá trình phát triển/sprint | `develop` | `develop` | `bugfix/<issue-id>-<ten-loi>` |
| **`hotfix`** | Sửa lỗi nghiêm trọng phát sinh trên `main` (Production) | `main` | `main` & `develop` | `hotfix/<ten-loi-khan-cap>` |
| **`docs`** | Cập nhật tài liệu, README, sơ đồ | `develop` | `develop` | `docs/<noi-dung-tai-lieu>` |

#### Ví dụ đặt tên nhánh:
* `feature/MOD-01-auth-login`
* `feature/MOD-02-user-management`
* `feature/MOD-03-post-crud`
* `feature/MOD-04-approval-workflow`
* `feature/MOD-05-schedule-calendar`
* `feature/MOD-06-tracking-publish`
* `feature/MOD-07-analytics-export`
* `bugfix/issue-14-fix-jwt-expiration`
* `docs/update-readme-local-guide`

---

## 2. QUY ƯỚC ĐẶT THÔNG ĐIỆP COMMIT (CONVENTIONAL COMMITS)

Mỗi commit phải đại diện cho một đơn vị công việc hoàn chỉnh và có ý nghĩa rõ ràng. Áp dụng chuẩn **Conventional Commits v1.0.0**:

### 2.1. Cấu trúc cú pháp
```
<type>(<scope>): <mô tả ngắn gọn bằng tiếng Anh hoặc tiếng Việt>

[Tùy chọn: Thân commit mô tả chi tiết lý do và sự thay đổi]

[Tùy chọn: Footer tham chiếu ID nhiệm vụ, ví dụ: Closes #123]
```

### 2.2. Danh sách các `type` được phép:
* **`feat`**: Tính năng mới (ví dụ: `feat(MOD-01): implement brute force login protection`)
* **`fix`**: Sửa lỗi mã nguồn (ví dụ: `fix(MOD-03): handle invalid video mime types`)
* **`docs`**: Thay đổi tài liệu, ghi chú, markdown (ví dụ: `docs(readme): add docker setup instructions`)
* **`style`**: Định dạng code, dấu cách, thụt dòng, không đổi logic (ví dụ: `style(core): format code with black`)
* **`refactor`**: Tái cấu trúc code mà không thêm tính năng hay sửa lỗi (ví dụ: `refactor(services): optimize approval transaction flow`)
* **`perf`**: Cải tiến hiệu năng truy vấn, xử lý (ví dụ: `perf(analytics): add database composite indexes`)
* **`test`**: Bổ sung hoặc chỉnh sửa unit test / integration test (ví dụ: `test(auth): add test cases for failed login attempts`)
* **`chore`**: Công việc phụ trợ: cập nhật dependencies, cấu hình CI/CD, docker (ví dụ: `chore(deps): update fastapi and pydantic`)

---

## 3. QUY TRÌNH PULL REQUEST (PR WORKFLOW) & CODE REVIEW

### 3.1. Các bước trước khi tạo PR
1. Đồng bộ mã nguồn mới nhất từ nhánh đích:
   ```bash
   git checkout develop
   git pull origin develop
   git checkout feature/MOD-XX-...
   git merge develop
   ```
2. Kiểm tra lỗi cú pháp và chạy thử cục bộ (chắc chắn không bị lỗi vặt):
   ```bash
   uvicorn app.main:app --reload
   ```
3. Đảm bảo không commit các tệp rác, file `.env` cá nhân, thư mục `venv/` hoặc `__pycache__/`.

### 3.2. Tiêu chuẩn của một Pull Request
* **Tiêu đề PR**: Tuân theo format `[MOD-XX] <Mô tả ngắn gọn công việc>`  
  *Ví dụ:* `[MOD-01] Xây dựng API Đăng nhập và khóa tài khoản khi nhập sai 5 lần`
* **Nội dung PR**: Điền đầy đủ theo biểu mẫu tại `.github/pull_request_template.md`.
* **Người duyệt (Reviewer)**: Phải gán ít nhất **1 thành viên trong nhóm** (hoặc Tech Lead) review.
* **Điều kiện Merge**:
  * Tối thiểu 1 Reviewer duyệt (`Approved`).
  * Tất cả các cuộc thảo luận (Comments/Change Requests) đã được giải quyết (Resolved).
  * Phương thức merge ưu tiên: **Squash and merge** hoặc **Rebase and merge** để giữ cây lịch sử nhánh `develop` gọn gàng.

---

## 4. QUY TẮC BẢO MẬT KHI LÀM VIỆC VỚI GIT

1. **Tuyệt đối không commit tệp `.env` chứa mật khẩu thực tế hoặc Secret Key lên GitHub/GitLab.**
2. Chỉ commit file `.env.example` với các giá trị mẫu/placeholder.
3. Nếu lỡ commit thông tin nhạy cảm (API Key, Mật khẩu Database), phải lập tức liên hệ nhóm để thu hồi key và xóa lịch sử git commit (qua `git filter-branch` hoặc BFG Repo-Cleaner).
