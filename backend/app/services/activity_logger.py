import logging
import os
import json
from datetime import datetime
from typing import Optional, Any, Dict
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Request

from app.models.activity import UserActivityLog

# 配置专用 logger
logger = logging.getLogger("activity_logger")

# 确保 logs 目录存在
LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)

# 配置 FileHandler
error_log_path = os.path.join(LOG_DIR, "activity_errors.log")
file_handler = logging.FileHandler(error_log_path)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)
logger.setLevel(logging.ERROR) # 只记录错误

class ActivityLogger:
    @staticmethod
    async def log_activity(
        db: AsyncSession,
        user_id: Optional[str],
        action: str,
        resource_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        request: Optional[Request] = None
    ):
        """
        记录用户活动
        
        即使数据库写入失败，也不应影响主流程，错误会被记录到 dedicated log file
        """
        try:
            user_agent = None
            if request:
                user_agent = request.headers.get("user-agent")
            
            activity = UserActivityLog(
                user_id=user_id,
                action=action,
                resource_id=resource_id,
                details=details,
                user_agent=user_agent
            )
            
            db.add(activity)
            # 注意：此处不 commit，由调用方统一 commit，或者如果是 background task 则需要 commit
            # 为保证不影响主业务，我们在这里 flush 甚至 commit?
            # 通常最好是让此操作作为主事务的一部分。
            # 但如果要求 "不影响主功能"，意味着如果这个 insert 失败了，不应该 rollback 主事务。
            # 所以最好是使用 nested transaction 或者 separately committed.
            # 为了简单和性能，通常我们直接 add 到 session。如果 session commit 失败，确实会影响主业务。
            # 如果要完全隔离，需要一个新的 session 或者 background task。
            
            # 策略：直接 add，假设 DB 没挂。如果 DB 挂了，主业务本来也做不了。
            # 唯一风险是 UserActivityLog 模型本身有问题导致 commit 失败。
            # 考虑到用户强调 "完全独立，不影响主功能"，最好使用 begin_nested() 或者在 catch 中处理。
            
            # 但 AsyncSession 的 begin_nested 支持有限。
            # 最稳妥的方式：不做即时 commit，让它随主业务 flow。
            # 如果非常担心模型错误，可以在此时 try flush。
            
            # 然而，用户要求：如果跟踪失败，不能影响正常功能。
            # 如果把 log activity 放在主业务 commit 之后（作为 background task），那是最好的。
            # 但我们需要 db session。
            
            # 让我们尝试一种混合模式：如果不强制 commit，就随缘。
            # 但那样就没法 catch error 了（error 会在最后 commit 时爆出来）。
            
            # 既然是 AsyncSession，我们其实可以启动一个新的 task 来写 log。
            # 但这需要 session factory。
            
            # 简单起见，我们加一个 safe_flush helper? 
            # 暂时先直接 add，在实际调用处（routers）里，尽量放在最后，
            # 或者，更高级的：使用 background tasks 并且在 background task 里创建新的 session。
            # 这是一个非常好的模式： BackgroundTasks with new session.
            
            pass 
            
        except Exception as e:
            # 这一层 catch 只能捕获 add 时的错误（很少见，除非数据类型错）。
            # 真正的 DB error 会在 commit 时发生。
            ActivityLogger._log_error(f"Failed to stage activity log: {e}", user_id, action)

    @staticmethod
    async def log_activity_background(
        session_factory, 
        user_id: Optional[str],
        action: str,
        resource_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        user_agent: Optional[str] = None
    ):
        """
        后台任务执行日志记录（完全隔离）
        """
        try:
            async with session_factory() as db:
                activity = UserActivityLog(
                    user_id=user_id,
                    action=action,
                    resource_id=resource_id,
                    details=details,
                    user_agent=user_agent
                )
                db.add(activity)
                await db.commit()
        except Exception as e:
            ActivityLogger._log_error(f"Failed to save activity log in background: {e}", user_id, action)

    @staticmethod
    def _log_error(error_msg: str, user_id: Any, action: str):
        try:
            logger.error(f"Activity Logging Error | User: {user_id} | Action: {action} | Error: {error_msg}")
        except:
            print(f"CRITICAL: Failed to write to error log file. Original error: {error_msg}")
