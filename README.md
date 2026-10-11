# FastAPI Core Practice

An async REST API built with **FastAPI**, **SQLAlchemy 2** and **PostgreSQL**. It covers JWT authentication with email verification and password reset, a product catalog with image uploads, and an order system with role-based access (regular user / staff).

## Features

- **Auth**: registration, login, access and refresh JWTs, logout with token revocation, profile update (including avatar), change password
- **Email flows**: email verification and a password reset code sent over SMTP (async, via background tasks)
- **Security**: bcrypt password hashing, token revocation list (`jti`), reset codes stored as HMAC hashes, attempt limit on reset codes (HTTP 429), timing-attack protection on login
- **Roles**: `is_staff` users manage products and see all orders; regular users only see their own orders
- **Products**: full CRUD, image upload (JPG / PNG / WEBP, max 2 MB, validated by file signature rather than extension)
- **Orders**: authenticated users only; the price is calculated on the server, never taken from the client, and `total_price` is stored as a snapshot
- **Database**: Alembic migrations, async SQLAlchemy sessions (`asyncpg`)

## Tech Stack

Python 3.10+, FastAPI, Pydantic v2, SQLAlchemy 2 (async), PostgreSQL, Alembic, python-jose (JWT), bcrypt, aiosmtplib, aiofiles

## Project Structure

```text
fastapi_core_practice/
├── alembic/              # migrations
├── app/
│   ├── core/             # settings (config.py), token helpers (security.py)
│   ├── users/            # auth routes, models, schemas, mail, token store
│   ├── products/         # product routes, models, schemas, image utils
│   ├── orders/           # order routes, models, schemas
│   ├── database.py       # engine, session, Base
│   ├── dependencies.py   # get_current_user, get_current_staff
│   └── main.py           # app entrypoint
├── alembic.ini
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
| `RESET_TOKEN_EXPIRE_MINUTES` | password reset code lifetime (default `15`) |
| `RESET_CODE_MAX_ATTEMPTS` | max wrong reset code attempts (default `5`, optional) |
| `SMTP_HOST`, `SMTP_PORT` | mail server (Gmail: `smtp.gmail.com`, `587`) |
| `SMTP_USER`, `SMTP_PASSWORD`, `EMAIL_FROM` | SMTP credentials (Gmail needs an App Password) |
| `FRONTEND_URL` | used to build links in emails |

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

## API Overview

Protected endpoints expect the header `Authorization: Bearer <access_token>`.

### Auth: `/api/v1/auth`

| Method | Path | Access | Description |
| --- | --- | --- | --- |
| POST | `/register` | public | Create an account (optional avatar) |
| POST | `/login` | public | Get access and refresh tokens |
| POST | `/refresh-token` | public | Exchange a refresh token for new tokens |
| POST | `/logout` | user | Revoke the current token |
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
# login
curl -X POST http://127.0.0.1:8000/api/v1/auth/login -H "Content-Type: application/json" \
  -d '{"username": "john", "password": "..."}'

# place an order
curl -X POST http://127.0.0.1:8000/api/v1/orders/create \
  -H "Authorization: Bearer <access_token>" -H "Content-Type: application/json" \
  -d '{"product_id": 1, "quantity": 2}'
```

> The exact login and register fields are listed in Swagger (`/docs`).

## Database Migrations

```bash
alembic revision --autogenerate -m "describe the change"   # create a migration
alembic upgrade head                                       # apply
alembic downgrade -1                                       # roll back one step
```

New models must be imported in `app/init_db.py` so Alembic can see them.

## Roadmap

- [ ] Send the verification email (`send_verification_email` is still a stub)
- [ ] Order status workflow (`status` column exists; add it to the schema and a staff PATCH endpoint)
- [ ] Pytest test suite
- [ ] Dockerfile and docker-compose (app + PostgreSQL)
- [ ] Rate limiting on login and email endpoints

## Author

**Ilhomjon Rakhimov**, Backend Developer (Python / FastAPI)