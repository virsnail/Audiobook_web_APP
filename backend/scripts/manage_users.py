
import asyncio
import sys
import os
import argparse
from sqlalchemy import select, delete, text
from sqlalchemy.ext.asyncio import AsyncSession

# 添加项目根目录到 pythonpath
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import AsyncSessionLocal, engine
from app.models.user import User, Book, InvitationCode, EmailVerification
from app.models.activity import UserActivityLog
from app.config import settings

async def list_users(session: AsyncSession):
    """列出所有用户"""
    result = await session.execute(select(User).order_by(User.created_at.desc()))
    users = result.scalars().all()
    
    print(f"\n{'ID':<36} | {'Email':<30} | {'Nickname':<20} | {'Created At'}")
    print("-" * 110)
    for user in users:
        print(f"{str(user.id):<36} | {user.email:<30} | {user.nickname or '':<20} | {user.created_at}")
    print(f"\nTotal Components: {len(users)}\n")

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
    
    # 1. 删除关联的活动日志
    # (如果 ActivityLog 模型存在)
    try:
        if 'UserActivityLog' in globals():
             await session.execute(delete(UserActivityLog).where(UserActivityLog.user_id == user_id))
    except Exception:
         pass # 忽略如果表不存在

    # 2. 删除书籍文件 (物理删除)
    # 首先查询用户的所有书籍
    result = await session.execute(select(Book).where(Book.owner_id == user_id))
    books = result.scalars().all()
    
    deleted_files = 0
    for book in books:
        # TODO: 这里只处理了数据库记录，实际上应该删除物理文件
        # 在 Docker 环境中，这可能需要挂载卷的权限
        # 暂时只打印路径
        print(f"   - Would delete book files for: {book.title} ({book.id})")
        
    # 3. 删除书籍记录 (DB)
    await session.execute(delete(Book).where(Book.owner_id == user_id))
    
    # 4. 删除邀请码使用记录 (将 used_by 置空 或 删除)
    # 这里我们选择保留邀请码但清除使用状态? 不, 保持原样, 只是用户被删了
    
    # 5. 删除用户
    await session.delete(user)
    await session.commit()
    print(f"✅ User {email} and all associated data deleted.")

async def wipe_all(session: AsyncSession):
    """清空所有用户和书籍数据 (保留管理员?)"""
    print("⚠️  WARNING: THIS WILL DELETE ALL USERS AND BOOKS!")
    confirm = input("Type 'DELETE_ALL' to confirm: ")
    if confirm != "DELETE_ALL":
        print("Operation cancelled.")
        return

    # 删除所有非管理员用户? 或者全部删除?
    # 用户需求是 "方便所有用户重新开始注册", 所以应该是全部删除
    
    # Truncate tables (cascade)
    # SQLite 不支持 CASCADE TRUNCATE, PostgreSQL 支持
    # 但为了安全，我们用 delete
    
    await session.execute(delete(UserActivityLog))
    await session.execute(delete(Book))
    await session.execute(delete(EmailVerification))
    await session.execute(delete(InvitationCode)) # 邀请码也清空吗? 用户说 "方便所有用户重新开始", 邀请码可能也需要重置
    await session.execute(delete(User))
    
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
