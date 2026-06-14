import importlib
import sys

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker


def make_client(tmp_path, monkeypatch) -> TestClient:
    monkeypatch.setenv("APP_SECRET_KEY", "test-secret-key-value")
    monkeypatch.setenv("ADMIN_EMAIL", "admin@example.com")
    monkeypatch.setenv("ADMIN_PASSWORD", "secret-password")
    monkeypatch.setenv("DATABASE_URL", f"sqlite+pysqlite:///{tmp_path.as_posix()}/auth.sqlite3")

    from app.core.config import get_settings

    get_settings.cache_clear()
    sys.modules.pop("app.api.auth", None)
    sys.modules.pop("app.main", None)
    sys.modules.pop("app.db.session", None)

    from app.db.init_db import bootstrap_database
    from app.db.models import Base

    engine = create_engine(f"sqlite+pysqlite:///{tmp_path.as_posix()}/auth.sqlite3", future=True)
    TestingSession = sessionmaker(bind=engine, future=True)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        bootstrap_database(session, "admin@example.com", "secret-password")

    session_module = importlib.import_module("app.db.session")
    main = importlib.import_module("app.main")

    def override_db():
        with TestingSession() as session:
            yield session

    app = main.create_app()
    app.dependency_overrides[session_module.get_db] = override_db
    return TestClient(app)


def test_login_with_admin_credentials_sets_session_cookie_and_returns_admin_email(tmp_path, monkeypatch):
    with make_client(tmp_path, monkeypatch) as client:
        response = client.post(
            "/api/auth/login",
            json={"email": "admin@example.com", "password": "secret-password"},
        )

    assert response.status_code == 200
    assert response.json()["email"] == "admin@example.com"

    from app.core.config import get_settings

    assert get_settings().session_cookie_name in response.cookies


def test_me_without_session_returns_401(tmp_path, monkeypatch):
    with make_client(tmp_path, monkeypatch) as client:
        response = client.get("/api/auth/me")

    assert response.status_code == 401


def test_me_with_session_returns_admin_user(tmp_path, monkeypatch):
    with make_client(tmp_path, monkeypatch) as client:
        client.post(
            "/api/auth/login",
            json={"email": "admin@example.com", "password": "secret-password"},
        )
        response = client.get("/api/auth/me")

    assert response.status_code == 200
    assert response.json()["email"] == "admin@example.com"
    assert response.json()["is_admin"] is True


def test_logout_revokes_existing_session_token(tmp_path, monkeypatch):
    with make_client(tmp_path, monkeypatch) as client:
        login_response = client.post(
            "/api/auth/login",
            json={"email": "admin@example.com", "password": "secret-password"},
        )

        from app.core.config import get_settings

        cookie_name = get_settings().session_cookie_name
        old_token = login_response.cookies[cookie_name]
        logout_response = client.post("/api/auth/logout")
        response = client.get("/api/auth/me", headers={"Cookie": f"{cookie_name}={old_token}"})

    assert logout_response.status_code == 200
    assert logout_response.json() == {"status": "ok"}
    assert response.status_code == 401
