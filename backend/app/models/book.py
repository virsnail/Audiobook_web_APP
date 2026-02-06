import uuid
from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Integer, Float, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


class Book(Base):
    """书籍表"""
    __tablename__ = "books"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(500), nullable=False)
    author = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)
    cover_path = Column(String(500), nullable=True)
    storage_path = Column(String(500), nullable=False)  # 相对于 media/books 的路径
    total_duration = Column(Integer, nullable=True)  # 总时长（秒）
    total_segments = Column(Integer, nullable=True)  # 总段落数
    is_public = Column(Boolean, default=False)  # 是否公开给所有用户
    book_type = Column(String(20), default="txt")  # "txt" 或 "epub" (方案2)
    epub_structure = Column(Text, nullable=True)  # EPUB 结构数据 (JSON 字符串，仅方案2使用)
    processing_status = Column(String(20), default="ready")  # "ready", "processing", "failed"
    processing_error = Column(Text, nullable=True)  # 失败时的错误信息
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 关系
    owner = relationship("User", back_populates="books")
    shares = relationship("BookShare", back_populates="book", cascade="all, delete-orphan")
    reading_progress = relationship("ReadingProgress", back_populates="book", cascade="all, delete-orphan")


class BookShare(Base):
    """书籍分享表"""
    __tablename__ = "book_shares"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    book_id = Column(UUID(as_uuid=True), ForeignKey("books.id", ondelete="CASCADE"), nullable=False, index=True)
    shared_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    shared_to = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=True)  # NULL 表示公开
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # 关系
    book = relationship("Book", back_populates="shares")


class ReadingProgress(Base):
    """阅读进度表"""
    __tablename__ = "reading_progress"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    book_id = Column(UUID(as_uuid=True), ForeignKey("books.id", ondelete="CASCADE"), nullable=False, index=True)
    current_position = Column(Float, default=0)  # 当前播放位置（秒）
    current_segment = Column(Integer, default=0)  # 当前段落索引
    playback_speed = Column(Float, default=1.0)  # 播放速度
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 关系
    user = relationship("User", back_populates="reading_progress")
    book = relationship("Book", back_populates="reading_progress")
