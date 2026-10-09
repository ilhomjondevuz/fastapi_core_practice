from datetime import datetime, timezone

from sqlalchemy import delete
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.users.models import RevokedToken


async def revoke_token(session: AsyncSession, payload: dict) -> bool:
    """True: hozir bekor qilindi. False: avval ham bekor qilingan edi."""
    session.add(
        RevokedToken(
            jti=payload["jti"],
            expires_at=datetime.fromtimestamp(payload["exp"], tz=timezone.utc),
        )
    )
    try:
        await session.commit()
        return True
    except IntegrityError:
        await session.rollback()
        return False


async def purge_expired(session: AsyncSession) -> None:
    """Muddati o'tganlarini tozalash (cron / startup'da chaqiring)."""
    await session.execute(
        delete(RevokedToken).where(RevokedToken.expires_at < datetime.now(timezone.utc))
    )
    await session.commit()