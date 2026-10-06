from environs import Env
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase

env = Env()
env.read_env()

DATABASE_URL = env.str("DATABASE_URL")
engine = create_async_engine(DATABASE_URL)

async_session = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
    class_=AsyncSession
)

class Base(DeclarativeBase):
    pass