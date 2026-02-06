import os
import json
import uuid
import shutil
import zipfile
import tempfile
import re
from typing import Optional, List
from mutagen.mp3 import MP3

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, Request, BackgroundTasks
from fastapi.responses import FileResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, delete

from app.database import get_db
from app.models.user import User
from app.models.book import Book, BookShare, ReadingProgress
from app.schemas.book import BookResponse, BookListResponse, BookProgressUpdate, BookProgressResponse
from app.utils.deps import get_current_user, get_current_user_optional, get_current_user_token_or_query
from app.config import settings
from app.utils import epub_utils  # 方案2: EPUB processing
from app.services.activity_logger import ActivityLogger
from app.database import AsyncSessionLocal

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
    
    支持两种格式:
    - 方案1 (TXT): ch001_audio.mp3, ch001_text.txt, ch001_align.json
    - 方案2 (EPUB): bookname.epub + ch001_audio.mp3 + ch001_align.json
    
    返回 manifest 数据
    """
    chapters = []
    epub_manifest = None
    book_type = "txt"
    extracted_files = []
    
    # 1. 预先解压所有文件 (除了系统文件)
    with zipfile.ZipFile(zip_path, 'r') as zf:
        file_names = zf.namelist()
        for name in file_names:
            if name.startswith('__MACOSX') or name.endswith('.DS_Store') or name.endswith('/'):
                continue
            
            basename = os.path.basename(name)
            if not basename: continue
            
            target_path = os.path.join(output_dir, basename)
            with zf.open(name) as src, open(target_path, 'wb') as dst:
                shutil.copyfileobj(src, dst)
            extracted_files.append(basename)

    # 2. 判断是否包含 EPUB 文件 (方案2)
    epub_file_name = next((f for f in extracted_files if f.lower().endswith('.epub')), None)
    
    if epub_file_name:
        # 方案2: 处理 EPUB
        book_type = "epub"
        epub_path = os.path.join(output_dir, epub_file_name)
        
        # 解压 EPUB
        epub_extract_dir = epub_utils.extract_epub(epub_path, output_dir)
        
        # 收集对齐文件列表
        align_files = [f for f in extracted_files if re.match(r'^ch(\d{1,9})_align\.json$', f, re.IGNORECASE)]
        
        # 分析 EPUB 结构并生成 manifest
        try:
            # 尝试提取封面
            epub_utils.extract_cover_image(epub_extract_dir, output_dir)

            epub_manifest = epub_utils.create_epub_manifest(epub_extract_dir, align_files)
            
            # 保存 EPUB manifest
            epub_manifest_path = os.path.join(output_dir, "epub_manifest.json")
            with open(epub_manifest_path, 'w', encoding='utf-8') as f:
                json.dump(epub_manifest, f, ensure_ascii=False, indent=2)
            
            # 注意：如果 extracted_files 中包含 "manifest.json"，它已经存在于 output_dir 中了
            # 无需额外操作
            
            return {
                "type": "epub",
                "epub_manifest": epub_manifest,
                "totalDuration": 0,  # 会在后面计算
                "chapters": epub_manifest.get('chapters', [])
            }
        
        except Exception as e:
            raise ValueError(f"EPUB 处理失败: {str(e)}")
    
    # ===== 方案1: 处理 TXT (对已解压的文件进行整理) =====
    
    # 查找所有章节 ID
    chapter_files = {}  # {chapter_id: {mp3: name, txt: name, json: name}}
    
    # 匹配两种格式：
    # 格式1: 纯数字 (0000001.mp3, 0000001.txt, 0000001.json)
    pattern_old = re.compile(r'^(\d{1,9})\.(mp3|txt|json)$', re.IGNORECASE)
    # 格式2: ch开头 (ch001_audio.mp3, ch001_text.txt, ch001_align.json)
    pattern_new = re.compile(r'^ch(\d{1,9})_(audio\.mp3|text\.txt|align\.json)$', re.IGNORECASE)
    
    for basename in extracted_files:
        # 尝试匹配旧格式
        match_old = pattern_old.match(basename)
        if match_old:
            chapter_id = match_old.group(1)
            file_type = match_old.group(2).lower()
            
            if chapter_id not in chapter_files:
                chapter_files[chapter_id] = {}
            chapter_files[chapter_id][file_type] = basename
            continue
        
        # 尝试匹配新格式
        match_new = pattern_new.match(basename)
        if match_new:
            chapter_id = match_new.group(1)
            file_suffix = match_new.group(2).lower()
            
            if chapter_id not in chapter_files:
                chapter_files[chapter_id] = {}
            
            # 映射新格式到标准类型
            if file_suffix == 'audio.mp3':
                chapter_files[chapter_id]['mp3'] = basename
            elif file_suffix == 'text.txt':
                chapter_files[chapter_id]['txt'] = basename
            elif file_suffix == 'align.json':
                chapter_files[chapter_id]['json'] = basename
    
    # 查找封面图片 (如果存在)
    if not any(re.match(r'^cover\.(jpg|jpeg|png)$', f, re.IGNORECASE) for f in extracted_files):
        # 如果没有标准封面，看有没有被解压进去
        pass 
        
    if not chapter_files:
        raise ValueError("ZIP 文件中未找到有效的章节文件\n支持格式:\n  - 旧格式: 0000001.mp3/txt/json\n  - 新格式: ch001_audio.mp3, ch001_text.txt, ch001_align.json")
    
    # 按章节 ID 排序
    sorted_ids = sorted(chapter_files.keys())
    
    total_duration = 0.0
    
    for ch_id in sorted_ids:
        files = chapter_files[ch_id]
        
        # 检查是否有完整的三个文件
        if not all(key in files for key in ['mp3', 'txt', 'json']):
            continue  # 跳过不完整的章节
        
        # 目标文件路径
        audio_path = os.path.join(output_dir, f"{ch_id}_audio.mp3")
        text_path = os.path.join(output_dir, f"{ch_id}_text.txt")
        align_path = os.path.join(output_dir, f"{ch_id}_align.json")
        
        # 重命名/移动文件到规范名称
        # 如果原文件名就是规范名称，os.rename 可能会报错（同一文件），所以先检查
        
        src_mp3 = os.path.join(output_dir, files['mp3'])
        if src_mp3 != audio_path: shutil.move(src_mp3, audio_path)
            
        src_txt = os.path.join(output_dir, files['txt'])
        if src_txt != text_path: shutil.move(src_txt, text_path)
            
        src_json = os.path.join(output_dir, files['json'])
        if src_json != align_path: shutil.move(src_json, align_path)
        
        # 获取音频时长
        duration = get_mp3_duration(audio_path)
        
        chapters.append({
            "id": ch_id,
            "duration": round(duration, 2)
        })
        
        total_duration += duration
    
    if not chapters:
        raise ValueError("未能处理任何完整的章节")
    
    # 生成 manifest (方案1)
    manifest = {
        "type": "txt",
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
    book_zip: UploadFile = File(..., description="包含多章节文件的 ZIP (支持: 0000001.mp3/txt/json 或 ch001_audio.mp3/text.txt/align.json)"),
    cover_file: Optional[UploadFile] = File(None),
    background_tasks: BackgroundTasks = None,  # Inject
    request: Request = None,  # Inject
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    上传新书籍（ZIP 格式）
    
    ZIP 文件支持两种命名格式：
    
    旧格式:
    - 0000001.mp3, 0000001.txt, 0000001.json
    - 0000002.mp3, 0000002.txt, 0000002.json
    - ...
    
    新格式:
    - ch001_audio.mp3, ch001_text.txt, ch001_align.json
    - ch002_audio.mp3, ch002_text.txt, ch002_align.json
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
        else:
            # 检查 ZIP 中是否包含封面
            for ext in ['.jpg', '.jpeg', '.png']:
                extracted_cover = os.path.join(full_path, f"cover{ext}")
                if os.path.exists(extracted_cover):
                    cover_path = f"{storage_path}/cover{ext}"
                    break
        
        # 计算总段落数和书籍类型
        total_segments = 0
        book_type = manifest.get("type", "txt")
        epub_structure_json = None
        
        if book_type == "epub":
            # 方案2: EPUB 书籍
            epub_manifest = manifest.get("epub_manifest", {})
            epub_structure_json = json.dumps(epub_manifest, ensure_ascii=False)
            
            # 从 EPUB manifest 计算章节数
            for chapter in epub_manifest.get('chapters', []):
                if chapter.get('has_audio'):
                    # 读取对齐文件计算段落数
                    chapter_id = chapter['id']
                    align_path = os.path.join(full_path, f"ch{chapter_id}_align.json")
                    if os.path.exists(align_path):
                        with open(align_path, 'r', encoding='utf-8') as f:
                            align_data = json.load(f)
                            if isinstance(align_data, list):
                                total_segments += len(align_data)
                            elif isinstance(align_data, dict) and "segments" in align_data:
                                total_segments += len(align_data["segments"])
            
            # 计算总时长（从音频文件）
            total_duration = 0
            for chapter in epub_manifest.get('chapters', []):
                if chapter.get('audio_file'):
                    audio_path = os.path.join(full_path, chapter['audio_file'])
                    if os.path.exists(audio_path):
                        total_duration += get_mp3_duration(audio_path)
        
        else:
            # 方案1: TXT 书籍（原有逻辑）
            for chapter in manifest["chapters"]:
                align_path = os.path.join(full_path, f"{chapter['id']}_align.json")
                if os.path.exists(align_path):
                    with open(align_path, 'r', encoding='utf-8') as f:
                        align_data = json.load(f)
                        if isinstance(align_data, list):
                            total_segments += len(align_data)
                        elif isinstance(align_data, dict) and "segments" in align_data:
                            total_segments += len(align_data["segments"])
            
            total_duration = manifest.get("totalDuration", 0)
        
        # 创建数据库记录
        book = Book(
            id=book_id,
            owner_id=current_user.id,
            title=title,
            author=author,
            description=description,
            cover_path=cover_path,
            storage_path=storage_path,
            total_duration=int(total_duration),
            total_segments=total_segments,
            book_type=book_type,  # 新增字段
            epub_structure=epub_structure_json,  # 新增字段
        )
        db.add(book)
        await db.commit()
        await db.refresh(book)
        
        # 记录上传活动
        action_type = "UPLOAD_TXT"
        if book_type == "epub":
            action_type = "UPLOAD_EPUB"
            
        if background_tasks:
            background_tasks.add_task(
                ActivityLogger.log_activity_background,
                AsyncSessionLocal,
                str(current_user.id),
                action_type,
                str(book.id),
                {"title": book.title, "filename": book_zip.filename},
                request.headers.get("user-agent") if request else None
            )
        
        return book
        
    except ValueError as e:
        # 清理已上传的文件
        if os.path.exists(full_path):
            shutil.rmtree(full_path)
        
        # 记录上传失败活动
        if background_tasks:
            background_tasks.add_task(
                ActivityLogger.log_activity_background,
                AsyncSessionLocal,
                str(current_user.id),
                "UPLOAD_FAILED",
                None,
                {"error": str(e), "title": title, "filename": book_zip.filename},
                request.headers.get("user-agent") if request else None
            )
            
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        # 清理已上传的文件
        if os.path.exists(full_path):
            shutil.rmtree(full_path)
            
        # 记录上传失败活动
        if background_tasks:
            background_tasks.add_task(
                ActivityLogger.log_activity_background,
                AsyncSessionLocal,
                str(current_user.id),
                "UPLOAD_FAILED",
                None,
                {"error": str(e), "title": title, "filename": book_zip.filename},
                request.headers.get("user-agent") if request else None
            )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"上传失败: {str(e)}"
        )


# ============= TXT 文本转有声书 =============

import asyncio
import logging
from app.utils import tts_utils

logger = logging.getLogger(__name__)


async def background_tts_processing(
    book_id: uuid.UUID, 
    raw_text: str, 
    output_dir: str,
    book_title: str,
    db_url: str,
    voice: str = "zh-CN-YunyangNeural"
):
    """后台任务：TTS 处理完成后更新数据库状态"""
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy.orm import sessionmaker
    
    # 创建新的数据库会话（后台任务不能使用请求的会话）
    engine = create_async_engine(db_url)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    try:
        logger.info(f"开始处理书籍 {book_id} 的 TTS 转换 (Voice: {voice})")
        
        # 执行 TTS 处理
        manifest = await tts_utils.process_text_to_audiobook(
            raw_text=raw_text,
            output_dir=output_dir,
            book_title=book_title,
            voice=voice
        )
        
        async with async_session() as session:
            result = await session.execute(select(Book).where(Book.id == book_id))
            book = result.scalar_one_or_none()
            
            if book and manifest:
                book.processing_status = "ready"
                book.total_duration = int(manifest.get('total_duration', 0))
                book.total_segments = manifest.get('total_words', 0)
                await session.commit()
                logger.info(f"书籍 {book_id} TTS 处理完成")
            elif book:
                book.processing_status = "failed"
                book.processing_error = "TTS 处理失败"
                await session.commit()
                logger.error(f"书籍 {book_id} TTS 处理失败")
                
    except Exception as e:
        logger.error(f"书籍 {book_id} TTS 处理异常: {str(e)}")
        try:
            async with async_session() as session:
                result = await session.execute(select(Book).where(Book.id == book_id))
                book = result.scalar_one_or_none()
                if book:
                    book.processing_status = "failed"
                    book.processing_error = str(e)
                    await session.commit()
        except Exception as db_err:
            logger.error(f"更新书籍状态失败: {str(db_err)}")
    finally:
        await engine.dispose()


@router.post("/from-text", response_model=BookResponse, summary="从文本创建有声书")
async def create_book_from_text(
    background_tasks: BackgroundTasks,
    request: Request,
    title: str = Form(...),
    author: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    text_content: Optional[str] = Form(None),
    txt_file: Optional[UploadFile] = File(None),
    voice: str = Form("zh-CN-YunyangNeural"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    从纯文本创建有声书
    
    支持两种输入方式：
    1. text_content: 直接粘贴文本内容
    2. txt_file: 上传 TXT 文件
    
    服务器将异步处理：
    - 使用 Edge-TTS 生成音频
    - 生成词级别时间对齐
    - 按时长自动分割章节
    """
    try:
        # 获取文本内容
        raw_text = None
        
        if txt_file and txt_file.filename:
            # 从上传的文件读取
            content = await txt_file.read()
            try:
                raw_text = content.decode('utf-8')
            except UnicodeDecodeError:
                raw_text = content.decode('gbk', errors='ignore')
        elif text_content:
            raw_text = text_content
        
        if not raw_text or not raw_text.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="请提供文本内容（上传 TXT 文件或粘贴文本）"
            )
        
        # 创建书籍目录
        book_id = uuid.uuid4()
        storage_path = f"{current_user.id}/{book_id}"
        full_path = os.path.join(settings.MEDIA_PATH, "books", storage_path)
        os.makedirs(full_path, exist_ok=True)
        
        # 保存原始文本
        raw_text_path = os.path.join(full_path, "raw_text.txt")
        with open(raw_text_path, 'w', encoding='utf-8') as f:
            f.write(raw_text)
        
        # Markdown 格式检测和清洗
        # 如果包含 MD 格式标记，自动清洗；如果是纯文本，不会出错
        from app.utils.tts_utils import MarkdownCleaner
        
        logger.info(f"Checking for MD markers in text of length {len(raw_text)}")
        # 检测是否包含常见 MD 标记
        has_md_markers = bool(
            re.search(r'```|^#{1,6}\s|\*\*|\[.+\]\(.+\)|!\[.*\]\(.+\)', raw_text, re.MULTILINE)
        )
        logger.info(f"Has MD markers: {has_md_markers}")
        
        if has_md_markers:
            logger.info(f"检测到 Markdown 格式，进行清洗处理")
            try:
                cleaned_text = MarkdownCleaner.md_to_txt(raw_text)
                logger.info(f"Cleaned text length: {len(cleaned_text)}")
            except Exception as e:
                logger.error(f"Markdown cleaning failed: {e}")
                # Fallback to raw text if cleaning fails
                cleaned_text = raw_text
        else:
            # 尝试清洗版权信息（针对纯文本）
            try:
                logger.info("Tentatively cleaning copyright info from raw text")
                cleaned_text = MarkdownCleaner.clean_copyright_text(raw_text)
            except Exception as e:
                logger.warning(f"Copyright cleaning failed: {e}")
                cleaned_text = raw_text
        
        # 使用清洗后的文本进行 TTS 处理
        
        # 创建数据库记录（状态为 processing）
        book = Book(
            id=book_id,
            owner_id=current_user.id,
            title=title,
            author=author,
            description=description,
            storage_path=storage_path,
            book_type="txt",
            processing_status="processing",
            total_duration=0,
            total_segments=0,
        )
        db.add(book)
        await db.commit()
        await db.refresh(book)
        
        # 添加后台任务（使用清洗后的文本）
        background_tasks.add_task(
            background_tts_processing,
            book_id=book_id,
            raw_text=cleaned_text,  # 使用清洗后的文本
            output_dir=full_path,
            book_title=title,
            db_url=str(settings.DATABASE_URL),
            voice=voice
        )
        
        # 记录上传活动 (TXT/Text)
        background_tasks.add_task(
            ActivityLogger.log_activity_background,
            AsyncSessionLocal,
            str(current_user.id),
            "UPLOAD_TXT",
            str(book.id),
            {"title": book.title, "source": "file" if txt_file else "text"},
            request.headers.get("user-agent")
        )
        
        return book

    except Exception as e:
        # 记录上传失败活动
        background_tasks.add_task(
            ActivityLogger.log_activity_background,
            AsyncSessionLocal,
            str(current_user.id),
            "UPLOAD_FAILED",
            None,
            {"error": str(e), "title": title, "type": "txt"},
            request.headers.get("user-agent")
        )
        raise e



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
    background_tasks: BackgroundTasks,
    request: Request,
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
    
    # 记录阅读活动
    background_tasks.add_task(
        ActivityLogger.log_activity_background,
        AsyncSessionLocal,
        str(current_user.id),
        "READ_BOOK",
        str(book.id),
        {"title": book.title},
        request.headers.get("user-agent")
    )
    
    manifest_path = os.path.join(
        settings.MEDIA_PATH, "books", book.storage_path, "manifest.json"
    )
    
    # 如果 manifest.json 存在，直接返回 (TXT书籍)
    if os.path.exists(manifest_path):
        with open(manifest_path, "r", encoding="utf-8") as f:
            return json.load(f)
            
    # 如果不存在，检查是否为 EPUB 书籍并尝试读取 epub_manifest.json
    epub_manifest_path = os.path.join(
        settings.MEDIA_PATH, "books", book.storage_path, "epub_manifest.json"
    )
    
    if os.path.exists(epub_manifest_path):
        with open(epub_manifest_path, "r", encoding="utf-8") as f:
            epub_data = json.load(f)
            
        # 转换为 TXT manifest 格式
        # TXT manifest: {"type": "txt", "chapters": [{"id": "...", "duration": ...}], "totalDuration": ...}
        chapters = []
        total_duration = 0
        
        for ch in epub_data.get('chapters', []):
            duration = ch.get('duration', 0)
            chapters.append({
                "id": ch['id'],
                "duration": duration,
                "title": ch.get('title', f"Chapter {ch['id']}")
            })
            total_duration += duration
            
        return {
            "type": "epub_compatible",
            "chapters": chapters,
            "totalDuration": round(total_duration, 2)
        }

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="章节清单不存在"
    )


