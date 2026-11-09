from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, JSON
from sqlalchemy.orm import relationship
from app.core.database import Base

class Role(Base):
    __tablename__ = "roles"

    role_id = Column(Integer, primary_key=True, autoincrement=True)
    role_code = Column(String(30), unique=True, nullable=False, index=True)
    role_name = Column(String(100), nullable=False)
    permissions = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.now, nullable=False)

    users = relationship("User", back_populates="role")
