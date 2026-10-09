import hashlib
import hmac
import secrets
import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
from jose import jwt, JWTError

from app.core.config import settings


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def _create_token(subject: str, token_type: str, expires_delta: timedelta) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        "type": token_type,   # "access" yoki "refresh"
        "iat": now,
        "exp": now + expires_delta,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_access_token(user_id: int) -> str:
    return _create_token(
        str(user_id),
        "access",
        timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )


def create_refresh_token(user_id: int) -> str:
    return _create_token(
        str(user_id),
        "refresh",
        timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )


def decode_token(token: str, expected_type: str) -> dict | None:
    """Token yaroqli va turi to'g'ri bo'lsa payload qaytaradi, aks holda None."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:
        return None
    if payload.get("type") != expected_type:
        return None
    return payload

# ---------- Parolni tiklash (email kodi bilan) ----------

def generate_reset_code() -> str:
    """6 xonali tasodifiy kod (secrets: kriptografik xavfsiz)."""
    return f"{secrets.randbelow(10**6):06d}"


def hash_reset_code(reset_id: str, code: str) -> str:
    """Kodni bazada ochiq saqlamaymiz: HMAC(SECRET_KEY, reset_id:code)."""
    return hmac.new(
        settings.SECRET_KEY.encode(),
        f"{reset_id}:{code}".encode(),
        hashlib.sha256,
    ).hexdigest()


def create_reset_session_token(reset_id: str) -> str:
    """1-token: /forgot-password dan keyin beriladi, faqat kodni tekshirishga yaraydi."""
    return _create_token(
        reset_id, "reset_session", timedelta(minutes=settings.RESET_TOKEN_EXPIRE_MINUTES)
    )


def create_reset_confirm_token(reset_id: str) -> str:
    """2-token: kod to'g'ri bo'lgandan keyin beriladi, faqat parolni o'zgartirishga yaraydi."""
    return _create_token(
        reset_id, "reset_confirm", timedelta(minutes=settings.RESET_TOKEN_EXPIRE_MINUTES)
    )


# Foydalanuvchi topilmaganda ham vaqt bir xil ketishi uchun (timing attack'dan himoya)
DUMMY_HASH = hash_password("dummy-password")

def _make_token(sub, token_type: str, expires: timedelta) -> str:
    payload = {
        "sub": str(sub),
        "type": token_type,
        "jti": uuid.uuid4().hex,
        "exp": datetime.now(timezone.utc) + expires,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

def create_refresh_token(user_id) -> str:
    return _make_token(user_id, "refresh", timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS))

def create_verify_token(user_id) -> str:
    return _make_token(user_id, "verify", timedelta(hours=settings.VERIFY_TOKEN_EXPIRE_HOURS))