import os
import uuid
import logging
from typing import Tuple
from fastapi import UploadFile, HTTPException, status
from app.config import settings

logger = logging.getLogger(__name__)

class MediaUploadService:
    """
    Xử lý kiểm tra dung lượng và định dạng tệp Media tải lên (SDD 3.2.3 & Mục 8.2 SRS).
    - Ảnh: jpeg, png, webp <= 10MB
    - Video: mp4, quicktime <= 50MB
    - Hỗ trợ lưu trữ trực tiếp lên Cloudflare R2 (S3-compatible) hoặc fallback cục bộ uploads/.
    """
    MAX_IMAGE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB
    MAX_VIDEO_SIZE_BYTES = 50 * 1024 * 1024  # 50 MB

    ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
    ALLOWED_VIDEO_TYPES = {"video/mp4", "video/quicktime"}

    @classmethod
    def get_s3_client(cls):
        """Khởi tạo S3 Client cho Cloudflare R2 nếu có đủ thông tin xác thực."""
        if not (settings.R2_ACCOUNT_ID and settings.R2_ACCESS_KEY_ID and settings.R2_SECRET_ACCESS_KEY):
            return None
        try:
            import boto3
            from botocore.config import Config
            endpoint_url = f"https://{settings.R2_ACCOUNT_ID}.r2.cloudflarestorage.com"
            return boto3.client(
                service_name="s3",
                endpoint_url=endpoint_url,
                aws_access_key_id=settings.R2_ACCESS_KEY_ID,
                aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
                region_name="auto",
                config=Config(signature_version="s3v4")
            )
        except Exception as e:
            logger.warning(f"[MediaService] Không thể khởi tạo S3 client cho Cloudflare R2: {e}")
            return None

    @classmethod
    async def validate_and_save(cls, file: UploadFile) -> Tuple[str, int, str]:
        """
        Kiểm tra và lưu file:
        - Đẩy lên Cloudflare R2 nếu đã cấu hình API Token.
        - Tự động fallback lưu thư mục uploads/ cục bộ nếu chưa có Token R2.
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

        ext = os.path.splitext(file.filename)[1]
        unique_filename = f"{uuid.uuid4().hex}{ext}"

        # 1. Thử đẩy lên Cloudflare R2 nếu có client
        s3_client = cls.get_s3_client()
        if s3_client and settings.R2_BUCKET_NAME:
            try:
                s3_client.put_object(
                    Bucket=settings.R2_BUCKET_NAME,
                    Key=unique_filename,
                    Body=contents,
                    ContentType=content_type
                )
                public_base = settings.R2_PUBLIC_URL.rstrip("/")
                file_url = f"{public_base}/{unique_filename}"
                logger.info(f"[MediaService] Đã upload lên Cloudflare R2 thành công: {file_url}")
                return file_url, file_size, media_type
            except Exception as e:
                logger.error(f"[MediaService] Upload lên R2 thất bại, fallback lưu cục bộ: {e}")

        # 2. Fallback: Lưu tệp cục bộ (uploads/)
        os.makedirs(settings.LOCAL_UPLOAD_DIR, exist_ok=True)
        local_path = os.path.join(settings.LOCAL_UPLOAD_DIR, unique_filename)

        with open(local_path, "wb") as f:
            f.write(contents)

        if settings.R2_PUBLIC_URL and settings.R2_PUBLIC_URL.startswith("http"):
            file_url = f"{settings.R2_PUBLIC_URL.rstrip('/')}/{unique_filename}"
        else:
            file_url = f"/uploads/{unique_filename}"

        return file_url, file_size, media_type
