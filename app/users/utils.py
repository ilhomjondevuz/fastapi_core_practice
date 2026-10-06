import uuid
from pathlib import Path

import aiofiles
from fastapi import HTTPException, UploadFile, status

# ---------- Yo'llar ----------
# utils.py: app/users/utils.py -> loyiha ildizi 3 daraja yuqorida
BASE_DIR = Path(__file__).resolve().parent.parent.parent

MEDIA_ROOT = BASE_DIR / "media"
STATIC_ROOT = BASE_DIR / "static"
AVATAR_DIR = MEDIA_ROOT / "avatars"

MEDIA_ROOT.mkdir(exist_ok=True)
STATIC_ROOT.mkdir(exist_ok=True)

# ---------- Avatar sozlamalari ----------
MAX_AVATAR_SIZE = 2 * 1024 * 1024  # 2 MB


def detect_image_ext(head: bytes) -> str | None:
    """Faylning boshlang'ich baytlariga qarab rasm kengaytmasini aniqlaydi."""
    if head.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return ".webp"
    return None


async def save_avatar(file: UploadFile) -> str:
    """Rasmni media/avatars/ ga saqlaydi va nisbiy yo'lini qaytaradi."""
    ext = detect_image_ext(await file.read(16))
    await file.seek(0)
    if ext is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Faqat haqiqiy JPG, PNG yoki WEBP rasm yuklash mumkin",
        )

    AVATAR_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid.uuid4().hex}{ext}"
    dest = AVATAR_DIR / filename

    size = 0
    try:
        async with aiofiles.open(dest, "wb") as out:
            while chunk := await file.read(64 * 1024):
                size += len(chunk)
                if size > MAX_AVATAR_SIZE:
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail="Rasm hajmi 2 MB dan oshmasligi kerak",
                    )
                await out.write(chunk)
    except Exception:
        dest.unlink(missing_ok=True)  # yarim yozilgan faylni o'chirish
        raise

    return f"avatars/{filename}"  # bazaga shu yo'l yoziladi


def delete_avatar(path: str | None) -> None:
    """Bazadagi nisbiy yo'l bo'yicha rasmni diskdan o'chiradi."""
    if path:
        (MEDIA_ROOT / path).unlink(missing_ok=True)