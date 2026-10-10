from decimal import Decimal

from fastapi import APIRouter, Depends, Request, Form, File, UploadFile
from starlette import status

from app.database import AsyncSession, get_session
from app.users.models import User
from app.dependencies import get_current_staff
from app.products.models import Product
from app.products.schemas import ProductRead, ProductCreate
from app.products.utils import save_image, PRODUCT_DIR
from app.users.utils import delete_avatar

products_router = APIRouter(
    prefix="/api/v1/products",
    tags=["products"],
)

@products_router.get("/get")
async def get_products() -> dict:
    return {"endpoint": 'Products'}

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
        delete_avatar(photo_path)  # baza xato bersa, rasm diskda qolib ketmasin
        raise
    await session.refresh(product)

    result = ProductRead.model_validate(product)
    if product.photo:
        result.photo = str(request.url_for("media", path=product.photo))
    return result