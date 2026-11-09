## 📌 Mô tả nhiệm vụ (Description)
<!-- Tóm tắt ngắn gọn mục tiêu của Pull Request này và tính năng/lỗi được giải quyết -->
- Thuộc Module: [MOD-01 / MOD-02 / MOD-03 / MOD-04 / MOD-05 / MOD-06 / MOD-07 / Chung]
- Mã yêu cầu SRS/SDD: [Ví dụ: FR-01, NFR-02, BR-04...]

## 🔄 Các thay đổi chính (Key Changes)
<!-- Liệt kê các thay đổi kỹ thuật cụ thể đã thực hiện -->
- [ ] Thêm mới / cập nhật API Endpoint: `METHOD /api/...`
- [ ] Xử lý logic nghiệp vụ tại tầng Service: `...`
- [ ] Thêm / cập nhật thực thể Model / Migration CSDL: `...`
- [ ] Bổ sung Schema DTO Validation: `...`

## 🧪 Kịch bản kiểm thử cục bộ (Testing Done)
<!-- Mô tả các bước đã test thành công trên máy local -->
1. Chạy server `uvicorn app.main:app --reload`
2. Truy cập Swagger UI `http://localhost:8000/docs`
3. Thao tác thử nghiệm API và kết quả:
   - [x] Case thành công: Trả về HTTP 200/201 kèm dữ liệu mong đợi
   - [x] Case thất bại (Validation / 401 Unauthorized / 403 Forbidden): Xử lý đúng lỗi

## 📸 Ảnh chụp minh họa / Swagger Logs (Optional)
<!-- Dán ảnh chụp màn hình Swagger UI hoặc Postman kết quả test -->

## ✅ Checklist trước khi yêu cầu Review
- [ ] Mã nguồn đã được tự kiểm tra (Self-review).
- [ ] Không có file thừa, file rác (`.env`, `__pycache__`, `venv`).
- [ ] Tên nhánh và commit tuân thủ quy ước trong `GIT_CONVENTION.md`.
- [ ] Code không có cảnh báo nghiêm trọng hoặc lỗi chưa xử lý.
