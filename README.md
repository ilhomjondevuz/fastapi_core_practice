# FastAPI Core Practice

A practical FastAPI project for reviewing and strengthening core backend development concepts.

## 🎯 Goal

The goal of this project is to practice and consolidate the core concepts of FastAPI through practical tasks and a structured mini project.

## 📚 Topics

* FastAPI application structure
* Routers
* Pydantic schemas
* Request and response validation
* Path and Query parameters
* Dependencies
* Dependency Injection
* HTTPException
* Error handling
* Middleware
* Async programming
* CRUD operations
* SQLAlchemy
* PostgreSQL
* Authentication
* Testing with Pytest

## 🛠️ Technologies

* Python
* FastAPI
* Pydantic
* SQLAlchemy
* PostgreSQL
* Pytest
* Docker
* Git

## 📁 Project Structure

```text
fastapi_core_practice/
├── app/
│   ├── main.py
│   ├── routers/
│   ├── schemas/
│   ├── models/
│   ├── services/
│   ├── dependencies.py
│   └── core/
│
├── tests/
├── .env
├── .gitignore
├── README.md
└── requirements.txt
```

## 🚀 Running the Project

Create and activate a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Run the application:

```bash
uvicorn app.main:app --reload
```

API documentation:

```text
http://127.0.0.1:8000/docs
```

Alternative documentation:

```text
http://127.0.0.1:8000/redoc
```

## 👨‍💻 Author

**Ilhomjon Rakhimov**

Backend Developer — Python / FastAPI
