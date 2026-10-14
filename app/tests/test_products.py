import struct
import zlib
from decimal import Decimal

from app.products.models import Product
from app.products import utils as product_utils

BASE = "/api/v1/products"
NO_AUTH = (401, 403)


def dec(value) -> Decimal:
    """JSON'dagi son/satrni Decimal'ga o'tkazadi (float xatolarisiz solishtirish uchun)."""
    return Decimal(str(value))


def tiny_png() -> bytes:
    """1x1 piksellik haqiqiy PNG (tashqi kutubxonasiz)."""

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(b"\x00\xff\x00\x00"))
        + chunk(b"IEND", b"")
    )


# ================================================================= LIST
async def test_list_empty(client):
    r = await client.get(f"{BASE}/")
    assert r.status_code == 200
    assert r.json() == []


async def test_list_is_public_and_ordered_by_id(client, make_product):
    p1 = await make_product()
    p2 = await make_product()
    p3 = await make_product()

    r = await client.get(f"{BASE}/")  # tokensiz
    assert r.status_code == 200
    assert [p["id"] for p in r.json()] == [p1.id, p2.id, p3.id]


async def test_list_pagination(client, make_product):
    created = [await make_product() for _ in range(3)]

    r = await client.get(f"{BASE}/", params={"limit": 2})
    assert [p["id"] for p in r.json()] == [created[0].id, created[1].id]

    r = await client.get(f"{BASE}/", params={"skip": 2, "limit": 2})
    assert [p["id"] for p in r.json()] == [created[2].id]


async def test_list_invalid_pagination_params(client):
    assert (await client.get(f"{BASE}/", params={"skip": -1})).status_code == 422
    assert (await client.get(f"{BASE}/", params={"limit": 0})).status_code == 422
    assert (await client.get(f"{BASE}/", params={"limit": 101})).status_code == 422


# ================================================================== GET
async def test_get_product(client, make_product):
    p = await make_product(name="Laptop", description="Fast")
    r = await client.get(f"{BASE}/{p.id}")
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == p.id
    assert body["name"] == "Laptop"
    assert body["description"] == "Fast"
    assert body["photo"] is None


async def test_get_product_photo_is_full_url(client, make_product):
    p = await make_product(photo="products/abc.png")
    r = await client.get(f"{BASE}/{p.id}")
    assert r.status_code == 200
    photo = r.json()["photo"]
    assert photo.startswith("http")
    assert photo.endswith("products/abc.png")


async def test_get_product_not_found(client):
    r = await client.get(f"{BASE}/999")
    assert r.status_code == 404


# =============================================================== CREATE
async def test_create_product_as_staff(client, staff, auth, db_get):
    r = await client.post(
        f"{BASE}/create",
        data={
            "name": "Phone",
            "price": "1000.50",
            "discount_price": "900",
            "description": "Nice phone",
        },
        headers=auth(staff),
    )
    assert r.status_code == 201
    body = r.json()
    assert body["name"] == "Phone"
    assert dec(body["price"]) == Decimal("1000.50")
    assert dec(body["discount_price"]) == Decimal("900")
    assert body["description"] == "Nice phone"
    assert body["photo"] is None

    assert (await db_get(Product, body["id"])) is not None


async def test_create_product_defaults(client, staff, auth):
    r = await client.post(
        f"{BASE}/create", data={"name": "Bare"}, headers=auth(staff)
    )
    assert r.status_code == 201
    assert dec(r.json()["price"]) == 0
    assert dec(r.json()["discount_price"]) == 0


async def test_create_product_requires_auth(client):
    r = await client.post(f"{BASE}/create", data={"name": "X"})
    assert r.status_code in NO_AUTH


async def test_create_product_forbidden_for_regular_user(client, user, auth):
    r = await client.post(
        f"{BASE}/create", data={"name": "X"}, headers=auth(user)
    )
    assert r.status_code == 403


async def test_create_product_discount_greater_than_price(client, staff, auth):
    r = await client.post(
        f"{BASE}/create",
        data={"name": "X", "price": "100", "discount_price": "150"},
        headers=auth(staff),
    )
    assert r.status_code == 422


async def test_create_product_discount_equal_to_price_is_allowed(client, staff, auth):
    r = await client.post(
        f"{BASE}/create",
        data={"name": "X", "price": "100", "discount_price": "100"},
        headers=auth(staff),
    )
    assert r.status_code == 201


