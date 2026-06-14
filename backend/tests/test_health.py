import os

from fastapi.testclient import TestClient

os.environ.setdefault("APP_SECRET_KEY", "test-secret-key-value")
os.environ.setdefault("ADMIN_EMAIL", "admin@example.local")
os.environ.setdefault("ADMIN_PASSWORD", "change-me")
os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://archive:archive@db:5432/archive")

from app.main import app


def test_health_returns_ok():
    response = TestClient(app).get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
