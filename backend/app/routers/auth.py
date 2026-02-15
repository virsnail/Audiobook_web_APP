import secrets
import random
import string
from datetime import datetime, date, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.database import get_db
from app.models.user import User, InvitationCode, EmailVerification
from app.schemas.auth import Token, EmailCodeRequest, RegisterRequest, ChangePasswordRequest, ForgotPasswordRequest
from app.schemas.user import UserLogin, UserResponse
from app.utils.security import verify_password, get_password_hash, create_access_token
from app.utils.deps import get_current_user
from app.config import settings
from app.services.activity_logger import ActivityLogger
from app.database import AsyncSessionLocal

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)

# 安全限制常量
MAX_FAILED_LOGIN_PER_DAY = 15       # 每天最多登录失败次数
MAX_FORGOT_PASSWORD_PER_DAY = 5     # 每天最多找回密码次数


def generate_email_code() -> str:
    """生成6位数字验证码"""
    return ''.join(random.choices(string.digits, k=6))


def generate_invitation_code() -> str:
    """生成邀请码"""
    return secrets.token_urlsafe(settings.INVITATION_CODE_LENGTH)


@router.post("/send-code", summary="发送邮箱验证码")
@limiter.limit("3/minute")  # 每分钟最多 3 次
async def send_email_code(
    body: EmailCodeRequest,
    request: Request,  # slowapi 需要参数名为 request 的 Request 对象
    db: AsyncSession = Depends(get_db)
):
    """发送邮箱验证码"""
    # 检查是否已有未过期的验证码
    result = await db.execute(
        select(EmailVerification)
        .where(EmailVerification.email == body.email)
        .where(EmailVerification.is_used == False)
        .where(EmailVerification.expires_at > datetime.utcnow())
        .order_by(EmailVerification.created_at.desc())
    )
    existing = result.scalar_one_or_none()
    
    if existing and (datetime.utcnow() - existing.created_at).seconds < 60:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="请求过于频繁，请1分钟后再试"
        )
    
    # 生成新验证码
    code = generate_email_code()
    verification = EmailVerification(
        email=body.email,
        code=code,
        expires_at=datetime.utcnow() + timedelta(minutes=10)
    )
    db.add(verification)
    await db.commit()
    
    # TODO: 实际发送邮件（开发环境直接返回验证码）
    if settings.DEBUG:
        return {"message": f"验证码已发送（开发模式）: {code}"}
    
    # 生产环境发送邮件
    try:
        from app.utils.email import send_email
        await send_email(
            body.email, 
            "AudioBook 验证码 / Verification Code", 
            f"""
            <div style="font-family: Arial, sans-serif; padding: 20px; color: #333;">
                <h2>您的验证码是 / Your Verification Code</h2>
                <p style="font-size: 24px; font-weight: bold; color: #4F46E5; letter-spacing: 5px;">{code}</p>
                <p>该验证码将在 10 分钟后过期。请勿泄露给他人。</p>
                <p>This code will expire in 10 minutes. Do not share it with anyone.</p>
            </div>
            """,
            is_html=True
        )
    except Exception as e:
        # 如果发送失败，回滚并报错
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"邮件发送失败，请检查配置或稍后再试: {str(e)}"
        )
    
    return {"message": "验证码已发送到您的邮箱"}


@router.post("/register", response_model=Token, summary="用户注册")
@limiter.limit("5/minute")  # 每分钟最多 5 次注册尝试
async def register(
    body: RegisterRequest,
    request: Request,  # slowapi 需要参数名为 request 的 Request 对象
    db: AsyncSession = Depends(get_db)
):
    """用户注册（需要邀请码和邮箱验证码）"""
    # 检查邮箱是否已注册
    result = await db.execute(select(User).where(User.email == body.email))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="该邮箱已被注册"
        )
    
    # 验证邀请码
    result = await db.execute(
        select(InvitationCode)
        .where(InvitationCode.code == body.invitation_code)
        .where(InvitationCode.is_used == False)
    )
    invitation = result.scalar_one_or_none()
    
    if not invitation:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="邀请码无效或已被使用"
        )
    
    if invitation.expires_at and invitation.expires_at < datetime.utcnow():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="邀请码已过期"
        )
    
    # 验证邮箱验证码
    result = await db.execute(
        select(EmailVerification)
        .where(EmailVerification.email == body.email)
        .where(EmailVerification.code == body.email_code)
        .where(EmailVerification.is_used == False)
        .where(EmailVerification.expires_at > datetime.utcnow())
    )
    verification = result.scalar_one_or_none()
    
    if not verification:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="邮箱验证码无效或已过期"
        )
    
    # 创建用户
    user = User(
        email=body.email,
        password_hash=get_password_hash(body.password),
        nickname=body.nickname or body.email.split("@")[0]
    )
    db.add(user)
    
    # 标记邀请码和验证码已使用
    invitation.current_uses += 1
    if invitation.current_uses >= invitation.max_uses:
        invitation.is_used = True
        invitation.used_by = user.id
    verification.is_used = True
    
    await db.commit()
    await db.refresh(user)
    
    # 生成 token
    access_token = create_access_token(str(user.id))
    return Token(access_token=access_token)


