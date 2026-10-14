from environs import Env
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

env = Env()
env.read_env()


def test_login():
    payload = {
        "username_or_email": env.str("LOGIN_USERNAME_OR_EMAIL"),
        "password": env.str("LOGIN_PASSWORD"),
    }

    response = client.post("/api/v1/auth/login", json=payload)

    assert response.status_code == 200