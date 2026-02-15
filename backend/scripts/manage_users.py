
import asyncio
import sys
import os
import shutil
import argparse
from sqlalchemy import select, delete, text
from sqlalchemy.ext.asyncio import AsyncSession

# 添加项目根目录到 pythonpath
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import AsyncSessionLocal, engine
from app.models.user import User, InvitationCode, EmailVerification
from app.models.book import Book, BookShare, ReadingProgress
from app.models.activity import UserActivityLog
from app.config import settings


async def _table_exists(session: AsyncSession, table_name: str) -> bool:
    """检查数据库中是否存在指定的表"""
    result = await session.execute(
        text("SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = :t)"),
        {"t": table_name}
    )
    return result.scalar()


async def _safe_delete(session: AsyncSession, stmt, label: str):
    """
    安全执行 DELETE 语句：使用 SAVEPOINT 隔离，
    失败时只回滚到 SAVEPOINT 而不影响外层事务。
    """
    try:
        async with session.begin_nested():
            r = await session.execute(stmt)
            print(f"   - Deleted {r.rowcount} {label}")
            return r.rowcount
    except Exception as e:
        print(f"   - Skip {label}: {e}")
        return 0


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
    
    # 1. 删除活动日志（表可能不存在）
    if await _table_exists(session, "user_activity_logs"):
        await _safe_delete(
            session,
            delete(UserActivityLog).where(UserActivityLog.user_id == user_id),
            "activity logs"
        )
    else:
        print("   - Skip activity logs: table does not exist")

    # 2. 删除阅读进度
    await _safe_delete(
        session,
        delete(ReadingProgress).where(ReadingProgress.user_id == user_id),
        "reading progress records"
    )

    # 3. 删除书籍分享（作为分享者或被分享者）
    try:
        async with session.begin_nested():
            # 先获取该用户的书籍 ID
            book_result = await session.execute(select(Book.id).where(Book.owner_id == user_id))
            book_ids = [row[0] for row in book_result.all()]
            
            if book_ids:
                r = await session.execute(delete(BookShare).where(BookShare.book_id.in_(book_ids)))
                print(f"   - Deleted {r.rowcount} book shares (as owner)")
            
            r = await session.execute(delete(BookShare).where(BookShare.shared_to == user_id))
            print(f"   - Deleted {r.rowcount} book shares (as recipient)")
    except Exception as e:
        print(f"   - Skip book shares: {e}")

    # 4. 删除书籍（含物理文件）
    try:
        async with session.begin_nested():
            result = await session.execute(select(Book).where(Book.owner_id == user_id))
            books = result.scalars().all()
            
            for book in books:
                full_path = os.path.join(settings.MEDIA_PATH, "books", book.storage_path)
                if os.path.exists(full_path):
                    shutil.rmtree(full_path, ignore_errors=True)
                    print(f"   - Deleted book files: {book.title} ({full_path})")
                else:
                    print(f"   - Book files not found: {book.title} ({full_path})")
            
            await session.execute(delete(Book).where(Book.owner_id == user_id))
            print(f"   - Deleted {len(books)} books from database")
    except Exception as e:
        print(f"   - Error deleting books: {e}")

    # 5. 删除用户（重新查询以确保对象仍在 session 中）
    try:
        async with session.begin_nested():
            result = await session.execute(select(User).where(User.id == user_id))
            user = result.scalar_one_or_none()
            if user:
                await session.delete(user)
        print(f"   - User record marked for deletion")
    except Exception as e:
        print(f"   - Error deleting user record: {e}")

    # 6. 提交所有更改（步骤 1-5 中 SAVEPOINT 成功的部分）
    try:
        await session.commit()
        print(f"✅ User {email} and associated data deleted.")
    except Exception as e:
        await session.rollback()
        print(f"❌ Failed to commit changes: {e}")


async def wipe_all(session: AsyncSession):
    """清空所有用户和书籍数据"""
    print("⚠️  WARNING: THIS WILL DELETE ALL USERS AND BOOKS!")
    confirm = input("Type 'DELETE_ALL' to confirm: ")
    if confirm != "DELETE_ALL":
        print("Operation cancelled.")
        return

    # 按依赖顺序删除（每步用 SAVEPOINT 隔离，表不存在也不会中断）
    if await _table_exists(session, "user_activity_logs"):
        await _safe_delete(session, delete(UserActivityLog), "activity logs")
    else:
        print("   - Skip activity logs: table does not exist")

    await _safe_delete(session, delete(ReadingProgress), "reading progress records")
    await _safe_delete(session, delete(BookShare), "book shares")
    await _safe_delete(session, delete(Book), "books")
    await _safe_delete(session, delete(EmailVerification), "email verifications")
    await _safe_delete(session, delete(InvitationCode), "invitation codes")
    await _safe_delete(session, delete(User), "users")
    
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
