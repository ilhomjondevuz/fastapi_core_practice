from decimal import Decimal

from sqlalchemy import Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Product(Base):
    __tablename__ = 'products'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0)
    discount_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0)
    photo: Mapped[str | None] = mapped_column(String(100), nullable=True)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)

    orders = relationship("Order", back_populates="product")

    def __repr__(self) -> str:
        return f"<Product {self.name}>"