from sqlalchemy import Column, Integer, String, Boolean, JSON
from sqlalchemy.orm import relationship
from app.core.database import Base

class Platform(Base):
    __tablename__ = "platforms"

    platform_id = Column(Integer, primary_key=True, autoincrement=True)
    platform_code = Column(String(30), unique=True, nullable=False, index=True)
    platform_name = Column(String(100), nullable=False)
    channel_url = Column(String(500), nullable=True)
    color_hex = Column(String(10), default="#1877F2", nullable=False)
    oauth_config = Column(JSON, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)

    posts = relationship("Post", back_populates="platform")
