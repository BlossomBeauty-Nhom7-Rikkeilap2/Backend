import os
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

class Settings(BaseSettings):
    # App Settings
    APP_NAME: str = "Multi-Channel Communication Management System"
    APP_ENV: str = "development"
    DEBUG: bool = True
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    API_V1_PREFIX: str = "/api"

    # Security & JWT
    SECRET_KEY: str = "rikkeilab_nhom7_multi_channel_cms_super_secret_jwt_key_2026"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # Database
    DB_HOST: str = "localhost"
    DB_PORT: int = 3306
    DB_NAME: str = "multichannel_cms"
    DB_USER: str = "root"
    DB_PASSWORD: str = "password"
    DATABASE_URL: str = Field(
        default="mysql+pymysql://root:password@localhost:3306/multichannel_cms?charset=utf8mb4"
    )

    # Media Storage (Cloudflare R2 / AWS S3)
    R2_ACCOUNT_ID: str = ""
    R2_ACCESS_KEY_ID: str = ""
    R2_SECRET_ACCESS_KEY: str = ""
    R2_BUCKET_NAME: str = "multichannel-cms-media"
    R2_PUBLIC_URL: str = "http://localhost:8000/uploads"
    LOCAL_UPLOAD_DIR: str = "uploads"

    # Social APIs
    FACEBOOK_APP_ID: str = ""
    FACEBOOK_APP_SECRET: str = ""
    FACEBOOK_GRAPH_VERSION: str = "v19.0"
    TIKTOK_APP_ID: str = ""
    TIKTOK_APP_SECRET: str = ""
    TIKTOK_CLIENT_KEY: str = ""
    TIKTOK_CLIENT_SECRET: str = ""

    @property
    def tiktok_key(self) -> str:
        return self.TIKTOK_CLIENT_KEY or self.TIKTOK_APP_ID

    @property
    def tiktok_secret(self) -> str:
        return self.TIKTOK_CLIENT_SECRET or self.TIKTOK_APP_SECRET

    # Scheduler & CORS
    SCHEDULER_INTERVAL_SECONDS: int = 60
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:5173,http://localhost:5500,http://127.0.0.1:3000,http://127.0.0.1:5173,http://127.0.0.1:5500"

    @property
    def cors_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    model_config = SettingsConfigDict(
        env_file=(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"), ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
