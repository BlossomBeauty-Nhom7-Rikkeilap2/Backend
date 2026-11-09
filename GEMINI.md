# WORKSPACE RULES & GIT TEAMWORK PROTOCOL
# Hệ thống Quản lý Truyền thông Đa kênh (Multi-Channel CMS) - Nhóm 7 RikkeiLab 2

## QUY TẮC BẮT BUỘC KHI LÀM VIỆC VỚI GIT & MÃ NGUỒN (MANDATORY AGENT INSTRUCTIONS)

Mỗi khi người dùng yêu cầu chỉnh sửa mã nguồn, bổ sung tính năng, hoặc sửa lỗi trong workspace này, AI Assistant BẮT BUỘC phải tuân thủ nghiêm ngặt quy trình 5 bước sau:

### 1. TUYỆT ĐỐI KHÔNG COMMIT LÊN NHÁNH `main`
- Nhánh `main` là nhánh Production/Demo của nhóm, chỉ nhận code thông qua Release PR từ nhánh `develop`.
- Không bao giờ chạy `git commit` hoặc `git push` trực tiếp trên nhánh `main`.

### 2. LUÔN BẮT ĐẦU TỪ `develop` MỚI NHẤT
- Trước khi thực hiện bất kỳ thay đổi nào, luôn kiểm tra và kéo mã nguồn mới nhất:
  ```bash
  git checkout develop
  git pull origin develop
  ```

### 3. TỰ ĐỘNG TẠO NHÁNH TÍNH NĂNG (FEATURE BRANCHING)
- Tạo nhánh riêng biệt từ `develop` theo đúng Module nghiệp vụ SRS/SDD:
  - Tính năng mới: `git checkout -b feature/MOD-XX-<ten-tinh-nang-ngan-gon>`
    - Ví dụ: `feature/MOD-01-auth-login`, `feature/MOD-03-media-upload`, `feature/MOD-04-approval-flow`
  - Sửa lỗi: `git checkout -b bugfix/issue-<ma-loi>-<ten-loi>`

### 4. TỰ KIỂM THỬ TRƯỚC KHI COMMIT (PRE-COMMIT VERIFICATION)
- Kiểm tra lỗi cú pháp: `python -m compileall app`
- Kiểm tra OpenAPI schema & FastAPI routes nếu có thêm endpoint mới.
- Kiểm tra `git status`: Đảm bảo không theo dõi file rác, file log, thư mục `__pycache__` hay file `.env` cá nhân.
- Commit thông điệp theo chuẩn Conventional Commits:
  - Format: `<type>(<scope>): <mô tả>`
  - Types: `feat`, `fix`, `docs`, `refactor`, `perf`, `test`, `chore`.

### 5. ĐỒNG BỘ VÀ ĐẨY LÊN NHÁNH FEATURE (PUSH & PULL REQUEST)
- Đồng bộ nhánh `develop` để giải quyết xung đột (nếu có): `git merge develop`
- Đẩy nhánh lên GitHub: `git push -u origin feature/MOD-XX-...`
- Cung cấp đường link tạo Pull Request vào nhánh `develop` để nhóm review và merge.
