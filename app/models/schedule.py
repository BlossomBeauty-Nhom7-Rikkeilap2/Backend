from datetime import datetime
from sqlalchemy import Column, BigInteger, Integer, Boolean, DateTime, Enum, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base

class Schedule(Base):
    __tablename__ = "schedules"

    schedule_id = Column(BigInteger, primary_key=True, autoincrement=True)
    post_id = Column(BigInteger, ForeignKey("posts.post_id"), unique=True, nullable=False, index=True)
    scheduled_time = Column(DateTime, nullable=False, index=True)
    remind_before_minutes = Column(Integer, default=30, nullable=False)
    is_reminded_30m = Column(Boolean, default=False, nullable=False)
    is_reminded_10m = Column(Boolean, default=False, nullable=False)
    is_overdue_alerted = Column(Boolean, default=False, nullable=False)
    schedule_status = Column(Enum("ACTIVE", "COMPLETED", "CANCELLED"), default="ACTIVE", nullable=False, index=True)
    scheduled_by = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    created_at = Column(DateTime, default=datetime.now, nullable=False)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)

    post = relationship("Post", back_populates="schedule")
    creator = relationship("User", back_populates="schedules")
