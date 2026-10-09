import uuid

import bcrypt
from datetime import datetime, timedelta, timezone

from environs import Env
from jose import jwt, JWTError

from app.users.security import hash_password
from app.core.config import settings

env = Env()
env.read_env()

SECRET_KEY = env.str("SECRET_KEY")
ALGORITHM = "HS256"


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def create_access_token(data: dict, expires_minutes: int = 60) -> str:
    payload = data | {"exp": datetime.now(timezone.utc) + timedelta(minutes=expires_minutes)}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        return None


# Foydalanuvchi topilmaganda ham vaqt bir xil ketishi uchun (timing attack'dan himoya)
DUMMY_HASH = hash_password("dummy-password")

def create_token(sub: str, token_type: str, expires: timedelta) -> tuple[str, str]:
    jti = uuid.uuid4().hex
    payload = {
        "sub": sub,
        "type": token_type,          # access | refresh | verify
        "jti": jti,
        "exp": datetime.now(timezone.utc) + expires,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256"), jti

def decode_token(token: str, expected_type: str) -> dict:
    payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
    if payload.get("type") != expected_type:
        raise jwt.InvalidTokenError("Wrong token type")
    return payload