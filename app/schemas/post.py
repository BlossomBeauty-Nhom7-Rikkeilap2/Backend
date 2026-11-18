from typing import Optional, List, Any
from datetime import datetime, date
from pydantic import BaseModel, Field

class PostCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    caption: Optional[str] = None
    hashtags: Optional[str] = None
    platform_id: int
    media_type: str = Field(default="IMAGE", pattern="^(IMAGE|VIDEO)$")
    media_files: Optional[List[str]] = None
    total_media_size_bytes: Optional[int] = 0
    planned_publish_time: Optional[datetime] = None

class PostUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    caption: Optional[str] = None
    hashtags: Optional[str] = None
    platform_id: Optional[int] = None
    media_type: Optional[str] = Field(None, pattern="^(IMAGE|VIDEO)$")
    media_files: Optional[List[str]] = None
    total_media_size_bytes: Optional[int] = None
    planned_publish_time: Optional[datetime] = None

class PostResponse(BaseModel):
    post_id: int
    title: str
    caption: Optional[str] = None
    hashtags: Optional[str] = None
    platform_id: int
    author_id: int
    media_type: str
    media_files: Optional[Any] = None
    total_media_size_bytes: int
    planned_publish_time: Optional[datetime] = None
    status: str
    published_url: Optional[str] = None
    published_at: Optional[datetime] = None
    deleted_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class PostFilterParams(BaseModel):
    platform_id: Optional[int] = None
    platform: Optional[str] = None
    status: Optional[str] = None
    author_id: Optional[int] = None
    author_name: Optional[str] = None
    search: Optional[str] = None
    planned_date: Optional[date] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    include_deleted: bool = False
    page: int = 1
    page_size: int = 10

class PaginatedPostResponse(BaseModel):
    items: List[PostResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
    response_time_ms: float
