
import asyncio
import sys
import os
import argparse
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

# 添加项目根目录到 pythonpath
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import AsyncSessionLocal, engine
from app.models.user import User, InvitationCode, EmailVerification
from app.models.book import Book, BookShare, ReadingProgress
from app.models.activity import UserActivityLog
from app.config import settings

async def list_users(session: AsyncSession):
    """列出所有用户"""
    result = await session.execute(select(User).order_by(User.created_at.desc()))
    users = result.scalars().all()
    
    print(f"\n{'ID':<36} | {'Email':<30} | {'Nickname':<20} | {'Admin':<6} | {'Created At'}")
    print("-" * 120)
    for user in users:
        print(f"{str(user.id):<36} | {user.email:<30} | {user.nickname or '':<20} | {'Yes' if user.is_admin else 'No':<6} | {user.created_at}")
    print(f"\nTotal Users: {len(users)}\n")

async def delete_user(session: AsyncSession, email: str):
    """删除特定用户及其所有数据"""
    # 查找用户
    result = await session.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    
    if not user:
        print(f"❌ User not found: {email}")
        return

    user_id = user.id
    print(f"⚠️  Deleting user: {email} ({user_id})")
    
    # 1. 删除活动日志
    try:
        r = await session.execute(delete(UserActivityLog).where(UserActivityLog.user_id == user_id))
        print(f"   - Deleted {r.rowcount} activity logs")
    except Exception as e:
        print(f"   - Skip activity logs: {e}")

    # 2. 删除阅读进度
    try:
        r = await session.execute(delete(ReadingProgress).where(ReadingProgress.user_id == user_id))
        print(f"   - Deleted {r.rowcount} reading progress records")
    except Exception as e:
        print(f"   - Skip reading progress: {e}")

    # 3. 删除书籍分享（作为分享者或被分享者）
    try:
        # 先获取该用户的书籍 ID
        book_result = await session.execute(select(Book.id).where(Book.owner_id == user_id))
        book_ids = [row[0] for row in book_result.all()]
        
        if book_ids:
            r = await session.execute(delete(BookShare).where(BookShare.book_id.in_(book_ids)))
            print(f"   - Deleted {r.rowcount} book shares (as owner)")
        
        r = await session.execute(delete(BookShare).where(BookShare.shared_to_id == user_id))
        print(f"   - Deleted {r.rowcount} book shares (as recipient)")
    except Exception as e:
        print(f"   - Skip book shares: {e}")

    # 4. 删除书籍（含物理文件警告）
    result = await session.execute(select(Book).where(Book.owner_id == user_id))
    books = result.scalars().all()
    
    for book in books:
        full_path = os.path.join(settings.MEDIA_PATH, "books", book.storage_path)
        if os.path.exists(full_path):
            import shutil
            shutil.rmtree(full_path, ignore_errors=True)
            print(f"   - Deleted book files: {book.title} ({full_path})")
        else:
            print(f"   - Book files not found: {book.title} ({full_path})")
    
    await session.execute(delete(Book).where(Book.owner_id == user_id))
    print(f"   - Deleted {len(books)} books from database")
    
    # 5. 删除用户
    await session.delete(user)
    await session.commit()
    print(f"✅ User {email} and all associated data deleted.")

async def wipe_all(session: AsyncSession):
    """清空所有用户和书籍数据"""
    print("⚠️  WARNING: THIS WILL DELETE ALL USERS AND BOOKS!")
    confirm = input("Type 'DELETE_ALL' to confirm: ")
    if confirm != "DELETE_ALL":
        print("Operation cancelled.")
        return

    # 按依赖顺序删除
    r = await session.execute(delete(UserActivityLog))
    print(f"   - Deleted {r.rowcount} activity logs")
    
    r = await session.execute(delete(ReadingProgress))
    print(f"   - Deleted {r.rowcount} reading progress records")
    
    r = await session.execute(delete(BookShare))
    print(f"   - Deleted {r.rowcount} book shares")
    
    r = await session.execute(delete(Book))
    print(f"   - Deleted {r.rowcount} books")
    
    r = await session.execute(delete(EmailVerification))
    print(f"   - Deleted {r.rowcount} email verifications")
    
    r = await session.execute(delete(InvitationCode))
    print(f"   - Deleted {r.rowcount} invitation codes")
    
    r = await session.execute(delete(User))
    print(f"   - Deleted {r.rowcount} users")
    
    await session.commit()
    print("✅ All users and data wiped successfully.")

async def main():
    parser = argparse.ArgumentParser(description="User Management Tool")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # List command
    subparsers.add_parser("list", help="List all users")
    
    # Delete command
    del_parser = subparsers.add_parser("delete", help="Delete a specific user")
    del_parser.add_argument("email", help="Email of the user to delete")
    
    # Wipe command
    subparsers.add_parser("wipe", help="Wipe ALL users and data")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return

    async with AsyncSessionLocal() as session:
        if args.command == "list":
            await list_users(session)
        elif args.command == "delete":
            await delete_user(session, args.email)
        elif args.command == "wipe":
            await wipe_all(session)

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
