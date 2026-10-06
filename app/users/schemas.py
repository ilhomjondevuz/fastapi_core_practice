from pydantic import BaseModel


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