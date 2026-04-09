from pydantic import BaseModel, Field
from uuid import UUID
from datetime import datetime
from typing import Optional, List


class TagCreate(BaseModel):
    """创建标签"""
    name: str = Field(..., min_length=1, max_length=100, description="标签名称")


class TagUpdate(BaseModel):
    """修改标签名称"""
    name: str = Field(..., min_length=1, max_length=100, description="新标签名称")


class TagResponse(BaseModel):
    """标签响应"""
    id: UUID
    name: str
    owner_id: UUID
    book_count: int = 0
    created_at: datetime

    class Config:
        from_attributes = True


class BookTagsUpdate(BaseModel):
    """更新书籍的标签列表（全量替换）"""
    tag_ids: List[UUID] = Field(default_factory=list, description="标签 ID 列表")
