from pydantic import BaseModel


class CreateUser(BaseModel):
    username: str
    email: str
    password1: str
    password2: str

class CreatedUser(BaseModel):
    success: bool
    message: str
    data: CreateUser