# FastAPI Core Practice

An async REST API built with **FastAPI**, **SQLAlchemy 2** and **PostgreSQL**. It covers JWT authentication with email verification and password reset, a product catalog with image uploads, and an order system with role-based access (regular user / staff). The API is covered by an async **pytest** suite that runs against a separate PostgreSQL test database.

## Features

- **Auth**: registration, login, access and refresh JWTs, logout with token revocation, profile update (including avatar), change password
- **Email flows**: email verification and a password reset code sent over SMTP (async, via background tasks)
- **Security**: bcrypt password hashing, token revocation list (`jti`), reset codes stored as HMAC hashes, attempt limit on reset codes (HTTP 429), timing-attack protection on login
- **Roles**: `is_staff` users manage products and see all orders; regular users only see their own orders
- **Products**: full CRUD, image upload (JPG / PNG / WEBP, max 2 MB, validated by file signature rather than extension)
- **Orders**: authenticated users only; the price is calculated on the server, never taken from the client, and `total_price` is stored as a snapshot
- **Database**: Alembic migrations, async SQLAlchemy sessions (`asyncpg`)
- **Tests**: async pytest suite (users, products, orders, health check) running against an isolated test database, with emails mocked

## Tech Stack

Python 3.10+, FastAPI, Pydantic v2, SQLAlchemy 2 (async), PostgreSQL, Alembic, python-jose (JWT), bcrypt, aiosmtplib, aiofiles, pytest, pytest-asyncio, httpx

## Project Structure

```text
fastapi_core_practice/
├── alembic/              # migrations
├── app/
│   ├── core/             # settings (config.py), token helpers (security.py)
│   ├── users/            # auth routes, models, schemas, mail, token store
│   ├── products/         # product routes, models, schemas, image utils
│   ├── orders/           # order routes, models, schemas
│   ├── tests/            # pytest suite
│   │   ├── conftest.py               # test DB, client, fixtures, mail mock
│   │   ├── test_users.py             # auth and profile endpoints
│   │   ├── test_products.py          # product CRUD and permissions
│   │   ├── test_orders.py            # orders and access rules
│   │   └── test_health_endpoint.py   # /health
│   ├── database.py       # engine, session, Base
│   ├── dependencies.py   # get_current_user, get_current_staff
│   └── main.py           # app entrypoint
├── alembic.ini
├── pytest.ini            # pytest configuration (project root)
├── .env.example
└── requirements.txt
```

## Getting Started

### 1. Clone and install

```bash
git clone https://github.com/ilhomjondevuz/fastapi_core_practice.git
cd fastapi_core_practice

python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure the environment

```bash
cp .env.example .env
```

Then edit `.env`:

| Variable | Description |
| --- | --- |
| `DATABASE_URL` | `postgresql+asyncpg://user:password@localhost:5432/dbname` |
| `SECRET_KEY` | long random string used to sign JWTs (`openssl rand -hex 32`) |
| `ALGORITHM` | `HS256` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | access token lifetime (default in example: `30`) |
| `REFRESH_TOKEN_EXPIRE_DAYS` | refresh token lifetime (default in example: `7`) |
| `VERIFY_TOKEN_EXPIRE_HOURS` | email verification token lifetime (default `24`, optional) |
| `RESET_TOKEN_EXPIRE_MINUTES` | password reset code lifetime (default `15`) |
| `RESET_CODE_MAX_ATTEMPTS` | max wrong reset code attempts (default `5`, optional) |
| `SMTP_HOST`, `SMTP_PORT` | mail server (Gmail: `smtp.gmail.com`, `587`) |
| `SMTP_USER`, `SMTP_PASSWORD`, `EMAIL_FROM` | SMTP credentials (Gmail needs an App Password) |
| `FRONTEND_URL` | used to build links in emails |
| `TEST_DATABASE_URL` | **tests only**: separate database, its name must contain `test` |
| `LOGIN_PASSWORD` | **tests only**: a strong password used for the test users |

Never commit `.env`. It holds real secrets, so keep it in `.gitignore` and share only `.env.example`.

### 3. Create the database and run migrations

```bash
createdb dbname                    # or create it with any PostgreSQL client
alembic upgrade head
```

### 4. Run the server

```bash
uvicorn app.main:app --reload
```

- Swagger UI: http://127.0.0.1:8000/docs
- ReDoc: http://127.0.0.1:8000/redoc

### 5. Make a user staff

There is no endpoint for promoting users, so set the flag directly in the database:

```sql
UPDATE users SET is_staff = true WHERE username = 'your_username';
```

## Testing

The test suite uses **pytest** with **pytest-asyncio** and an in-process `httpx` client, so no server has to be running. Tests talk to a real PostgreSQL database, which keeps behavior identical to production (unique constraints, row locks, `TRUNCATE`).

### Setup

1. Create a separate database for tests:

   ```bash
   createdb dbname_test
   ```

2. Add the test variables to `.env`:

   ```env
   TEST_DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/dbname_test
   LOGIN_PASSWORD=Test!Passw0rd#99
   ```

   - The database name **must contain `test`**. `conftest.py` refuses to start otherwise, because it runs `drop_all` / `TRUNCATE` on that database.
   - `LOGIN_PASSWORD` must satisfy the app's password rules (8+ characters, upper and lower case, a digit, no sequences like `1234`, no 4 repeated characters, must not contain the username or email name).

3. You do **not** need to run Alembic for the test database. The tables are created from the models automatically and dropped when the session ends.

### Run

```bash
python -m pytest -v                                  # everything
python -m pytest app/tests/test_users.py -v          # one file
python -m pytest -k "login" -v                       # by name
python -m pytest -x --lf                             # stop at first failure, rerun last failed
```

