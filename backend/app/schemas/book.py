from pydantic import BaseModel, Json, Field
from uuid import UUID
from datetime import datetime
from typing import Optional, List


class BookBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    author: Optional[str] = Field(None, max_length=200)
    description: Optional[str] = Field(None, max_length=5000)


class BookCreate(BookBase):
    pass


class BookResponse(BookBase):
    id: UUID
    owner_id: UUID
    cover_path: Optional[str] = None
    total_duration: Optional[int] = None
    total_segments: Optional[int] = None
    is_public: bool
    created_at: datetime
    book_type: Optional[str] = "txt"
    epub_structure: Optional[Json] = None
    
    class Config:
        from_attributes = True


class BookListResponse(BaseModel):
    books: List[BookResponse]
    total: int


class BookProgressUpdate(BaseModel):
    current_position: float = Field(..., ge=0, le=360000, description="播放位置（秒），最大 100 小时")
    current_segment: int = Field(..., ge=0, le=1_000_000, description="当前 segment 索引")
    playback_speed: float = Field(1.0, ge=0.25, le=4.0, description="播放速度 0.25x-4x")


class BookProgressResponse(BaseModel):
    book_id: UUID
    current_position: float
    current_segment: int
    playback_speed: float
    updated_at: datetime
    
    class Config:
        from_attributes = True


class ShareCreate(BaseModel):
    book_id: UUID
    shared_to_email: Optional[str] = None  # None 表示公开分享
