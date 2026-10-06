import bcrypt
from datetime import datetime, timedelta, timezone

from environs import Env
from jose import jwt, JWTError

from app.users.security import hash_password

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