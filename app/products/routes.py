from fastapi import APIRouter

auth_router = APIRouter(
    prefix="/auth",
    tags=["auth"],
)

@auth_router.get("/me")
async def read_users_me():
    return {"my_info": "FIO: Test"}