import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


class Tag(Base):
    """标签表 - 每个用户拥有自己的标签命名空间"""
    __tablename__ = "tags"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False, index=True)
    owner_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # 关系
    owner = relationship("User", backref="tags")
    book_tags = relationship("BookTag", back_populates="tag", cascade="all, delete-orphan")

    # 同一用户不能有同名标签
    __table_args__ = (
        UniqueConstraint('name', 'owner_id', name='uq_tag_name_owner'),
    )


class BookTag(Base):
    """书籍-标签关联表"""
    __tablename__ = "book_tags"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    book_id = Column(UUID(as_uuid=True), ForeignKey("books.id", ondelete="CASCADE"), nullable=False, index=True)
    tag_id = Column(UUID(as_uuid=True), ForeignKey("tags.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # 关系
    tag = relationship("Tag", back_populates="book_tags")
    book = relationship("Book", backref="book_tags")

    # 同一本书不能重复添加同一个标签
    __table_args__ = (
        UniqueConstraint('book_id', 'tag_id', name='uq_book_tag'),
    )