@router.get("/{book_id}/chapters/{chapter_id}/audio", summary="获取章节音频")
async def get_chapter_audio(
    book_id: uuid.UUID,
    chapter_id: str,
    request: Request,  # 添加 Request 参数以访问 headers
    current_user: User = Depends(get_current_user_token_or_query),
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
    
    base_path = os.path.join(settings.MEDIA_PATH, "books", book.storage_path)
    audio_path = os.path.join(base_path, f"{chapter_id}_audio.mp3")
    
    if not os.path.exists(audio_path):
        # 尝试带 ch 前缀的格式：ch1, ch001
        fallback_path = os.path.join(base_path, f"ch{chapter_id}_audio.mp3")
        if os.path.exists(fallback_path):
            audio_path = fallback_path
        else:
            # 尝试三位数字格式 ch001
            try:
                chapter_num = int(chapter_id)
                fallback_path = os.path.join(base_path, f"ch{chapter_num:03d}_audio.mp3")
                if os.path.exists(fallback_path):
                    audio_path = fallback_path
                else:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="章节音频不存在"
                    )
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="章节音频不存在"
                )
    
    
    # 关键修复：支持 HTTP Range requests，允许浏览器 seek 到任意位置
    from fastapi.responses import StreamingResponse
    import re
    
    # 获取文件大小
    file_stat = os.stat(audio_path)
    file_size = file_stat.st_size
    
    # 从请求头中解析 Range
    range_header = request.headers.get("Range")
    
    if range_header:
        # 解析 Range 头：bytes=start-end
        import re
        match = re.match(r'bytes=(\d+)-(\d*)', range_header)
        if match:
            start = int(match.group(1))
            end = int(match.group(2)) if match.group(2) else file_size - 1
            
            # 确保范围有效
            if start >= file_size:
                raise HTTPException(
                    status_code=416,  # Range Not Satisfiable
                    detail="Range not satisfiable"
                )
            
            end = min(end, file_size - 1)
            length = end - start + 1
            
            # 读取文件的指定范围
            def file_iterator(file_path: str, start: int, length: int, chunk_size=8192):
                with open(file_path, 'rb') as f:
                    f.seek(start)
                    remaining = length
                    while remaining > 0:
                        chunk = f.read(min(chunk_size, remaining))
                        if not chunk:
                            break
                        remaining -= len(chunk)
                        yield chunk
            
            headers = {
                "Content-Range": f"bytes {start}-{end}/{file_size}",
                "Accept-Ranges": "bytes",
                "Content-Length": str(length),
                "Content-Type": "audio/mpeg",
            }
            
            return StreamingResponse(
                file_iterator(audio_path, start, length),
                status_code=206,  # Partial Content
                headers=headers
            )
    
    # 没有 Range 请求，返回完整文件
    return FileResponse(
        audio_path,
        media_type="audio/mpeg",
        filename=f"{chapter_id}.mp3",
        headers={"Accept-Ranges": "bytes"}  # 告诉浏览器支持 Range
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
        # 尝试带 ch 前缀的格式：ch1, ch001
        fallback_path = os.path.join(
            settings.MEDIA_PATH, "books", book.storage_path, f"ch{chapter_id}_text.txt"
        )
        if os.path.exists(fallback_path):
            text_path = fallback_path
        else:
            # 尝试三位数字格式 ch001
            try:
                chapter_num = int(chapter_id)
                fallback_path = os.path.join(
                    settings.MEDIA_PATH, "books", book.storage_path, f"ch{chapter_num:03d}_text.txt"
                )
                if os.path.exists(fallback_path):
                    text_path = fallback_path
                else:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="章节文本不存在"
                    )
            except ValueError:
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
    
    base_path = os.path.join(settings.MEDIA_PATH, "books", book.storage_path)
    align_path = os.path.join(base_path, f"{chapter_id}_align.json")
    
    if not os.path.exists(align_path):
        # 尝试带 ch 前缀的格式：ch1, ch001
        fallback_path = os.path.join(base_path, f"ch{chapter_id}_align.json")
        if os.path.exists(fallback_path):
            align_path = fallback_path
        else:
            # 尝试三位数字格式 ch001
            try:
                chapter_num = int(chapter_id)
                fallback_path = os.path.join(base_path, f"ch{chapter_num:03d}_align.json")
                if os.path.exists(fallback_path):
                    align_path = fallback_path
                else:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="章节对齐数据不存在"
                    )
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="章节对齐数据不存在"
                )
    
    with open(align_path, "r", encoding="utf-8") as f:
        return json.load(f)


