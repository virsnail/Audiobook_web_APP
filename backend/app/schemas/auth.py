from pydantic import BaseModel, EmailStr, Field
from typing import Optional


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenPayload(BaseModel):
    sub: str  # user id
    exp: int


class EmailCodeRequest(BaseModel):
    email: EmailStr


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=6, max_length=128, description="密码长度 6-128 位")
    nickname: Optional[str] = Field(None, max_length=50, description="昵称最长 50 字符")
    invitation_code: str = Field(..., min_length=1, max_length=20, description="邀请码")
    email_code: str = Field(..., min_length=6, max_length=6, pattern=r'^\d{6}$', description="6 位数字验证码")


class ChangePasswordRequest(BaseModel):
    new_password: str = Field(..., min_length=6, max_length=128, description="新密码长度 6-128 位")
    email_code: str = Field(..., min_length=6, max_length=6, pattern=r'^\d{6}$', description="6 位数字验证码")
