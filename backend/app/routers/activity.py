from fastapi import APIRouter, Depends, BackgroundTasks, Request, Body
from typing import Optional, Dict, Any
from app.utils.deps import get_current_user
from app.models.user import User
from app.services.activity_logger import ActivityLogger
from app.database import AsyncSessionLocal

router = APIRouter(tags=["activity"])

@router.post("/log", summary="记录前端活动")
async def log_frontend_activity(
    background_tasks: BackgroundTasks,
    request: Request,
    action: str = Body(..., embed=True),
    details: Optional[Dict[str, Any]] = Body(None, embed=True),
    current_user: User = Depends(get_current_user)
):
    """
    接收前端发送的用户活动日志
    例如: CHANGE_THEME, CHANGE_FONT_SIZE, etc.
    """
    background_tasks.add_task(
        ActivityLogger.log_activity_background,
        AsyncSessionLocal,
        str(current_user.id),
        action,
        None,
        details,
        request.headers.get("user-agent")
    )
    
    return {"status": "ok"}
