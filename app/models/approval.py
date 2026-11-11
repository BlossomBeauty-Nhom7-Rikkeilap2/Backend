from datetime import datetime
from sqlalchemy import Column, BigInteger, Integer, Text, DateTime, Enum, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base

class Approval(Base):
    __tablename__ = "approvals"

    approval_id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    post_id = Column(BigInteger, ForeignKey("posts.post_id"), nullable=False, index=True)
    actor_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    action = Column(
        Enum("SUBMITTED", "RESUBMITTED", "APPROVED", "REVISION_REQUESTED", "REJECTED"),
        nullable=False
    )
    comment = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.now, nullable=False)
    deleted_at = Column(DateTime, nullable=True)

    post = relationship("Post", back_populates="approvals")
    actor = relationship("User", back_populates="approvals")
