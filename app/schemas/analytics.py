from typing import Optional, Dict, Any, List
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict

class PostStatisticCreate(BaseModel):
    reach_count: int = Field(default=0, ge=0, description="Luot tiep can (so nguyen >= 0)")
    view_count: int = Field(default=0, ge=0, description="Luot xem (so nguyen >= 0)")
    like_count: int = Field(default=0, ge=0, description="Luot thich (so nguyen >= 0)")
    comment_count: int = Field(default=0, ge=0, description="Luot binh luan (so nguyen >= 0)")
    share_count: int = Field(default=0, ge=0, description="Luot chia se (so nguyen >= 0)")
    source_type: str = Field(default="MANUAL", pattern="^(MANUAL|API)$", description="Nguon cap nhat: MANUAL hoac API")
    milestone: Optional[str] = Field(default=None, pattern="^(24H|7D|30D|CUSTOM)$", description="Moc thoi gian thong ke")

class MockSyncRequest(BaseModel):
    milestone: Optional[str] = Field(default=None, pattern="^(24H|7D|30D|CUSTOM)$", description="Moc thoi gian can dong bo")
    reach_count: Optional[int] = Field(default=None, ge=0, description="Luot tiep can tuy chon (>= 0)")
    view_count: Optional[int] = Field(default=None, ge=0, description="Luot xem tuy chon (>= 0)")
    like_count: Optional[int] = Field(default=None, ge=0, description="Luot thich tuy chon (>= 0)")
    comment_count: Optional[int] = Field(default=None, ge=0, description="Luot binh luan tuy chon (>= 0)")
    share_count: Optional[int] = Field(default=None, ge=0, description="Luot chia se tuy chon (>= 0)")

class PostStatisticResponse(BaseModel):
    stat_id: int
    post_id: int
    reach_count: int
    view_count: int
    like_count: int
    comment_count: int
    share_count: int
    source_type: str
    milestone: Optional[str] = None
    updated_by: Optional[int] = None
    recorded_at: datetime

    model_config = ConfigDict(from_attributes=True)

class PostStatisticHistoryItem(BaseModel):
    stat_id: int
    post_id: int
    reach_count: int
    view_count: int
    like_count: int
    comment_count: int
    share_count: int
    total_engagement: int
    engagement_rate: float
    source_type: str
    milestone: Optional[str] = None
    recorded_at: datetime
    updated_by: Optional[int] = None
    updater_name: Optional[str] = None
    hours_since_published: Optional[float] = None

    model_config = ConfigDict(from_attributes=True)

class MilestonesSummary(BaseModel):
    m24h: Optional[PostStatisticHistoryItem] = None
    m7d: Optional[PostStatisticHistoryItem] = None
    m30d: Optional[PostStatisticHistoryItem] = None
    latest: Optional[PostStatisticHistoryItem] = None

class GrowthRateSummary(BaseModel):
    m24h_to_m7d: Optional[Dict[str, Any]] = None
    m7d_to_m30d: Optional[Dict[str, Any]] = None

class PostStatisticHistoryResponse(BaseModel):
    post_id: int
    title: str
    platform_name: str
    published_at: Optional[datetime] = None
    total_records: int
    history: List[PostStatisticHistoryItem]
    milestones: MilestonesSummary
    growth_rate: GrowthRateSummary

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
