from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from app.database import get_session
from app.users.models import User
from app.users.security import decode_token

bearer_scheme = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    session: AsyncSession = Depends(get_session),
) -> User:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token yaroqsiz yoki muddati tugagan",
        headers={"WWW-Authenticate": "Bearer"},
    )
    payload = decode_token(credentials.credentials, "access")
    if not payload:
        raise unauthorized
    try:
        user_id = int(payload["sub"])
    except (KeyError, ValueError):
        raise unauthorized

    user = await session.get(User, user_id)
    if not user or not user.is_active:
        raise unauthorized
    return user

async def get_current_staff(
    current_user: User = Depends(get_current_user),
) -> User:
    if not current_user.is_staff:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Faqat staff foydalanuvchilar uchun",
        )
    return current_user