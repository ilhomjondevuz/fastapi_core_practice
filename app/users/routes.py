import hmac
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, BackgroundTasks, Request, Form, UploadFile, File, Depends, HTTPException
from pydantic import EmailStr
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status
from starlette.concurrency import run_in_threadpool
from sqlalchemy import delete, func, or_, select

from app.users.validators import (
    raise_if_errors, validate_password, validate_phone, validate_username,
)
from app.users.schemas import (
    RegisteredUser, UserData, LoginUser, LoginResponse,
    MessageResponse, ChangePasswordRequest,
    ForgotPasswordRequest, ForgotPasswordResponse,
    VerifyResetCodeRequest, VerifyResetCodeResponse, ResetPasswordRequest,
)
from app.database import get_session
from app.users.models import User, PasswordResetCode
from app.users.utils import save_avatar, delete_avatar
from app.users.security import (
    hash_password, verify_password, decode_token, DUMMY_HASH,
    create_access_token, create_refresh_token,
    generate_reset_code, hash_reset_code,
    create_reset_session_token, create_reset_confirm_token,
)
from app.users.mail import send_reset_email
from app.dependencies import get_current_user
from app.core.config import settings

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

@auth_router.post(
    "/login",
    status_code=status.HTTP_200_OK,
    response_model=LoginResponse,
    name="Login",
)
async def login_user(
    request: Request,
    user: LoginUser,
    session: AsyncSession = Depends(get_session),
):
    # 1. Normallashtirish
    identifier = user.username_or_email.strip().lower()

    # 2. Username yoki email bo'yicha qidirish (katta-kichik harfsiz)
    result = await session.execute(
        select(User).where(
            or_(
                func.lower(User.email) == identifier,
                func.lower(User.username) == identifier,
            )
        )
    )
    db_user = result.scalars().first()

    # 3. Parolni tekshirish (bcrypt og'ir, shuning uchun thread'da)
    password_ok = await run_in_threadpool(
        verify_password,
        user.password,
        db_user.password if db_user else DUMMY_HASH,
    )

    if not db_user or not password_ok:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Username/email yoki parol noto'g'ri",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not db_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Akkaunt faol emas",
        )

    # 4. Tokenlar
    access_token = create_access_token(db_user.id)
    refresh_token = create_refresh_token(db_user.id)

    # 5. Avatar to'liq URL bilan
    avatar_url = (
        str(request.url_for("media", path=db_user.avatar))
        if db_user.avatar
        else None
    )

    return LoginResponse(
        success=True,
        message="Muvaffaqiyatli kirdingiz",
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        data=UserData(
            id=db_user.id,
            username=db_user.username,
            email=db_user.email,
            first_name=db_user.first_name,
            last_name=db_user.last_name,
            phone=db_user.phone,
            avatar=avatar_url,
        ),
    )


@auth_router.post(
    "/forgot-password",
    status_code=status.HTTP_200_OK,
    response_model=ForgotPasswordResponse,
    name="Forgot password",
)
async def forgot_password(
    data: ForgotPasswordRequest,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
):
    """1-qadam: emailga 6 xonali kod yuboradi va 1-tokenni (reset_session) qaytaradi."""
    email = data.email.strip().lower()
    result = await session.execute(
        select(User).where(func.lower(User.email) == email)
    )
    db_user = result.scalars().first()

    reset_id = uuid.uuid4().hex

    if db_user and db_user.is_active:
        code = generate_reset_code()

        # Eski kodlar bekor qilinadi: bitta foydalanuvchida bitta faol kod
        await session.execute(
            delete(PasswordResetCode).where(PasswordResetCode.user_id == db_user.id)
        )
        session.add(
            PasswordResetCode(
                id=reset_id,
                user_id=db_user.id,
                code_hash=hash_reset_code(reset_id, code),
                expires_at=datetime.now(timezone.utc)
                + timedelta(minutes=settings.RESET_TOKEN_EXPIRE_MINUTES),
            )
        )
        await session.commit()

        # Email fonda yuboriladi: javob vaqti user bor-yo'qligini oshkor qilmaydi
        background_tasks.add_task(send_reset_email, db_user.email, code)

    # Email bazada bor-yo'qligidan qat'i nazar bir xil ko'rinishdagi javob.
    # Yo'q email uchun ham token beriladi, lekin uning kodi hech qachon to'g'ri chiqmaydi.
    return ForgotPasswordResponse(
        success=True,
        message="Agar bu email ro'yxatdan o'tgan bo'lsa, tasdiqlash kodi yuborildi",
        reset_token=create_reset_session_token(reset_id),
    )