@router.get("/{book_id}/epub/manifest", summary="获取 EPUB manifest (方案2)")
async def get_epub_manifest(
    book_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取 EPUB 书籍的 manifest（方案2专用）"""
    result = await db.execute(select(Book).where(Book.id == book_id))
    book = result.scalar_one_or_none()
    
    if not book:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="书籍不存在"
        )
    
    if book.book_type != "epub":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="此书籍不是 EPUB 格式"
        )
    
    epub_manifest_path = os.path.join(
        settings.MEDIA_PATH, "books", book.storage_path, "epub_manifest.json"
    )
    
    if not os.path.exists(epub_manifest_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="EPUB manifest 不存在"
        )
    
    with open(epub_manifest_path, "r", encoding="utf-8") as f:
        return json.load(f)


from fastapi import Cookie, Query
from app.utils.security import decode_token

@router.get("/{book_id}/epub_content/{file_path:path}", summary="获取 EPUB 内容文件")
async def get_epub_content(
    book_id: uuid.UUID,
    file_path: str,
    token_query: Optional[str] = Query(None, alias="token"),
    token_cookie: Optional[str] = Cookie(None, alias="access_token"),
    db: AsyncSession = Depends(get_db)
):
    """获取 EPUB 的静态资源文件 (HTML/Images/CSS)"""
    # 验证 Token (支持 Query Param 或 Cookie)
    token = token_query or token_cookie
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="需要认证"
        )
        
    user_id = decode_token(token)
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的认证凭据"
        )
        
    # 验证书籍权限 (简化: 只要登录即可，或者检查 owner)
    # result = await db.execute(select(Book).where(Book.id == book_id, Book.owner_id == user_id)) ...
    # 为了兼容共享逻辑，这里暂时只查书籍是否存在。严格逻辑应该查 owner_id == user_id
    
    result = await db.execute(select(Book).where(Book.id == book_id))
    book = result.scalar_one_or_none()
    
    if not book:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="书籍不存在"
        )
        
    # 鉴权: 检查当前用户是否是书籍拥有者
    if str(book.owner_id) != user_id:
         raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权访问该书籍"
        )

    # 构建文件完整路径
    # books/{storage_path}/epub/{file_path}
    base_path = os.path.join(settings.MEDIA_PATH, "books", book.storage_path, "epub")
    full_path = os.path.join(base_path, file_path)
    
    # 安全检查：防止目录遍历攻击
    if not os.path.abspath(full_path).startswith(os.path.abspath(base_path)):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="非法的文件访问路径"
        )
    
    if not os.path.exists(full_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="文件不存在"
        )
        
    # 根据扩展名猜测 MIME type
    media_type = "application/octet-stream"
    lower_path = full_path.lower()
    if lower_path.endswith(('.html', '.xhtml', '.htm')):
        media_type = "text/html"
    elif lower_path.endswith('.css'):
        media_type = "text/css"
    elif lower_path.endswith(('.jpg', '.jpeg')):
        media_type = "image/jpeg"
    elif lower_path.endswith('.png'):
        media_type = "image/png"
    elif lower_path.endswith('.gif'):
        media_type = "image/gif"
    elif lower_path.endswith('.svg'):
        media_type = "image/svg+xml"
    elif lower_path.endswith('.js'):
        media_type = "application/javascript"
    
    return FileResponse(full_path, media_type=media_type)


@router.get("/{book_id}/epub/chapters/{chapter_file:path}", summary="获取 EPUB 章节 HTML (方案2)")
async def get_epub_chapter_html(
    book_id: uuid.UUID,
    chapter_file: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    获取 EPUB 书籍的章节 HTML 文件（方案2专用）
    
    chapter_file: EPUB 章节文件的相对路径，例如 "OEBPS/Text/chapter01.xhtml"
    """
    result = await db.execute(select(Book).where(Book.id == book_id))
    book = result.scalar_one_or_none()
    
    if not book:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="书籍不存在"
        )
    
    if book.book_type != "epub":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="此书籍不是 EPUB 格式"
        )
    
    # 构建 EPUB 章节文件路径
    # 文件在 {storage_path}/epub/{chapter_file}
    chapter_path = os.path.join(
        settings.MEDIA_PATH, "books", book.storage_path, "epub", chapter_file
    )
    
    # 安全检查：确保路径在书籍目录内
    book_dir = os.path.join(settings.MEDIA_PATH, "books", book.storage_path, "epub")
    if not os.path.abspath(chapter_path).startswith(os.path.abspath(book_dir)):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="非法的文件路径"
        )
    
    if not os.path.exists(chapter_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"章节文件不存在: {chapter_file}"
        )
    
    # 读取 HTML 内容
    with open(chapter_path, "r", encoding="utf-8") as f:
        html_content = f.read()
    
    return Response(
        content=html_content,
        media_type="text/html; charset=utf-8"
    )



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
    background_tasks: BackgroundTasks,
    request: Request,
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
    
    
    # 删除文件系统中的所有书籍文件
    full_path = os.path.join(settings.MEDIA_PATH, "books", book.storage_path)
    
    # 安全检查：确保路径在 MEDIA_PATH 内，防止删除系统文件
    media_books_path = os.path.join(settings.MEDIA_PATH, "books")
    if not os.path.abspath(full_path).startswith(os.path.abspath(media_books_path)):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Invalid storage path"
        )
    
    if os.path.exists(full_path):
        # 列出将要删除的文件（用于日志记录）
        import logging
        logger = logging.getLogger(__name__)
        
        deleted_files = []
        for root, dirs, files in os.walk(full_path):
            for file in files:
                deleted_files.append(os.path.join(root, file))
        
        logger.info(f"Deleting book {book_id} with {len(deleted_files)} files:")
        for file_path in deleted_files:
            logger.info(f"  - {os.path.relpath(file_path, full_path)}")
        
        # 删除整个书籍目录（包括所有音频、文本、对齐文件、封面、未来的 epub 等）
        shutil.rmtree(full_path)
        logger.info(f"Successfully deleted directory: {full_path}")
    else:
        # 文件已不存在，但继续删除数据库记录
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"Book directory not found: {full_path}, proceeding to delete DB record only")
    
    # 删除数据库记录（包括级联删除相关的 shares 和 reading_progress）
    await db.delete(book)
    await db.commit()
    
    # 记录删除活动
    background_tasks.add_task(
        ActivityLogger.log_activity_background,
        AsyncSessionLocal,
        str(current_user.id),
        "DELETE_BOOK",
        str(book_id),
        {"title": book.title},
        request.headers.get("user-agent")
    )
    
    return {"message": "书籍已删除"}


