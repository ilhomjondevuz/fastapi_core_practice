from pydantic import BaseModel, Field
from pydantic import EmailStr


class UserData(BaseModel):
    id: int
    username: str
    email: str
    first_name: str | None = None
    last_name: str | None = None
    phone: str | None = None
    avatar: str | None = None  # bu yerda to'liq URL qaytadi


class RegisteredUser(BaseModel):
    success: bool
    message: str
    data: UserData

class LoginUser(BaseModel):
    username_or_email: str | EmailStr
    password: str

class LoginResponse(BaseModel):
    success: bool
    message: str
    access_token: str
    refresh_token: str
    token_type: str

class MessageResponse(BaseModel):
    success: bool
    message: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ForgotPasswordResponse(BaseModel):
    success: bool
    message: str
    reset_token: str  # 1-token: kodni tekshirishda yuboriladi


class VerifyResetCodeRequest(BaseModel):
    reset_token: str  # 1-token
    code: str = Field(..., pattern=r"^\d{6}$")


class VerifyResetCodeResponse(BaseModel):
    success: bool
    message: str
    reset_token: str  # 2-token: parolni o'zgartirishda yuboriladi


class ResetPasswordRequest(BaseModel):
    reset_token: str  # 2-token
    new_password1: str
    new_password2: str


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password1: str
    new_password2: str

class RefreshTokenIn(BaseModel):
    refresh_token: str

class TokenOut(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

class LogoutIn(BaseModel):
    refresh_token: str

class UserOut(BaseModel):
    id: int
    username: str
    email: EmailStr
    first_name: str | None = None
    last_name: str | None = None
    phone: str | None = None
    avatar: str | None = None      # to'liq URL
    is_verified: bool

class UserUpdate(BaseModel):
    first_name: str | None = Field(None, max_length=50)
    last_name: str | None = Field(None, max_length=50)
    phone: str | None = Field(None, pattern=r"^\+?[0-9]{9,15}$")
    avatar: str | None = None  # URL; fayl yuklash kerak bo'lsa pastga qarang

class VerifyEmailIn(BaseModel):
    token: str

class ResendVerificationIn(BaseModel):
    email: EmailStr