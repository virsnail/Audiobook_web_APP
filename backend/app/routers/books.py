import os
import json
import uuid
import shutil
import zipfile
import tempfile
import re
from typing import Optional, List
from mutagen.mp3 import MP3

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from fastapi.responses import FileResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_

from app.database import get_db
from app.models.user import User
from app.models.book import Book, BookShare, ReadingProgress
from app.schemas.book import BookResponse, BookListResponse, BookProgressUpdate, BookProgressResponse
from app.utils.deps import get_current_user, get_current_user_optional
from app.config import settings

router = APIRouter()


def get_mp3_duration(file_path: str) -> float:
    """获取 MP3 文件时长（秒）"""
    try:
        audio = MP3(file_path)
        return audio.info.length
    except Exception:
        return 0.0


def process_book_zip(zip_path: str, output_dir: str) -> dict:
    """
    处理上传的 ZIP 文件，提取并整理章节文件
    
    返回 manifest 数据
    """
    chapters = []
    
    with zipfile.ZipFile(zip_path, 'r') as zf:
        # 获取所有文件名
        file_names = zf.namelist()
        
        # 查找所有章节 ID（从 mp3 文件提取）
        chapter_ids = set()
        pattern = re.compile(r'^(\d{1,9})\.(mp3|txt|json)$', re.IGNORECASE)
        
        for name in file_names:
            # 获取文件名（去除目录）
            basename = os.path.basename(name)
            match = pattern.match(basename)
            if match:
                chapter_ids.add(match.group(1))
        
        if not chapter_ids:
            raise ValueError("ZIP 文件中未找到有效的章节文件 (格式: 0000001.mp3/txt/json)")
        
        # 按章节 ID 排序
        sorted_ids = sorted(chapter_ids)
        
        total_duration = 0.0
        
        for ch_id in sorted_ids:
            # 查找对应的文件
            mp3_file = None
            txt_file = None
            json_file = None
            
            for name in file_names:
                basename = os.path.basename(name)
                if basename.lower() == f"{ch_id}.mp3":
                    mp3_file = name
                elif basename.lower() == f"{ch_id}.txt":
                    txt_file = name
                elif basename.lower() == f"{ch_id}.json":
                    json_file = name
            
            if not all([mp3_file, txt_file, json_file]):
                continue  # 跳过不完整的章节
            
            # 提取文件
            audio_path = os.path.join(output_dir, f"{ch_id}_audio.mp3")
            text_path = os.path.join(output_dir, f"{ch_id}_text.txt")
            align_path = os.path.join(output_dir, f"{ch_id}_align.json")
            
            with zf.open(mp3_file) as src, open(audio_path, 'wb') as dst:
                shutil.copyfileobj(src, dst)
            
            with zf.open(txt_file) as src, open(text_path, 'wb') as dst:
                shutil.copyfileobj(src, dst)
            
            with zf.open(json_file) as src, open(align_path, 'wb') as dst:
                shutil.copyfileobj(src, dst)
            
            # 获取音频时长
            duration = get_mp3_duration(audio_path)
            
            chapters.append({
                "id": ch_id,
                "duration": round(duration, 2)
            })
            
            total_duration += duration
    
    if not chapters:
        raise ValueError("未能处理任何完整的章节")
    
    # 生成 manifest
    manifest = {
        "chapters": chapters,
        "totalDuration": round(total_duration, 2)
    }
    
    # 保存 manifest
    manifest_path = os.path.join(output_dir, "manifest.json")
    with open(manifest_path, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    
    return manifest


@router.get("", response_model=BookListResponse, summary="获取书籍列表")
async def get_books(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取用户的书籍列表（包括自己的和被分享的）"""
    # 自己的书籍
    result = await db.execute(
        select(Book).where(Book.owner_id == current_user.id)
    )
    my_books = result.scalars().all()
    
    # 被分享的书籍（私密分享）
    result = await db.execute(
        select(Book)
        .join(BookShare, Book.id == BookShare.book_id)
        .where(BookShare.shared_to == current_user.id)
    )
    shared_books = result.scalars().all()
    
    # 公开的书籍
    result = await db.execute(
        select(Book)
        .where(Book.is_public == True)
        .where(Book.owner_id != current_user.id)
    )
    public_books = result.scalars().all()
    
    # 合并去重
    all_books = {str(b.id): b for b in list(my_books) + list(shared_books) + list(public_books)}
    books = list(all_books.values())
    
    return BookListResponse(books=books, total=len(books))


@router.post("", response_model=BookResponse, summary="上传新书籍（ZIP格式）")
async def create_book(
    title: str = Form(...),
    author: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    book_zip: UploadFile = File(..., description="包含多章节文件的 ZIP (0000001.mp3/txt/json ...)"),
    cover_file: Optional[UploadFile] = File(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    上传新书籍（ZIP 格式）
    
    ZIP 文件应包含：
    - 0000001.mp3, 0000001.txt, 0000001.json
    - 0000002.mp3, 0000002.txt, 0000002.json
    - ...
    """
    # 验证文件类型
    if not book_zip.filename.lower().endswith('.zip'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="请上传 ZIP 格式的文件"
        )
    
    book_id = uuid.uuid4()
    storage_path = f"{current_user.id}/{book_id}"
    full_path = os.path.join(settings.MEDIA_PATH, "books", storage_path)
    
    # 创建目录
    os.makedirs(full_path, exist_ok=True)
    
    try:
        # 保存 ZIP 到临时文件
        with tempfile.NamedTemporaryFile(delete=False, suffix='.zip') as tmp:
            shutil.copyfileobj(book_zip.file, tmp)
            tmp_path = tmp.name
        
        # 处理 ZIP 文件
        manifest = process_book_zip(tmp_path, full_path)
        
        # 清理临时文件
        os.unlink(tmp_path)
        
        # 保存封面（可选）
        cover_path = None
        if cover_file:
            cover_path = f"{storage_path}/cover.jpg"
            with open(os.path.join(full_path, "cover.jpg"), "wb") as f:
                shutil.copyfileobj(cover_file.file, f)
        
        # 计算总段落数
        total_segments = 0
        for chapter in manifest["chapters"]:
            align_path = os.path.join(full_path, f"{chapter['id']}_align.json")
            if os.path.exists(align_path):
                with open(align_path, 'r', encoding='utf-8') as f:
                    align_data = json.load(f)
                    if isinstance(align_data, list):
                        total_segments += len(align_data)
                    elif isinstance(align_data, dict) and "segments" in align_data:
                        total_segments += len(align_data["segments"])
        
        # 创建数据库记录
        book = Book(
            id=book_id,
            owner_id=current_user.id,
            title=title,
            author=author,
            description=description,
            cover_path=cover_path,
            storage_path=storage_path,
            total_duration=int(manifest["totalDuration"]),
            total_segments=total_segments,
        )
        db.add(book)
        await db.commit()
        await db.refresh(book)
        
        return book
        
    except ValueError as e:
        # 清理已上传的文件
        if os.path.exists(full_path):
            shutil.rmtree(full_path)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        # 清理已上传的文件
        if os.path.exists(full_path):
            shutil.rmtree(full_path)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"上传失败: {str(e)}"
        )


@router.get("/{book_id}", response_model=BookResponse, summary="获取书籍详情")
async def get_book(
    book_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取书籍详情"""
    result = await db.execute(select(Book).where(Book.id == book_id))
    book = result.scalar_one_or_none()
    
    if not book:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="书籍不存在"
        )
    
    # 检查权限
    if book.owner_id != current_user.id and not book.is_public:
        # 检查是否被分享
        result = await db.execute(
            select(BookShare)
            .where(BookShare.book_id == book_id)
            .where(BookShare.shared_to == current_user.id)
        )
        if not result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权访问此书籍"
            )
    
    return book


@router.get("/{book_id}/manifest", summary="获取书籍章节清单")
async def get_manifest(
    book_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取书籍的章节清单 (manifest.json)"""
    result = await db.execute(select(Book).where(Book.id == book_id))
    book = result.scalar_one_or_none()
    
    if not book:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="书籍不存在"
        )
    
    manifest_path = os.path.join(
        settings.MEDIA_PATH, "books", book.storage_path, "manifest.json"
    )
    
    if not os.path.exists(manifest_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="章节清单不存在"
        )
    
    with open(manifest_path, "r", encoding="utf-8") as f:
        return json.load(f)


@router.get("/{book_id}/chapters/{chapter_id}/audio", summary="获取章节音频")
async def get_chapter_audio(
    book_id: uuid.UUID,
    chapter_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取指定章节的音频文件"""
    result = await db.execute(select(Book).where(Book.id == book_id))
    book = result.scalar_one_or_none()
    
    if not book:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="书籍不存在"
        )
    
    audio_path = os.path.join(
        settings.MEDIA_PATH, "books", book.storage_path, f"{chapter_id}_audio.mp3"
    )
    
    if not os.path.exists(audio_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="章节音频不存在"
        )
    
    return FileResponse(
        audio_path,
        media_type="audio/mpeg",
        filename=f"{chapter_id}.mp3"
    )


@router.get("/{book_id}/chapters/{chapter_id}/text", summary="获取章节文本")
async def get_chapter_text(
    book_id: uuid.UUID,
    chapter_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取指定章节的文本内容"""
    result = await db.execute(select(Book).where(Book.id == book_id))
    book = result.scalar_one_or_none()
    
    if not book:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="书籍不存在"
        )
    
    text_path = os.path.join(
        settings.MEDIA_PATH, "books", book.storage_path, f"{chapter_id}_text.txt"
    )
    
    if not os.path.exists(text_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="章节文本不存在"
        )
    
    with open(text_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    return Response(content=content, media_type="text/plain; charset=utf-8")


@router.get("/{book_id}/chapters/{chapter_id}/alignment", summary="获取章节对齐数据")
async def get_chapter_alignment(
    book_id: uuid.UUID,
    chapter_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取指定章节的音频-文本对齐数据"""
    result = await db.execute(select(Book).where(Book.id == book_id))
    book = result.scalar_one_or_none()
    
    if not book:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="书籍不存在"
        )
    
    align_path = os.path.join(
        settings.MEDIA_PATH, "books", book.storage_path, f"{chapter_id}_align.json"
    )
    
    if not os.path.exists(align_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="章节对齐数据不存在"
        )
    
    with open(align_path, "r", encoding="utf-8") as f:
        return json.load(f)


@router.get("/{book_id}/progress", response_model=BookProgressResponse, summary="获取阅读进度")
async def get_progress(
    book_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取用户在某本书的阅读进度"""
    result = await db.execute(
        select(ReadingProgress)
        .where(ReadingProgress.book_id == book_id)
        .where(ReadingProgress.user_id == current_user.id)
    )
    progress = result.scalar_one_or_none()
    
    if not progress:
        # 返回默认进度
        return BookProgressResponse(
            book_id=book_id,
            current_position=0,
            current_segment=0,
            playback_speed=1.0,
            updated_at=None
        )
    
    return progress


@router.put("/{book_id}/progress", response_model=BookProgressResponse, summary="保存阅读进度")
async def update_progress(
    book_id: uuid.UUID,
    progress_data: BookProgressUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """保存用户的阅读进度"""
    result = await db.execute(
        select(ReadingProgress)
        .where(ReadingProgress.book_id == book_id)
        .where(ReadingProgress.user_id == current_user.id)
    )
    progress = result.scalar_one_or_none()
    
    if progress:
        progress.current_position = progress_data.current_position
        progress.current_segment = progress_data.current_segment
        progress.playback_speed = progress_data.playback_speed
    else:
        progress = ReadingProgress(
            user_id=current_user.id,
            book_id=book_id,
            current_position=progress_data.current_position,
            current_segment=progress_data.current_segment,
            playback_speed=progress_data.playback_speed,
        )
        db.add(progress)
    
    await db.commit()
    await db.refresh(progress)
    
    return progress


@router.delete("/{book_id}", summary="删除书籍")
async def delete_book(
    book_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """删除书籍（仅限所有者）"""
    result = await db.execute(select(Book).where(Book.id == book_id))
    book = result.scalar_one_or_none()
    
    if not book:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="书籍不存在"
        )
    
    if book.owner_id != current_user.id and not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权删除此书籍"
        )
    
    # 删除文件
    full_path = os.path.join(settings.MEDIA_PATH, "books", book.storage_path)
    if os.path.exists(full_path):
        shutil.rmtree(full_path)
    
    # 删除数据库记录
    await db.delete(book)
    await db.commit()
    
    return {"message": "书籍已删除"}


@router.post("/{book_id}/share", summary="分享书籍")
async def share_book(
    book_id: uuid.UUID,
    shared_to_email: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """分享书籍给指定用户或公开分享"""
    result = await db.execute(select(Book).where(Book.id == book_id))
    book = result.scalar_one_or_none()
    
    if not book:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="书籍不存在"
        )
    
    if book.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="只有所有者可以分享此书籍"
        )
    
    if shared_to_email:
        # 分享给指定用户
        result = await db.execute(select(User).where(User.email == shared_to_email))
        target_user = result.scalar_one_or_none()
        
        if not target_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="目标用户不存在"
            )
        
        # 检查是否已分享
        result = await db.execute(
            select(BookShare)
            .where(BookShare.book_id == book_id)
            .where(BookShare.shared_to == target_user.id)
        )
        if result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="已经分享给该用户"
            )
        
        share = BookShare(
            book_id=book_id,
            shared_by=current_user.id,
            shared_to=target_user.id,
        )
        db.add(share)
        await db.commit()
        
        return {"message": f"已分享给 {shared_to_email}"}
    else:
        # 公开分享
        book.is_public = True
        await db.commit()
        
        return {"message": "书籍已设为公开"}