async def test_create_product_validation_errors(client, staff, auth):
    headers = auth(staff)
    # name yo'q
    assert (await client.post(f"{BASE}/create", data={}, headers=headers)).status_code == 422
    # name juda uzun (max 50)
    r = await client.post(f"{BASE}/create", data={"name": "x" * 51}, headers=headers)
    assert r.status_code == 422
    # manfiy narx
    r = await client.post(
        f"{BASE}/create", data={"name": "X", "price": "-1"}, headers=headers
    )
    assert r.status_code == 422
    # description juda uzun (max 500)
    r = await client.post(
        f"{BASE}/create",
        data={"name": "X", "description": "d" * 501},
        headers=headers,
    )
    assert r.status_code == 422


async def test_create_product_with_photo(client, staff, auth, tmp_path, monkeypatch):
    # rasm haqiqiy media papkaga tushib qolmasligi uchun vaqtinchalik papkaga yo'naltiramiz
    tmp_dir = type(product_utils.PRODUCT_DIR)(tmp_path)
    monkeypatch.setattr("app.products.routes.PRODUCT_DIR", tmp_dir)

    r = await client.post(
        f"{BASE}/create",
        data={"name": "With photo"},
        files={"photo": ("test.png", tiny_png(), "image/png")},
        headers=auth(staff),
    )
    assert r.status_code == 201
    photo = r.json()["photo"]
    assert photo is not None and photo.startswith("http")
    assert any(f.is_file() for f in tmp_path.rglob("*"))  # fayl diskka yozilgan


# =============================================================== UPDATE
async def test_update_product_partial(client, staff, auth, make_product, db_get):
    p = await make_product(name="Old", price=Decimal("100"), description="keep me")
    r = await client.patch(
        f"{BASE}/{p.id}", data={"name": "New"}, headers=auth(staff)
    )
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "New"
    assert dec(body["price"]) == 100
    assert body["description"] == "keep me"

    assert (await db_get(Product, p.id)).name == "New"


async def test_update_product_price_and_discount(client, staff, auth, make_product):
    p = await make_product(price=Decimal("100"))
    r = await client.patch(
        f"{BASE}/{p.id}",
        data={"price": "200", "discount_price": "150"},
        headers=auth(staff),
    )
    assert r.status_code == 200
    assert dec(r.json()["price"]) == 200
    assert dec(r.json()["discount_price"]) == 150


async def test_update_discount_checked_against_existing_price(
    client, staff, auth, make_product
):
    p = await make_product(price=Decimal("100"))
    # price yuborilmagan, lekin bazadagi price (100) dan katta chegirma mumkin emas
    r = await client.patch(
        f"{BASE}/{p.id}", data={"discount_price": "150"}, headers=auth(staff)
    )
    assert r.status_code == 422


async def test_update_price_below_existing_discount(client, staff, auth, make_product):
    p = await make_product(price=Decimal("100"), discount_price=Decimal("80"))
    r = await client.patch(
        f"{BASE}/{p.id}", data={"price": "50"}, headers=auth(staff)
    )
    assert r.status_code == 422


async def test_update_product_not_found(client, staff, auth):
    r = await client.patch(f"{BASE}/999", data={"name": "X"}, headers=auth(staff))
    assert r.status_code == 404


async def test_update_product_forbidden_for_regular_user(
    client, user, auth, make_product
):
    p = await make_product(name="Old")
    r = await client.patch(
        f"{BASE}/{p.id}", data={"name": "Hacked"}, headers=auth(user)
    )
    assert r.status_code == 403


async def test_update_product_requires_auth(client, make_product):
    p = await make_product()
    r = await client.patch(f"{BASE}/{p.id}", data={"name": "X"})
    assert r.status_code in NO_AUTH


# =============================================================== DELETE
async def test_delete_product(client, staff, auth, make_product, db_get):
    p = await make_product()
    r = await client.delete(f"{BASE}/{p.id}", headers=auth(staff))
    assert r.status_code == 204
    assert (await db_get(Product, p.id)) is None
    assert (await client.get(f"{BASE}/{p.id}")).status_code == 404


async def test_delete_product_not_found(client, staff, auth):
    r = await client.delete(f"{BASE}/999", headers=auth(staff))
    assert r.status_code == 404


async def test_delete_product_forbidden_for_regular_user(
    client, user, auth, make_product, db_get
):
    p = await make_product()
    r = await client.delete(f"{BASE}/{p.id}", headers=auth(user))
    assert r.status_code == 403
    assert (await db_get(Product, p.id)) is not None


async def test_delete_product_requires_auth(client, make_product):
    p = await make_product()
    r = await client.delete(f"{BASE}/{p.id}")
    assert r.status_code in NO_AUTH