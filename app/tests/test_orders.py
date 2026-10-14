from decimal import Decimal

import pytest

from app.orders.models import Order

BASE = "/api/v1/orders"
NO_AUTH = (401, 403)


def dec(value) -> Decimal:
    return Decimal(str(value))


# =============================================================== CREATE
async def test_create_order(client, user, auth, make_product, db_get):
    product = await make_product(price=Decimal("100"))
    r = await client.post(
        f"{BASE}/create",
        json={"product_id": product.id, "quantity": 3},
        headers=auth(user),
    )
    assert r.status_code == 201
    body = r.json()
    assert body["user_id"] == user.id
    assert body["product_id"] == product.id
    assert body["quantity"] == 3
    assert dec(body["total_price"]) == Decimal("300")

    assert (await db_get(Order, body["id"])) is not None


@pytest.mark.parametrize(
    "price, discount, expected_unit",
    [
        ("100", "0", "100"),      # chegirma yo'q -> oddiy narx
        ("100", "80", "80"),      # chegirma kichik -> chegirma narxi
        ("100", "100", "100"),    # chegirma price'ga teng -> oddiy narx
        ("100", "150", "100"),    # chegirma katta (noto'g'ri data) -> oddiy narx
    ],
)
async def test_create_order_unit_price(
    client, user, auth, make_product, price, discount, expected_unit
):
    product = await make_product(
        price=Decimal(price), discount_price=Decimal(discount)
    )
    r = await client.post(
        f"{BASE}/create",
        json={"product_id": product.id, "quantity": 2},
        headers=auth(user),
    )
    assert r.status_code == 201
    assert dec(r.json()["total_price"]) == Decimal(expected_unit) * 2


async def test_create_order_ignores_client_user_id(
    client, make_user, auth, make_product
):
    me = await make_user()
    other = await make_user()
    product = await make_product()

    r = await client.post(
        f"{BASE}/create",
        json={"product_id": product.id, "quantity": 1, "user_id": other.id},
        headers=auth(me),
    )
    assert r.status_code == 201
    assert r.json()["user_id"] == me.id  # faqat tokendan olinadi


async def test_create_order_product_not_found(client, user, auth):
    r = await client.post(
        f"{BASE}/create",
        json={"product_id": 999, "quantity": 1},
        headers=auth(user),
    )
    assert r.status_code == 404


async def test_create_order_requires_auth(client, make_product):
    product = await make_product()
    r = await client.post(
        f"{BASE}/create", json={"product_id": product.id, "quantity": 1}
    )
    assert r.status_code in NO_AUTH


async def test_create_order_missing_product_id(client, user, auth):
    r = await client.post(f"{BASE}/create", json={"quantity": 1}, headers=auth(user))
    assert r.status_code == 422


@pytest.mark.parametrize("quantity", [0, -1])
async def test_create_order_invalid_quantity(client, user, auth, make_product, quantity):
    # OrderCreate'da quantity > 0 (Field(gt=0)) bo'lishi kerak.
    # Agar bu test yiqilsa, schema'da validatsiya yetishmayapti degani.
    product = await make_product()
    r = await client.post(
        f"{BASE}/create",
        json={"product_id": product.id, "quantity": quantity},
        headers=auth(user),
    )
    assert r.status_code == 422


# ================================================================== MY
async def test_my_orders_only_own_newest_first(
    client, make_user, auth, make_product, make_order
):
    me = await make_user()
    other = await make_user()
    product = await make_product()

    o1 = await make_order(me, product)
    await make_order(other, product)
    o3 = await make_order(me, product)

    r = await client.get(f"{BASE}/my", headers=auth(me))
    assert r.status_code == 200
    assert [o["id"] for o in r.json()] == [o3.id, o1.id]
    assert all(o["user_id"] == me.id for o in r.json())


async def test_my_orders_empty(client, user, auth):
    r = await client.get(f"{BASE}/my", headers=auth(user))
    assert r.status_code == 200
    assert r.json() == []


async def test_my_orders_pagination(client, user, auth, make_product, make_order):
    product = await make_product()
    orders = [await make_order(user, product) for _ in range(3)]  # id: 1, 2, 3

    r = await client.get(f"{BASE}/my", params={"limit": 2}, headers=auth(user))
    assert [o["id"] for o in r.json()] == [orders[2].id, orders[1].id]

    r = await client.get(f"{BASE}/my", params={"skip": 2}, headers=auth(user))
    assert [o["id"] for o in r.json()] == [orders[0].id]


