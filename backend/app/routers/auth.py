import secrets
import random
import string
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models.user import User, InvitationCode, EmailVerification
from app.schemas.auth import Token, EmailCodeRequest, RegisterRequest
from app.schemas.user import UserLogin, UserResponse
from app.utils.security import verify_password, get_password_hash, create_access_token
from app.utils.deps import get_current_user
from app.config import settings

router = APIRouter()


def generate_email_code() -> str:
    """生成6位数字验证码"""
    return ''.join(random.choices(string.digits, k=6))


def generate_invitation_code() -> str:
    """生成邀请码"""
    return secrets.token_urlsafe(settings.INVITATION_CODE_LENGTH)


@router.post("/send-code", summary="发送邮箱验证码")
async def send_email_code(
    request: EmailCodeRequest,
    db: AsyncSession = Depends(get_db)
):
    """发送邮箱验证码"""
    # 检查是否已有未过期的验证码
    result = await db.execute(
        select(EmailVerification)
        .where(EmailVerification.email == request.email)
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
        email=request.email,
        code=code,
        expires_at=datetime.utcnow() + timedelta(minutes=10)
    )
    db.add(verification)
    await db.commit()
    
    # TODO: 实际发送邮件（开发环境直接返回验证码）
    if settings.DEBUG:
        return {"message": f"验证码已发送（开发模式）: {code}"}
    
    # 生产环境需要实现邮件发送
    # await send_email(request.email, "验证码", f"您的验证码是: {code}")
    
    return {"message": "验证码已发送到您的邮箱"}


@router.post("/register", response_model=Token, summary="用户注册")
async def register(
    request: RegisterRequest,
    db: AsyncSession = Depends(get_db)
):
    """用户注册（需要邀请码和邮箱验证码）"""
    # 检查邮箱是否已注册
    result = await db.execute(select(User).where(User.email == request.email))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="该邮箱已被注册"
        )
    
    # 验证邀请码
    result = await db.execute(
        select(InvitationCode)
        .where(InvitationCode.code == request.invitation_code)
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
        .where(EmailVerification.email == request.email)
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
    
    # 创建用户
    user = User(
        email=request.email,
        password_hash=get_password_hash(request.password),
        nickname=request.nickname or request.email.split("@")[0]
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
async def login(
    request: UserLogin,
    db: AsyncSession = Depends(get_db)
):
    """用户登录"""
    result = await db.execute(select(User).where(User.email == request.email))
    user = result.scalar_one_or_none()
    
    if not user or not verify_password(request.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="邮箱或密码错误"
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="账户已被禁用"
        )
    
    access_token = create_access_token(str(user.id))
    return Token(access_token=access_token)


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
