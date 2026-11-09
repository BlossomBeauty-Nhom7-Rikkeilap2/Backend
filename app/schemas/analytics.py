from typing import Optional, Dict, Any, List
from datetime import datetime
from pydantic import BaseModel, Field

class PostStatisticCreate(BaseModel):
    reach_count: int = Field(default=0, ge=0)
    view_count: int = Field(default=0, ge=0)
    like_count: int = Field(default=0, ge=0)
    comment_count: int = Field(default=0, ge=0)
    share_count: int = Field(default=0, ge=0)
    source_type: str = Field(default="MANUAL", pattern="^(MANUAL|API)$")

class PostStatisticResponse(BaseModel):
    stat_id: int
    post_id: int
    reach_count: int
    view_count: int
    like_count: int
    comment_count: int
    share_count: int
    source_type: str
    updated_by: Optional[int] = None
    recorded_at: datetime

    class Config:
        from_attributes = True

class PlatformSummary(BaseModel):
    platform_name: str
    total_posts: int
    total_reach: int
    total_views: int
    total_likes: int
    total_comments: int
    total_shares: int

class DashboardResponse(BaseModel):
    total_published_posts: int
    total_reach: int
    total_views: int
    total_engagement: int
    platforms: List[PlatformSummary]
