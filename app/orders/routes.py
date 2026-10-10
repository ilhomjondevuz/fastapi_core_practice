from fastapi import APIRouter

orders_router = APIRouter(
    prefix="/api/v1/orders",
    tags=["orders"],
)

@orders_router.get("/get")
async def read_users_me() -> dict:
    return {"endpoint": "Orders"}