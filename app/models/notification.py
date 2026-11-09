from datetime import datetime
from sqlalchemy import Column, BigInteger, Integer, String, Boolean, DateTime, Enum, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base

class Notification(Base):
    __tablename__ = "notifications"

    notification_id = Column(BigInteger, primary_key=True, autoincrement=True)
    recipient_id = Column(Integer, ForeignKey("users.user_id"), nullable=False, index=True)
    post_id = Column(BigInteger, ForeignKey("posts.post_id"), nullable=True)
    notification_type = Column(
        Enum("APPROVAL_REQUEST", "POST_APPROVED", "POST_REJECTED", "SCHEDULE_REMINDER", "OVERDUE_ALERT"),
        nullable=False
    )
    title = Column(String(255), nullable=False)
    message = Column(String(1000), nullable=False)
    is_read = Column(Boolean, default=False, nullable=False, index=True)
    read_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.now, nullable=False, index=True)

    recipient = relationship("User", back_populates="notifications")
    post = relationship("Post")
