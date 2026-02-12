from fastapi import APIRouter, Depends, BackgroundTasks, Request, Body, HTTPException, status
from typing import Optional, Dict, Any
import json
from app.utils.deps import get_current_user
from app.models.user import User
from app.services.activity_logger import ActivityLogger
from app.database import AsyncSessionLocal

router = APIRouter(tags=["activity"])

# 允许的活动类型白名单
ALLOWED_ACTIONS = {
    "CHANGE_THEME", "CHANGE_FONT_SIZE", "TOGGLE_DARK_MODE",
    "PLAY_AUDIO", "PAUSE_AUDIO", "SEEK_AUDIO", "CHANGE_SPEED",
    "OPEN_BOOK", "CLOSE_BOOK", "SCROLL_CHAPTER",
    "UPLOAD_BOOK", "DELETE_BOOK", "SHARE_BOOK",
    "LOGIN", "LOGOUT", "PAGE_VIEW",
}
MAX_DETAILS_SIZE = 4096  # details JSON 最大字节数


@router.post("/log", summary="记录前端活动")
async def log_frontend_activity(
    background_tasks: BackgroundTasks,
    request: Request,
    action: str = Body(..., embed=True, min_length=1, max_length=50),
    details: Optional[Dict[str, Any]] = Body(None, embed=True),
    current_user: User = Depends(get_current_user)
):
    """
    接收前端发送的用户活动日志
    例如: CHANGE_THEME, CHANGE_FONT_SIZE, etc.
    """
    # 安全：验证 action 类型
    if action not in ALLOWED_ACTIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"不支持的活动类型：{action}"
        )
    
    # 安全：限制 details 大小
    if details is not None:
        details_size = len(json.dumps(details, default=str))
        if details_size > MAX_DETAILS_SIZE:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"details 数据过大（{details_size} 字节），最大允许 {MAX_DETAILS_SIZE} 字节"
            )
    
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