Run these from the project root, where `pytest.ini` lives. Keep **one** `pytest.ini` (in the root) so pytest picks the correct `rootdir`.

### What is covered

| File | Covers |
| --- | --- |
| `test_users.py` | register (validation, duplicate email / username / phone), login (username or email, any case), refresh token rotation, logout, `/me` and profile update, email verification, resend verification, forgot / verify / reset password flow (attempt limit, expiry), change password |
| `test_products.py` | public list and pagination, get one, staff-only create / update / delete, discount vs. price rules, photo URLs |
| `test_orders.py` | create order (server-side pricing, ignores client `user_id`), own orders, staff-only `/all`, owner-or-staff get / delete (foreign orders return 404) |
| `test_health_endpoint.py` | `GET /health` |

### How the tests work

- `pytest.ini` sets `asyncio_mode = auto`, so async tests need no decorator, and runs everything in one session event loop.
- The test database is built once per session (`drop_all` + `create_all`), and every test is followed by `TRUNCATE ... RESTART IDENTITY CASCADE`, so each test starts from empty tables with ids from 1.
- The app's `get_session` dependency is overridden to use the test database. The session factory uses `expire_on_commit=False`, the same as `app/database.py`.
- Emails are never sent. The autouse `sent_mail` fixture replaces the mail functions, and tests read the captured messages from `sent_mail.verification` and `sent_mail.reset`.

Useful fixtures from `conftest.py`:

| Fixture | Purpose |
| --- | --- |
| `client` | async HTTP client bound to the app |
| `user`, `staff` | a regular and a staff user |
| `make_user`, `make_product`, `make_order` | factories with overridable fields |
| `auth(user)` | returns the `Authorization: Bearer ...` header for a user |
| `db_get(Model, pk)` | reads an object straight from the database |
| `password` | the plain password behind every test user |
| `sent_mail` | captured outgoing emails |

Example:

```python
async def test_get_own_order(client, user, auth, make_product, make_order):
    order = await make_order(user, await make_product())
    r = await client.get(f"/api/v1/orders/{order.id}", headers=auth(user))
    assert r.status_code == 200
```

### Notes

- A form field sent as an empty string (`""`) is treated by FastAPI as "not provided". To clear an optional form field in `PATCH /me`, the tests send a blank value such as `"   "`.
- Never point `TEST_DATABASE_URL` at your real database.

## API Overview

Protected endpoints expect the header `Authorization: Bearer <access_token>`.

### Auth: `/api/v1/auth`

| Method | Path | Access | Description |
| --- | --- | --- | --- |
| POST | `/register` | public | Create an account (optional avatar) |
| POST | `/login` | public | Get access and refresh tokens |
| POST | `/refresh-token` | public | Exchange a refresh token for new tokens |
| POST | `/logout` | public | Revoke a refresh token (body: `refresh_token`) |
| GET | `/me` | user | Current user profile |
| PATCH | `/me` | user | Update profile |
| POST | `/verify-email` | public | Confirm email with the emailed token |
| POST | `/resend-verification-email` | public | Send the verification email again |
| POST | `/forgot-password` | public | Email a password reset code |
| POST | `/verify-reset-code` | public | Check the reset code |
| POST | `/reset-password` | public | Set a new password |
| POST | `/change-password` | user | Change password (requires the old one) |

### Products: `/api/v1/products`

| Method | Path | Access | Description |
| --- | --- | --- | --- |
| GET | `/` | public | List products (`skip`, `limit`) |
| GET | `/{product_id}` | public | Get one product |
| POST | `/create` | **staff** | Create a product (multipart form, optional `photo`) |
| PATCH | `/{product_id}` | **staff** | Partial update, optionally replace the photo |
| DELETE | `/{product_id}` | **staff** | Delete a product and its image |

### Orders: `/api/v1/orders`

| Method | Path | Access | Description |
| --- | --- | --- | --- |
| POST | `/create` | user | Place an order (`product_id`, `quantity`) |
| GET | `/my` | user | Your own orders (`skip`, `limit`) |
| GET | `/all` | **staff** | All orders |
| GET | `/{order_id}` | owner or staff | Get one order |
| DELETE | `/{order_id}` | owner or staff | Cancel (delete) an order |

Quick example:

```bash
# login (username_or_email accepts either one)
curl -X POST http://127.0.0.1:8000/api/v1/auth/login -H "Content-Type: application/json" \
  -d '{"username_or_email": "john", "password": "..."}'

# place an order
curl -X POST http://127.0.0.1:8000/api/v1/orders/create \
  -H "Authorization: Bearer <access_token>" -H "Content-Type: application/json" \
  -d '{"product_id": 1, "quantity": 2}'
```

> The exact register fields are listed in Swagger (`/docs`).

## Database Migrations

```bash
alembic revision --autogenerate -m "describe the change"   # create a migration
alembic upgrade head                                       # apply
alembic downgrade -1                                       # roll back one step
```

New models must be imported in `app/init_db.py` so Alembic can see them. Run migrations only against the main database (`DATABASE_URL`), never against the test database.

## Roadmap

- [ ] Send the verification email (`send_verification_email` is still a stub)
- [ ] Order status workflow (`status` column exists; add it to the schema and a staff PATCH endpoint)
- [x] Pytest test suite (users, products, orders)
- [ ] Tests for avatar upload / removal and for the mail functions
- [ ] Dockerfile and docker-compose (app + PostgreSQL)
- [ ] Rate limiting on login and email endpoints

## Author

**Ilhomjon Rakhimov**, Backend Developer (Python / FastAPI)