@auth_router.post(
    "/verify-reset-code",
    status_code=status.HTTP_200_OK,
    response_model=VerifyResetCodeResponse,
    name="Verify reset code",
)
async def verify_reset_code(
    data: VerifyResetCodeRequest,
    session: AsyncSession = Depends(get_session),
):
    """2-qadam: 1-token + emaildagi kod. To'g'ri bo'lsa 2-tokenni (reset_confirm) beradi."""
    invalid = HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Kod noto'g'ri yoki muddati tugagan",
    )

    payload = decode_token(data.reset_token, "reset_session")
    if not payload:
        raise invalid
    reset_id = payload["sub"]

    # FOR UPDATE: bir vaqtda ko'p urinish bilan urinishlar limitini aylanib o'tib bo'lmasin
    result = await session.execute(
        select(PasswordResetCode)
        .where(PasswordResetCode.id == reset_id)
        .with_for_update()
    )
    row = result.scalars().first()
    if not row or row.expires_at <= datetime.now(timezone.utc):
        if row:
            await session.delete(row)
            await session.commit()
        raise invalid

    if row.attempts >= settings.RESET_CODE_MAX_ATTEMPTS:
        await session.delete(row)
        await session.commit()
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Urinishlar soni tugadi, qaytadan kod so'rang",
        )

    if not hmac.compare_digest(row.code_hash, hash_reset_code(reset_id, data.code)):
        row.attempts += 1
        await session.commit()
        raise invalid

    row.verified = True
    await session.commit()

    return VerifyResetCodeResponse(
        success=True,
        message="Kod tasdiqlandi, endi yangi parol o'rnating",
        reset_token=create_reset_confirm_token(reset_id),
    )


@auth_router.post(
    "/reset-password",
    status_code=status.HTTP_200_OK,
    response_model=MessageResponse,
    name="Reset password",
)
async def reset_password(
    data: ResetPasswordRequest,
    session: AsyncSession = Depends(get_session),
):
    """3-qadam: 2-token + yangi parol. Parol o'zgargach shu parol bilan /login qilinadi."""
    if data.new_password1 != data.new_password2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Parollar bir xil emas",
        )

    invalid = HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Sessiya yaroqsiz yoki muddati tugagan, qaytadan boshlang",
    )
    payload = decode_token(data.reset_token, "reset_confirm")
    if not payload:
        raise invalid

    result = await session.execute(
        select(PasswordResetCode)
        .where(PasswordResetCode.id == payload["sub"])
        .with_for_update()
    )
    row = result.scalars().first()
    if (
        not row
        or not row.verified
        or row.expires_at <= datetime.now(timezone.utc)
    ):
        raise invalid

    db_user = await session.get(User, row.user_id)
    if not db_user or not db_user.is_active:
        raise invalid

    raise_if_errors(
        validate_password(data.new_password1, db_user.username, db_user.email)
    )

    db_user.password = await run_in_threadpool(hash_password, data.new_password1)

    # Kod bir martalik: ishlatilgach (va shu foydalanuvchining boshqa kodlari ham) o'chiriladi
    await session.execute(
        delete(PasswordResetCode).where(PasswordResetCode.user_id == db_user.id)
    )
    await session.commit()

    return MessageResponse(success=True, message="Parol muvaffaqiyatli o'zgartirildi")


@auth_router.post(
    "/change-password",
    status_code=status.HTTP_200_OK,
    response_model=MessageResponse,
    name="Change password",
)
async def change_password(
    data: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    old_ok = await run_in_threadpool(
        verify_password, data.old_password, current_user.password
    )
    if not old_ok:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Eski parol noto'g'ri",
        )

    if data.new_password1 != data.new_password2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Yangi parollar bir xil emas",
        )

    if data.new_password1 == data.old_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Yangi parol eskisidan farq qilishi kerak",
        )

    raise_if_errors(
        validate_password(data.new_password1, current_user.username, current_user.email)
    )

    current_user.password = await run_in_threadpool(hash_password, data.new_password1)
    await session.commit()

    return MessageResponse(success=True, message="Parol muvaffaqiyatli o'zgartirildi")