import os
import uuid
from typing import Tuple
from fastapi import UploadFile, HTTPException, status
from app.config import settings

class MediaUploadService:
    """
    Xử lý kiểm tra dung lượng và định dạng tệp Media tải lên (SDD 3.2.3 & Mục 8.2 SRS).
    - Ảnh: jpeg, png, webp <= 10MB
    - Video: mp4, quicktime <= 50MB
    """
    MAX_IMAGE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB
    MAX_VIDEO_SIZE_BYTES = 50 * 1024 * 1024  # 50 MB

    ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
    ALLOWED_VIDEO_TYPES = {"video/mp4", "video/quicktime"}

    @classmethod
    async def validate_and_save(cls, file: UploadFile) -> Tuple[str, int, str]:
        """
        Kiểm tra và lưu file vào thư mục cục bộ (hoặc Cloud R2).
        Trả về: (file_url, file_size_bytes, media_type)
        """
        content_type = file.content_type
        if content_type in cls.ALLOWED_IMAGE_TYPES:
            media_type = "IMAGE"
            max_limit = cls.MAX_IMAGE_SIZE_BYTES
        elif content_type in cls.ALLOWED_VIDEO_TYPES:
            media_type = "VIDEO"
            max_limit = cls.MAX_VIDEO_SIZE_BYTES
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Định dạng tệp không được hỗ trợ ({content_type}). Chỉ chấp nhận JPG/PNG/WEBP hoặc MP4/MOV."
            )

        contents = await file.read()
        file_size = len(contents)

        if file_size > max_limit:
            limit_mb = max_limit // (1024 * 1024)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Dung lượng tệp vượt quá giới hạn cho phép ({limit_mb}MB)."
            )

        # Lưu tệp cục bộ (uploads/)
        os.makedirs(settings.LOCAL_UPLOAD_DIR, exist_ok=True)
        ext = os.path.splitext(file.filename)[1]
        unique_filename = f"{uuid.uuid4().hex}{ext}"
        local_path = os.path.join(settings.LOCAL_UPLOAD_DIR, unique_filename)

        with open(local_path, "wb") as f:
            f.write(contents)

        file_url = f"{settings.R2_PUBLIC_URL}/{unique_filename}"
        return file_url, file_size, media_type
