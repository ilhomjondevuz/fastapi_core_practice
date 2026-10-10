from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class ProductCreate(BaseModel):
    name: str
    price: Decimal = Decimal("0")
    discount_price: Decimal = Decimal("0")
    photo: str | None = None
    description: str | None = None


class ProductRead(ProductCreate):
    id: int
    name: str
    price: Decimal = Decimal("0")
    discount_price: Decimal = Decimal("0")
    photo: str | None = None
    description: str | None = None

    model_config = ConfigDict(from_attributes=True)