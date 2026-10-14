from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import func, select, update

from app.core.config import settings
from app.users.models import PasswordResetCode, User
from app.users.security import (
    create_access_token,
    create_refresh_token,
    create_reset_confirm_token,
    create_verify_token,
)

BASE = "/api/v1/auth"
NO_AUTH = (401, 403)  # tokensiz so'rovda qaytadigan status (security sxemasiga bog'liq)
INVALID_INPUT = (400, 422)
NEW_PASSWORD = "N3w!Passw0rd#77"


def register_data(password: str, **overrides) -> dict:
    data = {
        "username": "john_doe",
        "email": "john@example.com",
        "password1": password,
        "password2": password,
        "first_name": "John",
        "last_name": "Doe",
        "phone": "+998901234567",
    }
    data.update(overrides)
    return data


# ================================================================= register
async def test_register_success(client, sent_mail, password, db_get):
    r = await client.post(
        f"{BASE}/register",
        data=register_data(password, email="John@Example.COM"),
    )
    assert r.status_code == 201
    body = r.json()
    assert body["success"] is True
    assert body["data"]["username"] == "john_doe"
    assert body["data"]["email"] == "john@example.com"  # kichik harfga o'tadi
    assert body["data"]["avatar"] is None
    assert "password" not in body["data"]

    db_user = await db_get(User, body["data"]["id"])
    assert db_user.password != password  # hash saqlanadi
    assert not db_user.is_verified

    # tasdiqlash xati yuboriladi
    assert len(sent_mail.verification) == 1
    assert sent_mail.verification[0][0] == "john@example.com"


async def test_register_password_mismatch(client, password):
    r = await client.post(
        f"{BASE}/register",
        data=register_data(password, password2=password + "x"),
    )
    assert r.status_code == 400


async def test_register_weak_password(client):
    r = await client.post(
        f"{BASE}/register", data=register_data("12345678")
    )
    assert r.status_code in INVALID_INPUT


async def test_register_duplicate_email_case_insensitive(client, make_user, password):
    await make_user(email="john@example.com")
    r = await client.post(
        f"{BASE}/register",
        data=register_data(password, username="other_name", email="JOHN@example.com"),
    )
    assert r.status_code == 409


async def test_register_duplicate_username_case_insensitive(client, make_user, password):
    await make_user(username="john_doe")
    r = await client.post(
        f"{BASE}/register",
        data=register_data(password, username="JOHN_DOE", email="new@example.com"),
    )
    assert r.status_code == 409


async def test_register_invalid_email(client, password):
    r = await client.post(
        f"{BASE}/register", data=register_data(password, email="not-an-email")
    )
    assert r.status_code == 422


async def test_register_username_too_short(client, password):
    r = await client.post(
        f"{BASE}/register", data=register_data(password, username="ab")
    )
    assert r.status_code == 422


async def test_register_invalid_phone(client, password):
    r = await client.post(
        f"{BASE}/register", data=register_data(password, phone="abc")
    )
    assert r.status_code in INVALID_INPUT


