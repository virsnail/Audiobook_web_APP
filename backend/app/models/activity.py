import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from app.database import Base

class UserActivityLog(Base):
    """用户活动日志"""
    __tablename__ = "user_activity_logs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    action = Column(String(50), nullable=False, index=True)  # LOGIN, UPLOAD_TXT, READ_BOOK, etc.
    resource_id = Column(UUID(as_uuid=True), nullable=True)  # Optional related book/resource ID
    details = Column(JSONB, nullable=True)  # Extra details
    user_agent = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    
    # User relationship (optional)
    user = relationship("User", backref="activity_logs")
