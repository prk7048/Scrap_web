import importlib
import os
import sys

from fastapi.testclient import TestClient
from sqlalchemy import select


os.environ.setdefault("APP_SECRET_KEY", "test-secret-key-value")
os.environ.setdefault("ADMIN_EMAIL", "admin@example.local")
os.environ.setdefault("ADMIN_PASSWORD", "change-me")


def test_health_returns_ok(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_SECRET_KEY", "test-secret-key-value")
    monkeypatch.setenv("ADMIN_EMAIL", "admin@example.local")
    monkeypatch.setenv("ADMIN_PASSWORD", "change-me")
    monkeypatch.setenv("DATABASE_URL", f"sqlite+pysqlite:///{tmp_path.as_posix()}/health.sqlite3")

    from app.core.config import get_settings

    get_settings.cache_clear()
    sys.modules.pop("app.main", None)
    sys.modules.pop("app.db.session", None)
    main = importlib.import_module("app.main")

    with TestClient(main.create_app()) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

    from app.db.models import User
    from app.db.session import SessionLocal

    with SessionLocal() as session:
        user = session.scalar(select(User).where(User.email == "admin@example.local"))

    assert user is not None
    assert user.is_admin is True
