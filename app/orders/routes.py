from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from starlette import status

from app.database import AsyncSession, get_session
from app.users.models import User
from app.dependencies import get_current_user, get_current_staff
from app.products.models import Product
from app.orders.models import Order
from app.orders.schemas import OrderCreate, OrderRead

orders_router = APIRouter(
    prefix="/api/v1/orders",
    tags=["orders"],
)


def unit_price(product: Product):
    """Chegirma narxi bor va price'dan kichik bo'lsa, o'sha ishlatiladi."""
    if product.discount_price and product.discount_price < product.price:
        return product.discount_price
    return product.price


# ---------- CREATE (faqat login qilgan foydalanuvchi) ----------
@orders_router.post("/create", response_model=OrderRead, status_code=status.HTTP_201_CREATED)
async def create_order(
    data: OrderCreate,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    product = await session.get(Product, data.product_id)
    if product is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Product topilmadi")

    order = Order(
        user_id=user.id,  # user_id clientdan olinmaydi, faqat tokendan
        product_id=product.id,
        quantity=data.quantity,
        total_price=unit_price(product) * data.quantity,
    )
    session.add(order)
    await session.commit()
    await session.refresh(order)
    return order


# ---------- READ: o'zining buyurtmalari ----------
@orders_router.get("/my", response_model=list[OrderRead])
async def my_orders(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    result = await session.execute(
        select(Order)
        .where(Order.user_id == user.id)
        .order_by(Order.id.desc())
        .offset(skip)
        .limit(limit)
    )
    return result.scalars().all()


# ---------- READ: hamma buyurtmalar (faqat staff) ----------
@orders_router.get("/all", response_model=list[OrderRead])
async def all_orders(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
    staff: User = Depends(get_current_staff),
):
    result = await session.execute(
        select(Order).order_by(Order.id.desc()).offset(skip).limit(limit)
    )
    return result.scalars().all()


# ---------- READ: bitta buyurtma (egasi yoki staff) ----------
@orders_router.get("/{order_id}", response_model=OrderRead)
async def get_order(
    order_id: int,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    order = await session.get(Order, order_id)
    if order is None or (order.user_id != user.id and not user.is_staff):
        # begona buyurtma borligini bildirmaslik uchun ikkalasida ham 404
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Order topilmadi")
    return order


# ---------- DELETE: bekor qilish (egasi yoki staff) ----------
@orders_router.delete("/{order_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_order(
    order_id: int,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    order = await session.get(Order, order_id)
    if order is None or (order.user_id != user.id and not user.is_staff):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Order topilmadi")
    await session.delete(order)
    await session.commit()