# ===================================================================== login
@pytest.mark.parametrize("field", ["username", "email"])
@pytest.mark.parametrize("transform", [str, str.upper], ids=["exact", "upper"])
async def test_login_success(client, user, password, field, transform):
    r = await client.post(
        f"{BASE}/login",
        json={"username_or_email": transform(getattr(user, field)), "password": password},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    assert body["token_type"] == "bearer"
    assert body["data"]["id"] == user.id

    # olingan access token ishlaydi
    me = await client.get(
        f"{BASE}/me", headers={"Authorization": f"Bearer {body['access_token']}"}
    )
    assert me.status_code == 200


async def test_login_wrong_password(client, user):
    r = await client.post(
        f"{BASE}/login",
        json={"username_or_email": user.username, "password": "wrong-password"},
    )
    assert r.status_code == 401


async def test_login_unknown_user_same_error_as_wrong_password(client, user):
    wrong_pw = await client.post(
        f"{BASE}/login",
        json={"username_or_email": user.username, "password": "wrong-password"},
    )
    unknown = await client.post(
        f"{BASE}/login",
        json={"username_or_email": "nobody", "password": "wrong-password"},
    )
    assert unknown.status_code == 401
    # user bor-yo'qligi oshkor bo'lmasligi kerak
    assert unknown.json() == wrong_pw.json()


async def test_login_inactive_user(client, make_user, password):
    inactive = await make_user(is_active=False)
    r = await client.post(
        f"{BASE}/login",
        json={"username_or_email": inactive.username, "password": password},
    )
    assert r.status_code == 403


# ============================================================ refresh-token
async def test_refresh_token_success_and_rotation(client, user):
    old = create_refresh_token(user.id)
    r = await client.post(f"{BASE}/refresh-token", json={"refresh_token": old})
    assert r.status_code == 200
    body = r.json()
    assert body["access_token"] and body["refresh_token"]

    # eski token endi yaroqsiz (rotation)
    again = await client.post(f"{BASE}/refresh-token", json={"refresh_token": old})
    assert again.status_code == 401

    # yangisi esa ishlaydi
    nxt = await client.post(
        f"{BASE}/refresh-token", json={"refresh_token": body["refresh_token"]}
    )
    assert nxt.status_code == 200


async def test_refresh_token_rejects_access_token(client, user):
    r = await client.post(
        f"{BASE}/refresh-token", json={"refresh_token": create_access_token(user.id)}
    )
    assert r.status_code == 401


async def test_refresh_token_rejects_garbage(client):
    r = await client.post(f"{BASE}/refresh-token", json={"refresh_token": "garbage"})
    assert r.status_code == 401


async def test_refresh_token_inactive_user(client, make_user):
    inactive = await make_user(is_active=False)
    r = await client.post(
        f"{BASE}/refresh-token",
        json={"refresh_token": create_refresh_token(inactive.id)},
    )
    assert r.status_code == 401


# ===================================================================== logout
async def test_logout_revokes_refresh_token(client, user):
    token = create_refresh_token(user.id)
    r = await client.post(f"{BASE}/logout", json={"refresh_token": token})
    assert r.status_code == 204

    after = await client.post(f"{BASE}/refresh-token", json={"refresh_token": token})
    assert after.status_code == 401


async def test_logout_is_idempotent(client, user):
    token = create_refresh_token(user.id)
    first = await client.post(f"{BASE}/logout", json={"refresh_token": token})
    second = await client.post(f"{BASE}/logout", json={"refresh_token": token})
    assert first.status_code == second.status_code == 204


async def test_logout_with_garbage_token_is_204(client):
    r = await client.post(f"{BASE}/logout", json={"refresh_token": "garbage"})
    assert r.status_code == 204


# ======================================================================== me
async def test_me_requires_auth(client):
    r = await client.get(f"{BASE}/me")
    assert r.status_code in NO_AUTH


async def test_me_returns_current_user(client, user, auth):
    r = await client.get(f"{BASE}/me", headers=auth(user))
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == user.id
    assert body["username"] == user.username
    assert body["email"] == user.email
    assert "password" not in body


async def test_update_me_changes_fields(client, user, auth):
    r = await client.patch(
        f"{BASE}/me",
        data={"first_name": "  Ali ", "last_name": "Valiyev", "phone": "+998901112233"},
        headers=auth(user),
    )
    assert r.status_code == 200
    body = r.json()
    assert body["first_name"] == "Ali"  # strip qilinadi
    assert body["last_name"] == "Valiyev"
    assert body["phone"] == "+998901112233"


async def test_update_me_partial_keeps_other_fields(client, make_user, auth):
    u = await make_user(first_name="Old", last_name="Name")
    r = await client.patch(
        f"{BASE}/me", data={"first_name": "New"}, headers=auth(u)
    )
    assert r.status_code == 200
    assert r.json()["first_name"] == "New"
    assert r.json()["last_name"] == "Name"


async def test_update_me_empty_string_clears_field(client, make_user, auth):
    u = await make_user(first_name="Old")
    r = await client.patch(f"{BASE}/me", data={"first_name": ""}, headers=auth(u))
    assert r.status_code == 200
    assert r.json()["first_name"] is None


async def test_update_me_without_fields_is_400(client, user, auth):
    r = await client.patch(f"{BASE}/me", data={}, headers=auth(user))
    assert r.status_code == 400


async def test_update_me_invalid_phone(client, user, auth):
    r = await client.patch(f"{BASE}/me", data={"phone": "abc"}, headers=auth(user))
    assert r.status_code in INVALID_INPUT


async def test_update_me_duplicate_phone_is_409(client, make_user, auth):
    await make_user(phone="+998901112233")
    me = await make_user()
    r = await client.patch(
        f"{BASE}/me", data={"phone": "+998901112233"}, headers=auth(me)
    )
    assert r.status_code == 409


async def test_update_me_requires_auth(client):
    r = await client.patch(f"{BASE}/me", data={"first_name": "X"})
    assert r.status_code in NO_AUTH


# ============================================================== verify-email
async def test_verify_email_success(client, make_user, db_get):
    u = await make_user(is_verified=False)
    r = await client.post(
        f"{BASE}/verify-email", json={"token": create_verify_token(u.id)}
    )
    assert r.status_code == 200
    assert (await db_get(User, u.id)).is_verified is True


async def test_verify_email_is_idempotent(client, make_user):
    u = await make_user(is_verified=False)
    token = create_verify_token(u.id)
    first = await client.post(f"{BASE}/verify-email", json={"token": token})
    second = await client.post(f"{BASE}/verify-email", json={"token": token})
    assert first.status_code == second.status_code == 200


async def test_verify_email_garbage_token(client):
    r = await client.post(f"{BASE}/verify-email", json={"token": "garbage"})
    assert r.status_code == 400


async def test_verify_email_wrong_token_type(client, make_user):
    u = await make_user(is_verified=False)
    r = await client.post(
        f"{BASE}/verify-email", json={"token": create_access_token(u.id)}
    )
    assert r.status_code == 400


async def test_verify_email_inactive_user(client, make_user):
    u = await make_user(is_verified=False, is_active=False)
    r = await client.post(
        f"{BASE}/verify-email", json={"token": create_verify_token(u.id)}
    )
    assert r.status_code == 400


# ================================================= resend-verification-email
async def test_resend_verification_sends_mail_to_unverified(client, make_user, sent_mail):
    u = await make_user(is_verified=False)
    r = await client.post(f"{BASE}/resend-verification-email", json={"email": u.email})
    assert r.status_code == 200
    assert len(sent_mail.verification) == 1
    assert sent_mail.verification[0][0] == u.email


async def test_resend_verification_same_response_for_all_cases(
    client, make_user, sent_mail
):
    unverified = await make_user(is_verified=False)
    verified = await make_user(is_verified=True)

    responses = []
    for email in (unverified.email, verified.email, "nobody@example.com"):
        r = await client.post(f"{BASE}/resend-verification-email", json={"email": email})
        assert r.status_code == 200
        responses.append(r.json())

    # email bor-yo'qligi oshkor bo'lmasligi uchun javoblar bir xil
    assert responses[0] == responses[1] == responses[2]
    # xat faqat tasdiqlanmagan userga ketgan
    assert [m[0] for m in sent_mail.verification] == [unverified.email]


# ============================================================ forgot-password
async def start_reset(client, email: str) -> str:
    r = await client.post(f"{BASE}/forgot-password", json={"email": email})
    assert r.status_code == 200
    return r.json()["reset_token"]


async def count_reset_codes(session_maker) -> int:
    async with session_maker() as s:
        return (
            await s.execute(select(func.count()).select_from(PasswordResetCode))
        ).scalar_one()


async def test_forgot_password_existing_user(client, user, sent_mail, session_maker):
    token = await start_reset(client, user.email)
    assert token
    assert len(sent_mail.reset) == 1
    email, code = sent_mail.reset[0]
    assert email == user.email
    assert len(code) == 6
    assert await count_reset_codes(session_maker) == 1


async def test_forgot_password_unknown_email_looks_the_same(
    client, user, sent_mail, session_maker
):
    known = await client.post(f"{BASE}/forgot-password", json={"email": user.email})
    unknown = await client.post(
        f"{BASE}/forgot-password", json={"email": "nobody@example.com"}
    )
    assert unknown.status_code == 200
    assert unknown.json()["reset_token"]
    assert unknown.json()["message"] == known.json()["message"]
    # nomavjud email uchun xat ketmaydi va bazaga yozilmaydi
    assert len(sent_mail.reset) == 1
    assert await count_reset_codes(session_maker) == 1


async def test_forgot_password_new_request_invalidates_old_code(client, user, sent_mail):
    first_token = await start_reset(client, user.email)
    first_code = sent_mail.reset[0][1]
    await start_reset(client, user.email)

    r = await client.post(
        f"{BASE}/verify-reset-code",
        json={"reset_token": first_token, "code": first_code},
    )
    assert r.status_code == 400


# ======================================= verify-reset-code + reset-password
async def test_full_password_reset_flow(client, user, sent_mail, password):
    # 1-qadam
    reset_token = await start_reset(client, user.email)
    code = sent_mail.reset[-1][1]

    # 2-qadam
    r = await client.post(
        f"{BASE}/verify-reset-code", json={"reset_token": reset_token, "code": code}
    )
    assert r.status_code == 200
    confirm_token = r.json()["reset_token"]

    # 3-qadam
    r = await client.post(
        f"{BASE}/reset-password",
        json={
            "reset_token": confirm_token,
            "new_password1": NEW_PASSWORD,
            "new_password2": NEW_PASSWORD,
        },
    )
    assert r.status_code == 200

    # yangi parol bilan kirish mumkin, eskisi bilan yo'q
    ok = await client.post(
        f"{BASE}/login",
        json={"username_or_email": user.username, "password": NEW_PASSWORD},
    )
    assert ok.status_code == 200
    old = await client.post(
        f"{BASE}/login",
        json={"username_or_email": user.username, "password": password},
    )
    assert old.status_code == 401

    # kod bir martalik: shu token bilan qayta o'zgartirib bo'lmaydi
    again = await client.post(
        f"{BASE}/reset-password",
        json={
            "reset_token": confirm_token,
            "new_password1": NEW_PASSWORD + "x",
            "new_password2": NEW_PASSWORD + "x",
        },
    )
    assert again.status_code == 400


async def test_verify_reset_code_wrong_code(client, user, sent_mail):
    reset_token = await start_reset(client, user.email)
    real = sent_mail.reset[-1][1]
    wrong = "000000" if real != "000000" else "111111"
    r = await client.post(
        f"{BASE}/verify-reset-code", json={"reset_token": reset_token, "code": wrong}
    )
    assert r.status_code == 400


async def test_verify_reset_code_garbage_token(client):
    r = await client.post(
        f"{BASE}/verify-reset-code", json={"reset_token": "garbage", "code": "123456"}
    )
    assert r.status_code == 400


async def test_verify_reset_code_attempts_limit(client, user, sent_mail):
    reset_token = await start_reset(client, user.email)
    real = sent_mail.reset[-1][1]
    wrong = "000000" if real != "000000" else "111111"

    for _ in range(settings.RESET_CODE_MAX_ATTEMPTS):
        r = await client.post(
            f"{BASE}/verify-reset-code",
            json={"reset_token": reset_token, "code": wrong},
        )
        assert r.status_code == 400

    # limit tugagach to'g'ri kod ham o'tmaydi
    r = await client.post(
        f"{BASE}/verify-reset-code", json={"reset_token": reset_token, "code": real}
    )
    assert r.status_code == 429


async def test_verify_reset_code_expired(client, user, sent_mail, session_maker):
    reset_token = await start_reset(client, user.email)
    code = sent_mail.reset[-1][1]

    async with session_maker() as s:
        await s.execute(
            update(PasswordResetCode).values(
                expires_at=datetime.now(timezone.utc) - timedelta(minutes=1)
            )
        )
        await s.commit()

    r = await client.post(
        f"{BASE}/verify-reset-code", json={"reset_token": reset_token, "code": code}
    )
    assert r.status_code == 400


async def test_reset_password_requires_verified_code(client, user, session_maker):
    await start_reset(client, user.email)
    async with session_maker() as s:
        row = (await s.execute(select(PasswordResetCode))).scalars().one()
        reset_id = row.id

    # 2-qadamdan o'tmasdan to'g'ridan-to'g'ri 3-tokenni yasab ko'ramiz
    r = await client.post(
        f"{BASE}/reset-password",
        json={
            "reset_token": create_reset_confirm_token(reset_id),
            "new_password1": NEW_PASSWORD,
            "new_password2": NEW_PASSWORD,
        },
    )
    assert r.status_code == 400


async def test_reset_password_mismatch(client):
    r = await client.post(
        f"{BASE}/reset-password",
        json={
            "reset_token": "whatever",
            "new_password1": NEW_PASSWORD,
            "new_password2": NEW_PASSWORD + "x",
        },
    )
    assert r.status_code == 400


async def test_reset_password_garbage_token(client):
    r = await client.post(
        f"{BASE}/reset-password",
        json={
            "reset_token": "garbage",
            "new_password1": NEW_PASSWORD,
            "new_password2": NEW_PASSWORD,
        },
    )
    assert r.status_code == 400


# ========================================================== change-password
async def test_change_password_success(client, user, auth, password):
    r = await client.post(
        f"{BASE}/change-password",
        json={
            "old_password": password,
            "new_password1": NEW_PASSWORD,
            "new_password2": NEW_PASSWORD,
        },
        headers=auth(user),
    )
    assert r.status_code == 200

    ok = await client.post(
        f"{BASE}/login",
        json={"username_or_email": user.username, "password": NEW_PASSWORD},
    )
    assert ok.status_code == 200
    old = await client.post(
        f"{BASE}/login",
        json={"username_or_email": user.username, "password": password},
    )
    assert old.status_code == 401


async def test_change_password_wrong_old_password(client, user, auth):
    r = await client.post(
        f"{BASE}/change-password",
        json={
            "old_password": "wrong-password",
            "new_password1": NEW_PASSWORD,
            "new_password2": NEW_PASSWORD,
        },
        headers=auth(user),
    )
    assert r.status_code == 400


async def test_change_password_new_passwords_mismatch(client, user, auth, password):
    r = await client.post(
        f"{BASE}/change-password",
        json={
            "old_password": password,
            "new_password1": NEW_PASSWORD,
            "new_password2": NEW_PASSWORD + "x",
        },
        headers=auth(user),
    )
    assert r.status_code == 400


async def test_change_password_same_as_old(client, user, auth, password):
    r = await client.post(
        f"{BASE}/change-password",
        json={
            "old_password": password,
            "new_password1": password,
            "new_password2": password,
        },
        headers=auth(user),
    )
    assert r.status_code == 400


async def test_change_password_weak_new_password(client, user, auth, password):
    r = await client.post(
        f"{BASE}/change-password",
        json={
            "old_password": password,
            "new_password1": "12345678",
            "new_password2": "12345678",
        },
        headers=auth(user),
    )
    assert r.status_code in INVALID_INPUT


async def test_change_password_requires_auth(client, password):
    r = await client.post(
        f"{BASE}/change-password",
        json={
            "old_password": password,
            "new_password1": NEW_PASSWORD,
            "new_password2": NEW_PASSWORD,
        },
    )
    assert r.status_code in NO_AUTH