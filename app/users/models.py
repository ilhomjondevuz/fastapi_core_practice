from datetime import datetime, timezone

from sqlalchemy import Integer, String, Boolean, DateTime, ForeignKey, false
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(50), unique=True)
    email: Mapped[str] = mapped_column(String(255), unique=True)
    password: Mapped[str] = mapped_column(String(255))
    first_name: Mapped[str] = mapped_column(String(100), nullable=True)
    last_name: Mapped[str] = mapped_column(String(100), nullable=True)
    phone: Mapped[str] = mapped_column(String(13), nullable=True)
    avatar: Mapped[str] = mapped_column(String(100), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_staff: Mapped[bool] = mapped_column(default=False, server_default=false())
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())

    orders = relationship("Order", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<User: {self.username}>"


class PasswordResetCode(Base):
    """Parolni tiklash uchun emailga yuborilgan bir martalik kod."""
    __tablename__ = "password_reset_codes"

    # uuid4().hex: tokenlar ichida shu id saqlanadi (kim ekanini shu orqali taniymiz)
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    code_hash: Mapped[str] = mapped_column(String(64))  # kodning o'zi emas, HMAC hash'i
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    verified: Mapped[bool] = mapped_column(Boolean, default=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

class RevokedToken(Base):
    __tablename__ = "revoked_tokens"

    jti: Mapped[str] = mapped_column(String(32), primary_key=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)