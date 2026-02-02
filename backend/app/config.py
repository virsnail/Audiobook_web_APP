from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import List


class Settings(BaseSettings):
    """应用配置"""
    
    APP_NAME: str = "AudioBook Reader"
    DEBUG: bool = False
    
    # 数据库
    DATABASE_URL: str
    
    # 安全
    SECRET_KEY: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 天
    ALGORITHM: str = "HS256"
    
    # CORS
    CORS_ORIGINS: str = ""
    
    @property
    def cors_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]
    
    # 媒体
    MEDIA_PATH: str = "/app/media"
    MAX_UPLOAD_SIZE: int = 500 * 1024 * 1024  # 500MB
    ALLOWED_AUDIO_TYPES: List[str] = ["audio/mpeg", "audio/wav", "audio/ogg"]
    
    # 邮件
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = ""
    
    # 管理员
    ADMIN_EMAIL: str = ""
    ADMIN_PASSWORD: str = ""
    
    # 邀请码
    INVITATION_CODE_LENGTH: int = 8
    INITIAL_INVITATION_CODES: int = 5
    
    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
