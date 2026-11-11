from datetime import datetime
from sqlalchemy import Column, BigInteger, Integer, String, Text, DateTime, Enum, ForeignKey, JSON
from sqlalchemy.orm import relationship
from app.core.database import Base

class Post(Base):
    __tablename__ = "posts"

    post_id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    title = Column(String(255), nullable=False)
    caption = Column(Text, nullable=True)
    hashtags = Column(String(1000), nullable=True)
    platform_id = Column(Integer, ForeignKey("platforms.platform_id"), nullable=False)
    author_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    media_type = Column(Enum("IMAGE", "VIDEO"), default="IMAGE", nullable=False)
    media_files = Column(JSON, nullable=True)  # Danh sách URL tệp trên Cloud R2 / Local
    total_media_size_bytes = Column(BigInteger, default=0, nullable=False)
    planned_publish_time = Column(DateTime, nullable=True)
    status = Column(
        Enum("DRAFT", "PENDING_APPROVAL", "REVISION_REQUESTED", "REJECTED", "APPROVED", "SCHEDULED", "PUBLISHED"),
        default="DRAFT",
        nullable=False,
        index=True
    )
    published_url = Column(String(1000), nullable=True)
    published_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.now, nullable=False)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)
    deleted_at = Column(DateTime, nullable=True)  # Soft delete theo FR-06

    platform = relationship("Platform", back_populates="posts")
    author = relationship("User", back_populates="posts")
    approvals = relationship("Approval", back_populates="post", cascade="all, delete-orphan")
    schedule = relationship("Schedule", back_populates="post", uselist=False, cascade="all, delete-orphan")
    statistics = relationship("PostStatistic", back_populates="post", cascade="all, delete-orphan")
