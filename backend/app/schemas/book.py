from pydantic import BaseModel
from uuid import UUID
from datetime import datetime
from typing import Optional, List


class BookBase(BaseModel):
    title: str
    author: Optional[str] = None
    description: Optional[str] = None


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
    
    class Config:
        from_attributes = True


class BookListResponse(BaseModel):
    books: List[BookResponse]
    total: int


class BookProgressUpdate(BaseModel):
    current_position: float
    current_segment: int
    playback_speed: float = 1.0


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
