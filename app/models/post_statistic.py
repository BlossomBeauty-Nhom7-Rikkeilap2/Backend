from datetime import datetime
from sqlalchemy import Column, BigInteger, Integer, DateTime, Enum, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base

class PostStatistic(Base):
    __tablename__ = "post_statistics"

    stat_id = Column(BigInteger, primary_key=True, autoincrement=True)
    post_id = Column(BigInteger, ForeignKey("posts.post_id"), nullable=False, index=True)
    reach_count = Column(Integer, default=0, nullable=False)
    view_count = Column(Integer, default=0, nullable=False)
    like_count = Column(Integer, default=0, nullable=False)
    comment_count = Column(Integer, default=0, nullable=False)
    share_count = Column(Integer, default=0, nullable=False)
    source_type = Column(Enum("MANUAL", "API"), default="MANUAL", nullable=False)
    updated_by = Column(Integer, ForeignKey("users.user_id"), nullable=True)
    recorded_at = Column(DateTime, default=datetime.now, nullable=False, index=True)

    post = relationship("Post", back_populates="statistics")
    updater = relationship("User")
