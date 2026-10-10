import uuid
from pathlib import Path

import aiofiles
from fastapi import HTTPException, UploadFile, status

from app.users.utils import detect_image_ext


# ==================================================
# PATH CONFIGURATION
# ==================================================

BASE_DIR = Path(__file__).resolve().parent.parent.parent

MEDIA_ROOT = BASE_DIR / "media"
PRODUCT_DIR = MEDIA_ROOT / "products"

# ==================================================
# IMAGE CONFIGURATION
# ==================================================

MAX_PRODUCT_SIZE = 2 * 1024 * 1024  # 2 MB
CHUNK_SIZE = 64 * 1024  # 64 KB

# ==================================================
# CREATE DIRECTORIES
# ==================================================

MEDIA_ROOT.mkdir(parents=True, exist_ok=True)


# ==================================================
# SAVE IMAGE
# ==================================================

async def save_image(
    file: UploadFile,
    folder: Path,
    prefix: str,
) -> str:
    """
    Rasmni diskka saqlaydi va nisbiy yo'lni qaytaradi.

    Masalan:
        products/abc123.jpg
    """

    # 1. Rasm formatini aniqlash
    header = await file.read(16)
    ext = detect_image_ext(header)

    # Faylni qayta boshidan o'qish
    await file.seek(0)

    # 2. Formatni tekshirish
    if ext is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Faqat haqiqiy JPG, PNG yoki WEBP rasm yuklash mumkin.",
        )

    # 3. Saqlash papkasini yaratish
    folder.mkdir(parents=True, exist_ok=True)

    # 4. Noyob fayl nomini yaratish
    filename = f"{uuid.uuid4().hex}{ext}"
    dest = folder / filename

    size = 0

    try:
        # 5. Faylni asinxron yozish
        async with aiofiles.open(dest, "wb") as out:

            while chunk := await file.read(CHUNK_SIZE):

                # Fayl hajmini hisoblash
                size += len(chunk)

                # 6. Hajmni tekshirish
                if size > MAX_PRODUCT_SIZE:
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail="Rasm hajmi 2 MB dan oshmasligi kerak.",
                    )

                # 7. Fayl bo'lagini yozish
                await out.write(chunk)

    except Exception:
        # Xatolikda qisman yozilgan faylni o'chirish
        dest.unlink(missing_ok=True)
        raise

    finally:
        # UploadFile pozitsiyasini boshiga qaytarish
        await file.seek(0)

    # 8. Nisbiy yo'lni qaytarish
    return f"{prefix}/{filename}"


# ==================================================
# SAVE PRODUCT IMAGE
# ==================================================

async def save_product_image(file: UploadFile) -> str:
    """Mahsulot rasmini saqlaydi."""

    return await save_image(
        file=file,
        folder=PRODUCT_DIR,
        prefix="products",
    )