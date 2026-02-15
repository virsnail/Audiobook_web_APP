
import asyncio
import sys
import os
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# 添加项目根目录到 pythonpath
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import AsyncSessionLocal
from app.models.book import Book
from app.models.user import User
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
    # storage_path 格式: "user_uuid/book_uuid"
    db_book_paths = {book.storage_path for book in db_books}
    
    print(f"\n📚 Total Books in Database: {len(db_books)}")

    # 2. 获取文件系统中的所有书籍目录
    # 结构: books_dir / user_uuid / book_uuid /
    fs_book_paths = set()  # 格式: "user_uuid/book_uuid"
    try:
        for user_dir in os.listdir(books_dir):
            user_path = os.path.join(books_dir, user_dir)
            if not os.path.isdir(user_path):
                continue
            for book_dir in os.listdir(user_path):
                book_path = os.path.join(user_path, book_dir)
                if os.path.isdir(book_path):
                    # 拼接为与 storage_path 相同的格式
                    fs_book_paths.add(f"{user_dir}/{book_dir}")
    except OSError as e:
        print(f"❌ Error accessing media directory: {e}")
        return
        
    print(f"📁 Total Book Directories in Filesystem: {len(fs_book_paths)}")
    
    # 3. 查找数据库有但文件系统没有的 (Orphaned DB Records)
    orphaned_db_records = []
    for book in db_books:
        if book.storage_path not in fs_book_paths:
            # 再次确认物理路径确实不存在
            full_path = os.path.join(books_dir, book.storage_path)
            if not os.path.exists(full_path):
                orphaned_db_records.append(book)

    # 4. 查找文件系统有但数据库没有的 (Orphaned Files)
    orphaned_files = []
    for fs_path in fs_book_paths:
        if fs_path not in db_book_paths:
            orphaned_files.append(fs_path)

    # 5. 检查用户目录归属
    result = await session.execute(select(User.id))
    db_user_ids = {str(row[0]) for row in result.all()}
    
    orphaned_user_dirs = []
    for user_dir in os.listdir(books_dir):
        if os.path.isdir(os.path.join(books_dir, user_dir)):
            if user_dir not in db_user_ids:
                orphaned_user_dirs.append(user_dir)

    # 6. 生成报告
    print("\n" + "=" * 60)
    print("AUDIT REPORT")
    print("=" * 60)
    
    all_ok = True
    
    if orphaned_db_records:
        all_ok = False
        print(f"\n⚠️  {len(orphaned_db_records)} orphaned database records (Missing files):")
        for book in orphaned_db_records:
            print(f"   - [ID: {book.id}] {book.title} (Path: {book.storage_path})")
            
    if orphaned_files:
        all_ok = False
        print(f"\n⚠️  {len(orphaned_files)} orphaned directories (No DB record):")
        for dir_path in orphaned_files:
            full_path = os.path.join(books_dir, dir_path)
            size = sum(
                os.path.getsize(os.path.join(dp, f))
                for dp, _, fnames in os.walk(full_path)
                for f in fnames
            )
            print(f"   - {dir_path} ({size / 1024 / 1024:.1f} MB)")
    
    if orphaned_user_dirs:
        all_ok = False
        print(f"\n⚠️  {len(orphaned_user_dirs)} orphaned user directories (User not in DB):")
        for user_dir in orphaned_user_dirs:
            print(f"   - {user_dir}")
    
    if all_ok:
        print("\n✅ Data is consistent! No issues found.")
                
    print("\n" + "=" * 60)

async def main():
    async with AsyncSessionLocal() as session:
        await audit_data(session)

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