@router.post("/{book_id}/share", summary="分享书籍")
async def share_book(
    book_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    request: Request,
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
        existing_share = result.scalar_one_or_none()
        
        if existing_share:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="已经分享给该用户"
            )
        
        share = BookShare(
            book_id=book_id,
            shared_to=target_user.id,
            shared_by=current_user.id
        )
        db.add(share)
        await db.commit()
        
        # 记录分享给用户
        background_tasks.add_task(
            ActivityLogger.log_activity_background,
            AsyncSessionLocal,
            str(current_user.id),
            "SHARE_USER",
            str(book.id),
            {"title": book.title, "shared_to": shared_to_email},
            request.headers.get("user-agent")
        )
        
        return {"message": f"已将书籍分享给 {shared_to_email}"}
    else:
        # 公开分享
        book.is_public = True
        await db.commit()
        
        # 记录公开分享
        background_tasks.add_task(
            ActivityLogger.log_activity_background,
            AsyncSessionLocal,
            str(current_user.id),
            "SHARE_PUBLIC",
            str(book.id),
            {"title": book.title},
            request.headers.get("user-agent")
        )
        
        return {"message": "书籍已公开分享"}


@router.get("/{book_id}/shares", summary="获取书籍分享状态")
async def get_book_shares(
    book_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取书籍的所有分享信息"""
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
            detail="只有所有者可以查看分享状态"
        )
    
    # 获取所有分享给指定用户的记录
    result = await db.execute(
        select(BookShare, User)
        .join(User, BookShare.shared_to == User.id)
        .where(BookShare.book_id == book_id)
    )
    shares_with_users = result.all()
    
    shared_users = [
        {
            "email": user.email,
            "nickname": user.nickname,
            "shared_at": share.created_at.isoformat() if share.created_at else None
        }
        for share, user in shares_with_users
    ]
    
    return {
        "is_public": book.is_public,
        "shared_users": shared_users,
        "total_shares": len(shared_users)
    }


@router.delete("/{book_id}/shares", summary="取消所有分享")
async def unshare_book(
    book_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """取消书籍的所有分享（包括公开分享和指定用户分享）"""
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
            detail="只有所有者可以取消分享"
        )
    
    # 取消公开分享
    book.is_public = False
    
    # 删除所有指定用户的分享记录
    result = await db.execute(
        delete(BookShare).where(BookShare.book_id == book_id)
    )
    deleted_shares = result.rowcount
    
    await db.commit()
    
    # 记录取消分享
    background_tasks.add_task(
        ActivityLogger.log_activity_background,
        AsyncSessionLocal,
        str(current_user.id),
        "UNSHARE",
        str(book.id),
        {"title": book.title, "deleted_shares": deleted_shares},
        request.headers.get("user-agent")
    )
    
    return {
        "message": "已取消所有分享",
        "deleted_shares": deleted_shares
    }


@router.get("/{book_id}/cover", summary="获取书籍封面")
async def get_book_cover(
    book_id: uuid.UUID,
    db: AsyncSession = Depends(get_db)
):
    """获取书籍封面图片"""
    result = await db.execute(select(Book).where(Book.id == book_id))
    book = result.scalar_one_or_none()
    
    if not book:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="书籍不存在"
        )
    
    if not book.cover_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="封面不存在"
        )
    
    cover_full_path = os.path.join(settings.MEDIA_PATH, "books", book.cover_path)
    
    if not os.path.exists(cover_full_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="封面文件丢失"
        )
    
    return FileResponse(cover_full_path)
