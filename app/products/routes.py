from decimal import Decimal

from fastapi import (
    APIRouter, Depends, Request, Form, File, UploadFile, HTTPException, Query
)
from sqlalchemy import select
from starlette import status

from app.database import AsyncSession, get_session
from app.users.models import User
from app.dependencies import get_current_staff
from app.products.models import Product
from app.products.schemas import ProductRead
from app.products.utils import save_image, PRODUCT_DIR
from app.users.utils import delete_avatar

products_router = APIRouter(
    prefix="/api/v1/products",
    tags=["products"],
)


def to_read(product: Product, request: Request) -> ProductRead:
    """Product -> ProductRead, rasm uchun to'liq URL bilan."""
    result = ProductRead.model_validate(product)
    if product.photo:
        result.photo = str(request.url_for("media", path=product.photo))
    return result


async def get_product_or_404(session: AsyncSession, product_id: int) -> Product:
    product = await session.get(Product, product_id)
    if product is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Product topilmadi")
    return product


# ---------- READ (hammaga ochiq) ----------
@products_router.get("/", response_model=list[ProductRead])
async def list_products(
    request: Request,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(Product).order_by(Product.id).offset(skip).limit(limit)
    )
    return [to_read(p, request) for p in result.scalars().all()]


@products_router.get("/{product_id}", response_model=ProductRead)
async def get_product(
    product_id: int,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    product = await get_product_or_404(session, product_id)
    return to_read(product, request)


# ---------- CREATE (staff) ----------
@products_router.post("/create", response_model=ProductRead, status_code=status.HTTP_201_CREATED)
async def create_product(
    request: Request,
    name: str = Form(..., min_length=1, max_length=50),
    price: Decimal = Form(Decimal("0"), ge=0),
    discount_price: Decimal = Form(Decimal("0"), ge=0),
    description: str | None = Form(None, max_length=500),
    photo: UploadFile | None = File(None),
    session: AsyncSession = Depends(get_session),
    staff: User = Depends(get_current_staff),
):
    if discount_price > price:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "discount_price price'dan katta bo'lmasligi kerak",
        )

    photo_path = (
        await save_image(photo, PRODUCT_DIR, "products")
        if photo and photo.filename
        else None
    )

    product = Product(
        name=name,
        price=price,
        discount_price=discount_price,
        description=description,
        photo=photo_path,
    )
    session.add(product)
    try:
        await session.commit()
    except Exception:
        delete_avatar(photo_path)
        raise
    await session.refresh(product)
    return to_read(product, request)


# ---------- UPDATE (staff) ----------
@products_router.patch("/{product_id}", response_model=ProductRead)
async def update_product(
    product_id: int,
    request: Request,
    name: str | None = Form(None, min_length=1, max_length=50),
    price: Decimal | None = Form(None, ge=0),
    discount_price: Decimal | None = Form(None, ge=0),
    description: str | None = Form(None, max_length=500),
    photo: UploadFile | None = File(None),
    session: AsyncSession = Depends(get_session),
    staff: User = Depends(get_current_staff),
):
    product = await get_product_or_404(session, product_id)

    new_price = price if price is not None else product.price
    new_discount = discount_price if discount_price is not None else product.discount_price
    if new_discount > new_price:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "discount_price price'dan katta bo'lmasligi kerak",
        )

    if name is not None:
        product.name = name
    if price is not None:
        product.price = price
    if discount_price is not None:
        product.discount_price = discount_price
    if description is not None:
        product.description = description

    old_photo = product.photo
    new_photo = None
    if photo and photo.filename:
        new_photo = await save_image(photo, PRODUCT_DIR, "products")
        product.photo = new_photo

    try:
        await session.commit()
    except Exception:
        delete_avatar(new_photo)  # yangi rasm yetim qolmasin
        raise

    if new_photo and old_photo:
        delete_avatar(old_photo)  # commit muvaffaqiyatli bo'lgach eskisini o'chiramiz

    await session.refresh(product)
    return to_read(product, request)


# ---------- DELETE (staff) ----------
@products_router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_product(
    product_id: int,
    session: AsyncSession = Depends(get_session),
    staff: User = Depends(get_current_staff),
):
    product = await get_product_or_404(session, product_id)
    photo_path = product.photo

    await session.delete(product)
    await session.commit()

    delete_avatar(photo_path)