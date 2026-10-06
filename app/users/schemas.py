from pydantic import BaseModel
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