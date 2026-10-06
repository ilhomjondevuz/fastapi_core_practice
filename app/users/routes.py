from fastapi import APIRouter, HTTPException
from sqlalchemy import select, or_
from starlette import status

from app.database import async_session
from app.users.models import User
from app.users.schemas import CreatedUser

auth_router = APIRouter(
    prefix="/api/v1",
    tags=["auth"],
)

@auth_router.get("/me")
async def read_users_me():
    return {"my_info": "FIO: Test"}

@auth_router.post('/register', status_code=status.HTTP_201_CREATED, response_model=CreatedUser)
async def create_user(user: CreatedUser):
    result = await async_session.execute(select(User).where(or_(User.email == user.email), or_(User.username == user.username)))
    if user['password1'] != user['password2']:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,)