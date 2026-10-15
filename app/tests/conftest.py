import itertools
import os
from decimal import Decimal
from types import SimpleNamespace
from urllib.parse import urlparse

import pytest
import pytest_asyncio
from environs import Env
from httpx2 import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.database import Base, get_session
from app.main import app
from app.orders.models import Order
from app.products.models import Product
from app.users.models import User
from app.users.security import create_access_token, hash_password

env = Env()
env.read_env()

# MUHIM: alohida test bazasi. Asosiy bazangiz nomiga tegilmasligi uchun
# nomida "test" bo'lishi shart (har safar drop_all/TRUNCATE qilinadi).
TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    env.str('TEST_DATABASE_URL'),
)
_db_name = urlparse(TEST_DATABASE_URL).path.lstrip("/")
if "test" not in _db_name:
    raise RuntimeError(
        f"TEST_DATABASE_URL bazasi nomida 'test' bo'lishi kerak, hozir: {_db_name!r}"
    )

PASSWORD = env.str('LOGIN_PASSWORD')


# ---------------------------------------------------------------- database
@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def engine():
    engine = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def session_maker(engine):
    return async_sessionmaker(engine, expire_on_commit=False)  # app/database.py bilan bir xil


@pytest_asyncio.fixture(autouse=True)
async def _clean_db(engine):
    """Har bir testdan keyin jadvallar tozalanadi (id'lar 1 dan boshlanadi)."""
    yield
    tables = ", ".join(f'"{t.name}"' for t in Base.metadata.sorted_tables)
    async with engine.begin() as conn:
        await conn.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))


@pytest_asyncio.fixture
async def client(session_maker):
    async def override_get_session():
        async with session_maker() as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def db_get(session_maker):
    """Bazadan yangi sessiya bilan obyektni o'qiydi: `await db_get(User, 1)`."""

    async def _get(model, pk):
        async with session_maker() as s:
            return await s.get(model, pk)

    return _get


# -------------------------------------------------------------------- mail
@pytest.fixture(autouse=True)
def sent_mail(monkeypatch):
    """Haqiqiy email yuborilmaydi, o'rniga yuborilganlar ro'yxatga yig'iladi."""
    box = SimpleNamespace(verification=[], reset=[])
    monkeypatch.setattr(
        "app.users.routes.send_verification_email",
        lambda email, token: box.verification.append((email, token)),
    )
    monkeypatch.setattr(
        "app.users.routes.send_reset_email",
        lambda email, code: box.reset.append((email, code)),
    )
    return box


# ------------------------------------------------------------------- users
@pytest.fixture(scope="session")
def password():
    return PASSWORD


@pytest.fixture(scope="session")
def password_hash():
    # bcrypt sekin, shuning uchun bir marta hisoblaymiz
    return hash_password(PASSWORD)


@pytest_asyncio.fixture
async def make_user(session_maker, password_hash):
    counter = itertools.count(1)

    async def _make(**overrides):
        n = next(counter)
        data = dict(
            username=f"user{n}",
            email=f"user{n}@example.com",
            password=password_hash,
            is_active=True,
            is_verified=True,
            is_staff=False,
        )
        data.update(overrides)
        async with session_maker() as s:
            u = User(**data)
            s.add(u)
            await s.commit()
            await s.refresh(u)
            return u

    return _make


@pytest_asyncio.fixture
async def user(make_user):
    return await make_user()


@pytest_asyncio.fixture
async def staff(make_user):
    return await make_user(is_staff=True)


@pytest.fixture
def auth():
    def _auth(u: User) -> dict:
        return {"Authorization": f"Bearer {create_access_token(u.id)}"}

    return _auth


# ---------------------------------------------------------------- products
@pytest_asyncio.fixture
async def make_product(session_maker):
    counter = itertools.count(1)

    async def _make(**overrides):
        n = next(counter)
        data = dict(
            name=f"Product {n}",
            price=Decimal("100.00"),
            discount_price=Decimal("0"),
            description=None,
            photo=None,
        )
        data.update(overrides)
        async with session_maker() as s:
            p = Product(**data)
            s.add(p)
            await s.commit()
            await s.refresh(p)
            return p

    return _make


# ------------------------------------------------------------------ orders
@pytest_asyncio.fixture
async def make_order(session_maker):
    async def _make(user, product, quantity=1, total_price=None):
        async with session_maker() as s:
            o = Order(
                user_id=user.id,
                product_id=product.id,
                quantity=quantity,
                total_price=(
                    total_price
                    if total_price is not None
                    else product.price * quantity
                ),
            )
            s.add(o)
            await s.commit()
            await s.refresh(o)
            return o

    return _make