@router.post("/login", response_model=Token, summary="用户登录")
@limiter.limit("20/minute")  # IP 级别限流
async def login(
    body: UserLogin,
    background_tasks: BackgroundTasks,
    request: Request,  # slowapi 需要参数名为 request 的 Request 对象
    db: AsyncSession = Depends(get_db)
):
    """
    用户登录
    
    安全机制：每日最多 15 次错误尝试，超限后当天禁止登录
    """
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()
    
    if not user:
        # 用户不存在：不要透露是邮箱还是密码错误
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="邮箱或密码错误"
        )
    
    # 检查每日登录错误次数限制
    today = date.today()
    if user.failed_login_date == today and user.failed_login_count >= MAX_FAILED_LOGIN_PER_DAY:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"今日登录尝试次数已达上限（{MAX_FAILED_LOGIN_PER_DAY}次），请明天再试"
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="账户已被禁用"
        )
    
    # 验证密码
    if not verify_password(body.password, user.password_hash):
        # 密码错误：更新失败计数
        if user.failed_login_date != today:
            # 新的一天，重置计数
            user.failed_login_count = 1
            user.failed_login_date = today
        else:
            user.failed_login_count += 1
        await db.commit()
        
        remaining = MAX_FAILED_LOGIN_PER_DAY - user.failed_login_count
        if remaining <= 0:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"今日登录尝试次数已达上限（{MAX_FAILED_LOGIN_PER_DAY}次），请明天再试"
            )
        
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"邮箱或密码错误（今日还可尝试 {remaining} 次）"
        )
    
    # 登录成功：重置失败计数
    user.failed_login_count = 0
    user.failed_login_date = None
    await db.commit()
    
    access_token = create_access_token(str(user.id))
    
    # 记录登录活动
    background_tasks.add_task(
        ActivityLogger.log_activity_background,
        AsyncSessionLocal,
        str(user.id),
        "LOGIN",
        None,
        {"email": user.email},
        request.headers.get("user-agent")
    )
    
    return Token(access_token=access_token)


@router.post("/logout", summary="用户退出")
async def logout(
    background_tasks: BackgroundTasks,
    request: Request,
    current_user: User = Depends(get_current_user),
):
    """用户退出登录（记录日志）"""
    background_tasks.add_task(
        ActivityLogger.log_activity_background,
        AsyncSessionLocal,
        str(current_user.id),
        "LOGOUT",
        None,
        None,
        request.headers.get("user-agent")
    )
    return {"message": "Logged out successfully"}

@router.get("/me", response_model=UserResponse, summary="获取当前用户信息")
async def get_me(current_user: User = Depends(get_current_user)):
    """获取当前登录用户信息"""
    return current_user


@router.post("/invitation-codes", summary="生成邀请码（仅管理员）")
async def create_invitation_codes(
    count: int = 1,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """生成邀请码（需要管理员权限）"""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限"
        )
    
    codes = []
    for _ in range(min(count, 10)):  # 最多一次生成10个
        code = InvitationCode(
            code=generate_invitation_code(),
            created_by=current_user.id,
            expires_at=datetime.utcnow() + timedelta(days=30)
        )
        db.add(code)
        codes.append(code.code)
    
    await db.commit()
    return {"codes": codes}


@router.put("/change-password", summary="修改密码")
async def change_password(
    request: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """修改当前用户密码（需邮箱验证码）"""
    # 验证邮箱验证码
    result = await db.execute(
        select(EmailVerification)
        .where(EmailVerification.email == current_user.email)
        .where(EmailVerification.code == request.email_code)
        .where(EmailVerification.is_used == False)
        .where(EmailVerification.expires_at > datetime.utcnow())
    )
    verification = result.scalar_one_or_none()
    
    if not verification:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="邮箱验证码无效或已过期"
        )

    # 修改密码
    current_user.password_hash = get_password_hash(request.new_password)
    
    # 标记验证码已使用
    verification.is_used = True
    
    await db.commit()
    
    return {"message": "密码修改成功"}


@router.post("/forgot-password", summary="忘记密码（通过邮箱找回）")
@limiter.limit("10/minute")  # IP 级别限流
async def forgot_password(
    body: ForgotPasswordRequest,
    request: Request,  # slowapi 需要参数名为 request 的 Request 对象
    db: AsyncSession = Depends(get_db)
):
    """
    忘记密码：通过邮箱验证码重置密码（无需登录）
    
    安全机制：每个账户每天最多尝试 5 次
    """
    # 查找用户
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="该邮箱未注册"
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="账户已被禁用"
        )
    
    # 检查每日找回密码次数限制
    today = date.today()
    if user.forgot_password_date == today and user.forgot_password_count >= MAX_FORGOT_PASSWORD_PER_DAY:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"今日找回密码尝试次数已达上限（{MAX_FORGOT_PASSWORD_PER_DAY}次），请明天再试"
        )
    
    # 更新找回密码计数
    if user.forgot_password_date != today:
        user.forgot_password_count = 1
        user.forgot_password_date = today
    else:
        user.forgot_password_count += 1
    
    # 验证邮箱验证码
    result = await db.execute(
        select(EmailVerification)
        .where(EmailVerification.email == body.email)
        .where(EmailVerification.code == body.email_code)
        .where(EmailVerification.is_used == False)
        .where(EmailVerification.expires_at > datetime.utcnow())
    )
    verification = result.scalar_one_or_none()
    
    if not verification:
        await db.commit()  # 保存计数
        remaining = MAX_FORGOT_PASSWORD_PER_DAY - user.forgot_password_count
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"邮箱验证码无效或已过期（今日还可尝试 {max(0, remaining)} 次）"
        )
    
    # 重置密码
    user.password_hash = get_password_hash(body.new_password)
    # 同时重置登录错误计数
    user.failed_login_count = 0
    user.failed_login_date = None
    
    # 标记验证码已使用
    verification.is_used = True
    
    await db.commit()
    
    return {"message": "密码重置成功，请使用新密码登录"}
