from fastapi import APIRouter, Request, Form, UploadFile, File, Depends, HTTPException
from pydantic import EmailStr
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status
from starlette.concurrency import run_in_threadpool
from sqlalchemy import func, or_, select

from app.users.validators import (
    raise_if_errors, validate_password, validate_phone, validate_username,
)
from app.users.schemas import RegisteredUser, UserData
from app.database import get_session
from app.users.models import User
from app.users.utils import save_avatar, delete_avatar
from app.users.security import hash_password

auth_router = APIRouter(
    prefix="/api/v1/auth",
    tags=["auth"],
)


@auth_router.post(
    "/register",
    status_code=status.HTTP_201_CREATED,
    response_model=RegisteredUser,
    name="Register"
)
async def create_user(
    request: Request,
    username: str = Form(..., min_length=3, max_length=50),
    email: EmailStr = Form(...),
    password1: str = Form(...),
    password2: str = Form(...),
    first_name: str | None = Form(None, max_length=100),
    last_name: str | None = Form(None, max_length=100),
    phone: str | None = Form(None, max_length=13),
    avatar: UploadFile | None = File(None),
    session: AsyncSession = Depends(get_session),
):
    # 0. Normallashtirish
    username = username.strip()
    email = email.strip().lower()
    first_name = (first_name or "").strip() or None
    last_name = (last_name or "").strip() or None
    phone = (phone or "").strip() or None

    # 1. Parollar mosligi
    if password1 != password2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Parollar bir xil emas",
        )

    # 2. Format va parol sodda emasligini tekshirish (bazaga murojaatsiz)
    errors = (
        validate_username(username)
        + validate_phone(phone)
        + validate_password(password1, username, email)
    )
    raise_if_errors(errors)

    # 3. Username yoki email band ekanini tekshirish (katta-kichik harfsiz)
    result = await session.execute(
        select(User).where(
            or_(
                func.lower(User.email) == email,
                func.lower(User.username) == username.lower(),
            )
        )
    )
    existing_user = result.scalars().first()
    if existing_user:
        detail = (
            "Bu email bilan foydalanuvchi allaqachon mavjud"
            if existing_user.email.lower() == email
            else "Bu username band"
        )
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)

    # 4. Parolni hashlash (bcrypt CPU'ni band qiladi, shuning uchun alohida thread'da)
    hashed_password = await run_in_threadpool(hash_password, password1)

    # 5. Rasmni media/avatars/ ga saqlash (eng oxirida, hamma tekshiruvdan keyin)
    avatar_path = await save_avatar(avatar) if avatar and avatar.filename else None

    # 6. Userni bazaga yozish
    new_user = User(
        username=username,
        email=email,
        password=hashed_password,
        first_name=first_name,
        last_name=last_name,
        phone=phone,
        avatar=avatar_path,
    )
    try:
        session.add(new_user)
        await session.commit()
    except IntegrityError:
        await session.rollback()
        delete_avatar(avatar_path)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username yoki email band",
        )
    except Exception:
        await session.rollback()
        delete_avatar(avatar_path)
        raise
    await session.refresh(new_user)

    # 7. Javobda avatar to'liq URL bilan
    avatar_url = (
        str(request.url_for("media", path=new_user.avatar))
        if new_user.avatar
        else None
    )

    return RegisteredUser(
        success=True,
        message="Foydalanuvchi muvaffaqiyatli ro'yxatdan o'tdi",
        data=UserData(
            id=new_user.id,
            username=new_user.username,
            email=new_user.email,
            first_name=new_user.first_name,
            last_name=new_user.last_name,
            phone=new_user.phone,
            avatar=avatar_url,
        ),
    )