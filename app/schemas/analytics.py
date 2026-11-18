from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, Field

class PostStatisticUpdate(BaseModel):
    reach_count: int = Field(0, ge=0, description="Số người tiếp cận")
    view_count: int = Field(0, ge=0, description="Lượt xem bài viết / video")
    like_count: int = Field(0, ge=0, description="Lượt thích / thả tim")
    comment_count: int = Field(0, ge=0, description="Lượt bình luận")
    share_count: int = Field(0, ge=0, description="Lượt chia sẻ")

class ChannelComparisonItem(BaseModel):
    platform_name: str
    color_hex: str
    total_posts: int
    total_reach: int
    total_views: int
    total_engagement: int
    engagement_share_percent: float = 0.0

class TopPostRankingItem(BaseModel):
    post_id: int
    post_code: str = ""
    title: str
    platform_name: str
    author_name: str = ""
    reach_count: int = 0
    view_count: int
    total_engagement: int
    engagement_rate: float = 0.0
    published_url: Optional[str] = None
    published_at: Optional[datetime] = None

class MonthlyTrendItem(BaseModel):
    month_label: str
    published_posts: int
    total_reach: int
    total_engagement: int

class AnalyticsDashboardResponse(BaseModel):
    total_published_posts: int
    total_reach: int
    total_views: int
    total_engagement: int
    engagement_rate: float
    first_time_approval_rate: float
    channel_comparison: List[ChannelComparisonItem]
    top_posts: List[TopPostRankingItem]
    monthly_trend: List[MonthlyTrendItem] = []
    empty_state_message: Optional[str] = None
    response_time_ms: float = 0.0

# Aliases for backward compatibility in app.schemas.__init__
PostStatisticCreate = PostStatisticUpdate
PostStatisticResponse = PostStatisticUpdate
DashboardResponse = AnalyticsDashboardResponse

