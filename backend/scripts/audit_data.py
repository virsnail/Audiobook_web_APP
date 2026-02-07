
import asyncio
import sys
import os
import argparse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# 添加项目根目录到 pythonpath
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import AsyncSessionLocal
from app.models.book import Book
from app.config import settings

async def audit_data(session: AsyncSession):
    """审计数据：比较数据库和文件系统"""
    print(f"\n🔍 Starting Data Audit...")
    print(f"📂 Media Path: {settings.MEDIA_PATH}")
    
    books_dir = os.path.join(settings.MEDIA_PATH, "books")
    if not os.path.exists(books_dir):
        print(f"❌ Media books directory not found: {books_dir}")
        return

    # 1. 获取数据库中的所有书籍
    result = await session.execute(select(Book))
    db_books = result.scalars().all()
    db_book_paths = {book.storage_path for book in db_books}
    db_book_ids = {str(book.id) for book in db_books}
    
    print(f"\n📚 Total Books in Database: {len(db_books)}")

    # 2. 获取文件系统中的所有书籍目录
    fs_book_dirs = set()
    try:
        for item in os.listdir(books_dir):
            if os.path.isdir(os.path.join(books_dir, item)):
                fs_book_dirs.add(item)
    except OSError as e:
        print(f"❌ Error accessing media directory: {e}")
        return
        
    print(f"📁 Total Book Directories in Filesystem: {len(fs_book_dirs)}")
    
    # 3. 查找数据库有但文件系统没有的 (Orphaned DB Records)
    # storage_path通常就是目录名，但为了稳健，我们假设它可能是路径
    # 这里我们简化假设 storage_path 就是目录名，或者 storage_path 的第一级目录
    
    orphaned_db_records = []
    for book in db_books:
        # storage_path exp: "uuid-folder"
        path = book.storage_path
        if path not in fs_book_dirs:
             # 再检查一下是否是完整路径
             full_path = os.path.join(books_dir, path)
             if not os.path.exists(full_path):
                 orphaned_db_records.append(book)

    # 4. 查找文件系统有但数据库没有的 (Orphaned Files)
    orphaned_files = []
    for dir_name in fs_book_dirs:
        # 假设 storage_path 就是目录名
        if dir_name not in db_book_paths:
            orphaned_files.append(dir_name)

    # 5. 生成报告
    print("\n" + "="*50)
    print("AUDIT REPORT")
    print("="*50)
    
    if not orphaned_db_records and not orphaned_files:
        print("✅ Data is consistent! No issues found.")
    else:
        if orphaned_db_records:
            print(f"\n⚠️  Found {len(orphaned_db_records)} orphaned database records (Missing files):")
            for book in orphaned_db_records:
                print(f"   - [ID: {book.id}] {book.title} (Path: {book.storage_path})")
                
        if orphaned_files:
            print(f"\n⚠️  Found {len(orphaned_files)} orphaned directories (No DB record):")
            for dir_name in orphaned_files:
                print(f"   - {dir_name}")
                
    print("\n" + "="*50)

async def main():
    async with AsyncSessionLocal() as session:
        await audit_data(session)

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
