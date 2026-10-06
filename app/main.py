from fastapi import FastAPI, Request

from app.users.routes import auth_router

app = FastAPI(
    title="My FastAPI App",
    description="My FastAPI App",
    version="0.0.1",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)
app.include_router(auth_router)

@app.get("/")
async def read_root(request: Request):
    base_url = str(request.base_url).rstrip("/")
    return {
        "swagger_url": f"{base_url}/docs",
        "redoc_url": f"{base_url}/redoc",
        "openapi_url": f"{base_url}/openapi.json",
    }