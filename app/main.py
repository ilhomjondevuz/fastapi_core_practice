from fastapi import FastAPI, Request
from starlette.staticfiles import StaticFiles

from app.users.routes import auth_router
from app.users.utils import MEDIA_ROOT, STATIC_ROOT
from app.products.routes import products_router
from app.orders.routes import orders_router

app = FastAPI(
    title="My FastAPI App",
    description="My FastAPI App",
    version="0.0.1",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)
app.mount("/static", StaticFiles(directory=STATIC_ROOT), name="static")
app.mount("/media", StaticFiles(directory=MEDIA_ROOT), name="media")

app.include_router(auth_router)
app.include_router(products_router)
app.include_router(orders_router)

@app.get("/")
async def read_root(request: Request):
    base_url = str(request.base_url).rstrip("/")
    return {
        "swagger_url": f"{base_url}/docs",
        "redoc_url": f"{base_url}/redoc",
        "openapi_url": f"{base_url}/openapi.json",
    }