from pydantic import BaseModel, EmailStr
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
    password: str
    nickname: Optional[str] = None
    invitation_code: str
    email_code: str


class ChangePasswordRequest(BaseModel):
    new_password: str
    email_code: str
