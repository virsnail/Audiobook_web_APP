import secrets
import string
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from app.config import settings
from app.database import engine, Base, AsyncSessionLocal
from app.models.user import User, InvitationCode
from app.routers import auth_router, books_router
from app.utils.security import get_password_hash


async def create_admin_user():
    """创建管理员账户和初始邀请码"""
    if not settings.ADMIN_EMAIL or not settings.ADMIN_PASSWORD:
        return
    
    async with AsyncSessionLocal() as db:
        # 检查管理员是否已存在
        result = await db.execute(select(User).where(User.email == settings.ADMIN_EMAIL))
        admin = result.scalar_one_or_none()
        
        if not admin:
            admin = User(
                email=settings.ADMIN_EMAIL,
                password_hash=get_password_hash(settings.ADMIN_PASSWORD),
                nickname="Admin",
                is_admin=True,
            )
            db.add(admin)
            await db.commit()
            await db.refresh(admin)
            print(f"管理员账户已创建: {settings.ADMIN_EMAIL}")
            
            # 创建初始邀请码
            codes = []
            for _ in range(settings.INITIAL_INVITATION_CODES):
                code = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(8))
                invitation = InvitationCode(
                    code=code,
                    created_by=admin.id,
                )
                db.add(invitation)
                codes.append(code)
            
            await db.commit()
            print(f"初始邀请码: {', '.join(codes)}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时
    async with engine.begin() as conn:
        if settings.DEBUG:
            await conn.run_sync(Base.metadata.create_all)
    
    await create_admin_user()
    
    yield
    
    # 关闭时
    await engine.dispose()


app = FastAPI(
    title=settings.APP_NAME,
    description="音频书籍同步阅读器 API",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 路由
app.include_router(auth_router, prefix="/auth", tags=["认证"])
app.include_router(books_router, prefix="/books", tags=["书籍"])


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


@app.get("/")
async def root():
    return {"message": "AudioBook Reader API", "version": "1.0.0"}
