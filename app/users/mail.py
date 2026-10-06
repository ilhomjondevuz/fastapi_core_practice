import logging
from email.message import EmailMessage

import aiosmtplib

from app.core.config import settings

logger = logging.getLogger(__name__)


async def send_email(to: str, subject: str, text: str, html: str | None = None) -> None:
    msg = EmailMessage()
    msg["From"] = settings.EMAIL_FROM
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(text)
    if html:
        msg.add_alternative(html, subtype="html")

    await aiosmtplib.send(
        msg,
        hostname=settings.SMTP_HOST,
        port=settings.SMTP_PORT,
        username=settings.SMTP_USER,
        password=settings.SMTP_PASSWORD,
        start_tls=True,  # 465-port bo'lsa: use_tls=True, start_tls olib tashlang
    )


async def send_reset_email(to: str, code: str) -> None:
    minutes = settings.RESET_TOKEN_EXPIRE_MINUTES
    text = (
        f"Parolni tiklash kodingiz: {code}\n\n"
        f"Kod {minutes} daqiqa amal qiladi. Kodni hech kimga bermang.\n"
        "Agar bu so'rovni siz yubormagan bo'lsangiz, xatni e'tiborsiz qoldiring."
    )
    html = (
        "<p>Parolni tiklash kodingiz:</p>"
        f'<p style="font-size:28px;font-weight:bold;letter-spacing:6px">{code}</p>'
        f"<p>Kod {minutes} daqiqa amal qiladi. Kodni hech kimga bermang.</p>"
        "<p>Agar bu so'rovni siz yubormagan bo'lsangiz, xatni e'tiborsiz qoldiring.</p>"
    )
    try:
        await send_email(to, "Parolni tiklash kodi", text, html)
    except Exception:
        # Background task'da xato foydalanuvchiga qaytmaydi, shuning uchun logga yozamiz
        logger.exception("Reset email yuborilmadi: %s", to)