async def test_my_orders_invalid_pagination(client, user, auth):
    r = await client.get(f"{BASE}/my", params={"limit": 101}, headers=auth(user))
    assert r.status_code == 422


async def test_my_orders_requires_auth(client):
    r = await client.get(f"{BASE}/my")
    assert r.status_code in NO_AUTH


# ================================================================= ALL
async def test_all_orders_as_staff(
    client, staff, make_user, auth, make_product, make_order
):
    u1 = await make_user()
    u2 = await make_user()
    product = await make_product()
    o1 = await make_order(u1, product)
    o2 = await make_order(u2, product)

    r = await client.get(f"{BASE}/all", headers=auth(staff))
    assert r.status_code == 200
    assert [o["id"] for o in r.json()] == [o2.id, o1.id]


async def test_all_orders_forbidden_for_regular_user(client, user, auth):
    r = await client.get(f"{BASE}/all", headers=auth(user))
    assert r.status_code == 403


async def test_all_orders_requires_auth(client):
    r = await client.get(f"{BASE}/all")
    assert r.status_code in NO_AUTH


async def test_all_orders_pagination(client, staff, user, auth, make_product, make_order):
    product = await make_product()
    for _ in range(3):
        await make_order(user, product)

    r = await client.get(f"{BASE}/all", params={"limit": 2}, headers=auth(staff))
    assert len(r.json()) == 2
    r = await client.get(f"{BASE}/all", params={"skip": 2}, headers=auth(staff))
    assert len(r.json()) == 1


# ============================================================== GET ONE
async def test_get_own_order(client, user, auth, make_product, make_order):
    order = await make_order(user, await make_product())
    r = await client.get(f"{BASE}/{order.id}", headers=auth(user))
    assert r.status_code == 200
    assert r.json()["id"] == order.id


async def test_get_foreign_order_is_404(
    client, make_user, auth, make_product, make_order
):
    owner = await make_user()
    stranger = await make_user()
    order = await make_order(owner, await make_product())

    r = await client.get(f"{BASE}/{order.id}", headers=auth(stranger))
    assert r.status_code == 404  # 403 emas: begona order borligi sezilmasin


async def test_get_any_order_as_staff(client, staff, user, auth, make_product, make_order):
    order = await make_order(user, await make_product())
    r = await client.get(f"{BASE}/{order.id}", headers=auth(staff))
    assert r.status_code == 200


async def test_get_order_not_found(client, user, auth):
    r = await client.get(f"{BASE}/999", headers=auth(user))
    assert r.status_code == 404


async def test_get_order_requires_auth(client, user, make_product, make_order):
    order = await make_order(user, await make_product())
    r = await client.get(f"{BASE}/{order.id}")
    assert r.status_code in NO_AUTH


# ================================================================ DELETE
async def test_delete_own_order(client, user, auth, make_product, make_order, db_get):
    order = await make_order(user, await make_product())
    r = await client.delete(f"{BASE}/{order.id}", headers=auth(user))
    assert r.status_code == 204
    assert (await db_get(Order, order.id)) is None


async def test_delete_foreign_order_is_404_and_keeps_order(
    client, make_user, auth, make_product, make_order, db_get
):
    owner = await make_user()
    stranger = await make_user()
    order = await make_order(owner, await make_product())

    r = await client.delete(f"{BASE}/{order.id}", headers=auth(stranger))
    assert r.status_code == 404
    assert (await db_get(Order, order.id)) is not None


async def test_delete_any_order_as_staff(
    client, staff, user, auth, make_product, make_order, db_get
):
    order = await make_order(user, await make_product())
    r = await client.delete(f"{BASE}/{order.id}", headers=auth(staff))
    assert r.status_code == 204
    assert (await db_get(Order, order.id)) is None


async def test_delete_order_not_found(client, user, auth):
    r = await client.delete(f"{BASE}/999", headers=auth(user))
    assert r.status_code == 404


async def test_delete_order_requires_auth(client, user, make_product, make_order):
    order = await make_order(user, await make_product())
    r = await client.delete(f"{BASE}/{order.id}")
    assert r.status_code in NO_AUTH