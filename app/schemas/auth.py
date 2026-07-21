import re

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.schemas.user import UserOut


class LoginRequest(BaseModel):
    username: str
    password: str


class RegisterRequest(BaseModel):
    """Schema riêng cho đăng ký công khai — KHÔNG có trường `role` để chống
    leo quyền; role được gán cứng là 'reader' ở tầng service (mục 3.2b)."""

    username: str = Field(min_length=3, max_length=100)
    email: EmailStr
    full_name: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=8)
    phone: str | None = None
    address: str | None = None

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        if not re.search(r"[A-Z]", v):
            raise ValueError("Mật khẩu phải có ít nhất một chữ hoa")
        if not re.search(r"[a-z]", v):
            raise ValueError("Mật khẩu phải có ít nhất một chữ thường")
        if not re.search(r"\d", v):
            raise ValueError("Mật khẩu phải có ít nhất một chữ số")
        return v


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    expires_in: int
    user: UserOut
