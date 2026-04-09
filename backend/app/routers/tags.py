"""
标签管理 API
"""
import uuid
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, delete

from app.database import get_db
from app.models.user import User
from app.models.tag import Tag, BookTag
from app.schemas.tag import TagCreate, TagUpdate, TagResponse
from app.utils.deps import get_current_user

router = APIRouter()


@router.get("", response_model=List[TagResponse], summary="获取当前用户的所有标签")
async def list_tags(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    获取当前用户的所有标签（含关联 book 数量）。
    同时返回被分享给当前用户的书籍所属的标签（来自其他用户）。
    """
    # 1. 自己创建的标签
    own_tags_stmt = (
        select(Tag, func.count(BookTag.id).label("book_count"))
        .outerjoin(BookTag, Tag.id == BookTag.tag_id)
        .where(Tag.owner_id == current_user.id)
        .group_by(Tag.id)
        .order_by(Tag.name)
    )
    own_result = await db.execute(own_tags_stmt)
    own_rows = own_result.all()

    # 2. 从被分享 / 公开可见的书上收集"他人的标签"
    from app.models.book import Book, BookShare
    from sqlalchemy import or_

    shared_book_ids_stmt = (
        select(Book.id).where(
            or_(
                # 被分享给我的
                Book.id.in_(
                    select(BookShare.book_id).where(BookShare.shared_to == current_user.id)
                ),
                # 公开的 (且不是自己的)
                (Book.is_public == True) & (Book.owner_id != current_user.id),
            )
        )
    )
    shared_tags_stmt = (
        select(Tag, func.count(BookTag.id).label("book_count"))
        .join(BookTag, Tag.id == BookTag.tag_id)
        .where(
            BookTag.book_id.in_(shared_book_ids_stmt),
            Tag.owner_id != current_user.id,
        )
        .group_by(Tag.id)
        .order_by(Tag.name)
    )
    shared_result = await db.execute(shared_tags_stmt)
    shared_rows = shared_result.all()

    # 合并去重 (key=tag.id)
    seen = set()
    tags = []
    for tag, count in list(own_rows) + list(shared_rows):
        if tag.id in seen:
            continue
        seen.add(tag.id)
        tags.append(
            TagResponse(
                id=tag.id,
                name=tag.name,
                owner_id=tag.owner_id,
                book_count=count,
                created_at=tag.created_at,
            )
        )

    return tags


@router.post("", response_model=TagResponse, status_code=status.HTTP_201_CREATED, summary="创建新标签")
async def create_tag(
    body: TagCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """创建新标签（同名标签在同一用户下不允许重复）"""
    name = body.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="标签名称不能为空")

    # 检查同名
    existing = await db.execute(
        select(Tag).where(Tag.owner_id == current_user.id, Tag.name == name)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="该标签已存在 Tag already exists")

    tag = Tag(name=name, owner_id=current_user.id)
    db.add(tag)
    await db.commit()
    await db.refresh(tag)

    return TagResponse(
        id=tag.id,
        name=tag.name,
        owner_id=tag.owner_id,
        book_count=0,
        created_at=tag.created_at,
    )


@router.patch("/{tag_id}", response_model=TagResponse, summary="修改标签名称")
async def update_tag(
    tag_id: uuid.UUID,
    body: TagUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """修改标签名称（仅标签所有者）"""
    result = await db.execute(select(Tag).where(Tag.id == tag_id))
    tag = result.scalar_one_or_none()

    if not tag:
        raise HTTPException(status_code=404, detail="标签不存在")
    if tag.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="只有标签所有者可以修改")

    new_name = body.name.strip()
    if not new_name:
        raise HTTPException(status_code=400, detail="标签名称不能为空")

    # 检查新名称是否与用户的其他标签重复
    dup = await db.execute(
        select(Tag).where(
            Tag.owner_id == current_user.id,
            Tag.name == new_name,
            Tag.id != tag_id,
        )
    )
    if dup.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="该标签名已存在")

    tag.name = new_name
    await db.commit()
    await db.refresh(tag)

    # 获取 book_count
    count_result = await db.execute(
        select(func.count(BookTag.id)).where(BookTag.tag_id == tag_id)
    )
    book_count = count_result.scalar() or 0

    return TagResponse(
        id=tag.id,
        name=tag.name,
        owner_id=tag.owner_id,
        book_count=book_count,
        created_at=tag.created_at,
    )


@router.delete("/{tag_id}", status_code=status.HTTP_204_NO_CONTENT, summary="删除标签")
async def delete_tag(
    tag_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """删除标签（同时删除所有关联关系，仅标签所有者）"""
    result = await db.execute(select(Tag).where(Tag.id == tag_id))
    tag = result.scalar_one_or_none()

    if not tag:
        raise HTTPException(status_code=404, detail="标签不存在")
    if tag.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="只有标签所有者可以删除")

    await db.delete(tag)
    await db.commit()


@router.get("/search", response_model=List[TagResponse], summary="搜索标签")
async def search_tags(
    q: str = Query(..., min_length=1, max_length=100, description="搜索关键字"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    按名称模糊搜索当前用户的标签。
    同时搜索被分享的书上所属的他人标签。
    """
    pattern = f"%{q}%"

    stmt = (
        select(Tag, func.count(BookTag.id).label("book_count"))
        .outerjoin(BookTag, Tag.id == BookTag.tag_id)
        .where(Tag.owner_id == current_user.id, Tag.name.ilike(pattern))
        .group_by(Tag.id)
        .order_by(Tag.name)
    )
    result = await db.execute(stmt)
    rows = result.all()

    return [
        TagResponse(
            id=tag.id,
            name=tag.name,
            owner_id=tag.owner_id,
            book_count=count,
            created_at=tag.created_at,
        )
        for tag, count in rows
    ]
