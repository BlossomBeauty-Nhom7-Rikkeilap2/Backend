from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Enum, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base

class User(Base):
    __tablename__ = "users"

    user_id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(150), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(100), nullable=False)
    role_id = Column(Integer, ForeignKey("roles.role_id"), nullable=False)
    avatar_url = Column(String(500), nullable=True)
    status = Column(Enum("ACTIVE", "LOCKED", "DEACTIVATED"), default="ACTIVE", nullable=False)
    failed_login_attempts = Column(Integer, default=0, nullable=False)
    locked_until = Column(DateTime, nullable=True)
    last_login_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.now, nullable=False)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)

    role = relationship("Role", back_populates="users")
    posts = relationship("Post", back_populates="author")
    approvals = relationship("Approval", back_populates="actor")
    schedules = relationship("Schedule", back_populates="creator")
    notifications = relationship("Notification", back_populates="recipient")
