# Personal Web Archive MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first usable personal web archive MVP: authenticated web UI, URL save pipeline, background capture, searchable item list, browser extension save, and local backups.

**Architecture:** Use Docker Compose to run a Vite React frontend, FastAPI backend, Postgres database, and Python worker. All capture sources call one backend `save_url` API, which creates an item and enqueues background jobs; workers write page artifacts to a local data directory and update item status. The first version uses Postgres tables for jobs and search rather than adding Redis or a separate search engine.

**Tech Stack:** Vite React, TypeScript, Python 3.12, FastAPI, SQLAlchemy 2, Alembic, Postgres 16, Playwright, pytest, Vitest, Docker Compose, Chrome/Edge Manifest V3 extension.

---

## File Structure

- `docker-compose.yml`: local service orchestration for frontend, backend, worker, database, and one-shot backup commands.
- `.env.example`: documented defaults for ports, database URL, auth secret, data directory, and backup directory.
- `backend/pyproject.toml`: Python package, test, lint, and dependency configuration.
- `backend/app/main.py`: FastAPI app assembly, CORS, routers, startup checks.
- `backend/app/core/config.py`: environment settings.
- `backend/app/core/security.py`: password hashing, session token creation, session cookie helpers.
- `backend/app/db/session.py`: SQLAlchemy engine and session dependency.
- `backend/app/db/models.py`: database models for users, sessions, items, artifacts, topics, tags, jobs, and backups.
- `backend/app/db/init_db.py`: bootstrap admin account and tables for MVP.
- `backend/app/schemas/*.py`: Pydantic request and response models.
- `backend/app/services/url_normalize.py`: URL canonicalization and duplicate key generation.
- `backend/app/services/items.py`: save URL, list/search items, item detail, retry jobs.
- `backend/app/services/jobs.py`: Postgres-backed job enqueue, claim, complete, fail.
- `backend/app/services/capture.py`: metadata, body text, HTML, screenshot, and PDF-lite capture.
- `backend/app/services/ai.py`: deterministic MVP topic, tag, summary, and recommendation stubs with provider boundary.
- `backend/app/services/backup.py`: database dump and artifact directory backup orchestration.
- `backend/app/api/auth.py`: login/logout/session endpoints.
- `backend/app/api/items.py`: save, paste, list, detail, retry endpoints.
- `backend/app/api/topics.py`: topic tree endpoints.
- `backend/app/api/recommendations.py`: recommendation feed endpoints.
- `backend/app/api/backups.py`: backup status and manual run endpoints.
- `backend/app/worker.py`: polling worker loop for capture, AI, and backup jobs.
- `backend/tests/*`: pytest coverage for URL normalization, save flow, jobs, auth, capture fallbacks, search, and backup manifests.
- `frontend/package.json`: Vite React app scripts.
- `frontend/src/api/client.ts`: typed API wrapper.
- `frontend/src/App.tsx`: layout shell.
- `frontend/src/features/auth/*`: login and session state.
- `frontend/src/features/items/*`: save dialog, item list, item detail, status badges, search.
- `frontend/src/features/topics/*`: AI topic tree.
- `frontend/src/features/recommendations/*`: recommendation card feed.
- `frontend/src/features/backups/*`: backup status panel.
- `extension/manifest.json`: Chrome/Edge extension manifest.
- `extension/src/background.ts`: current tab save action.
- `extension/src/popup.html`: popup shell.
- `extension/src/popup.ts`: save status UI.
- `docs/superpowers/specs/2026-06-14-personal-web-archive-design.md`: approved design source.

---

### Task 1: Repository Scaffold And Runtime Configuration

**Files:**
- Create: `.gitignore`
- Create: `.env.example`
- Create: `docker-compose.yml`
- Create: `backend/pyproject.toml`
- Create: `backend/app/__init__.py`
- Create: `backend/app/core/config.py`
- Create: `backend/app/main.py`
- Create: `backend/tests/test_health.py`

- [ ] **Step 1: Initialize git if needed**

Run:

```powershell
git rev-parse --is-inside-work-tree
```

Expected if not initialized:

```text
fatal: not a git repository (or any of the parent directories): .git
```

If not initialized, run:

```powershell
git init
```

Expected:

```text
Initialized empty Git repository
```

- [ ] **Step 2: Create `.gitignore`**

```gitignore
.env
.venv/
__pycache__/
.pytest_cache/
.ruff_cache/
node_modules/
dist/
coverage/
playwright-report/
data/
backups/
.superpowers/
*.pyc
```

- [ ] **Step 3: Create `.env.example`**

```env
APP_ENV=development
APP_SECRET_KEY=change-me-in-local-env
ADMIN_EMAIL=admin@example.local
ADMIN_PASSWORD=change-me
DATABASE_URL=postgresql+psycopg://archive:archive@db:5432/archive
PUBLIC_API_BASE_URL=http://localhost:8000
BACKEND_CORS_ORIGINS=http://localhost:5173
DATA_DIR=/app/data
BACKUP_DIR=/app/backups
SESSION_COOKIE_NAME=archive_session
SESSION_TTL_DAYS=90
CAPTURE_TIMEOUT_MS=30000
```

- [ ] **Step 4: Create `docker-compose.yml`**

```yaml
services:
  db:
    image: postgres:16
    environment:
      POSTGRES_USER: archive
      POSTGRES_PASSWORD: archive
      POSTGRES_DB: archive
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U archive -d archive"]
      interval: 5s
      timeout: 5s
      retries: 10

  backend:
    build:
      context: ./backend
    env_file: .env
    ports:
      - "8000:8000"
    volumes:
      - ./data:/app/data
      - ./backups:/app/backups
    depends_on:
      db:
        condition: service_healthy
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

  worker:
    build:
      context: ./backend
    env_file: .env
    volumes:
      - ./data:/app/data
      - ./backups:/app/backups
    depends_on:
      db:
        condition: service_healthy
    command: python -m app.worker

  frontend:
    build:
      context: ./frontend
    env_file: .env
    ports:
      - "5173:5173"
    depends_on:
      - backend
    command: npm run dev -- --host 0.0.0.0

volumes:
  postgres_data:
```

- [ ] **Step 5: Create `backend/pyproject.toml`**

```toml
[project]
name = "personal-web-archive-backend"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
  "fastapi>=0.115.0",
  "uvicorn[standard]>=0.30.0",
  "pydantic-settings>=2.4.0",
  "sqlalchemy>=2.0.32",
  "psycopg[binary]>=3.2.1",
  "passlib[bcrypt]>=1.7.4",
  "python-multipart>=0.0.9",
  "beautifulsoup4>=4.12.3",
  "readability-lxml>=0.8.1",
  "playwright>=1.46.0",
]

[project.optional-dependencies]
dev = [
  "pytest>=8.3.0",
  "pytest-asyncio>=0.23.8",
  "ruff>=0.5.6",
]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]
```

- [ ] **Step 6: Create `backend/app/core/config.py`**

```python
from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    app_secret_key: str = Field(min_length=16)
    admin_email: str
    admin_password: str
    database_url: str
    public_api_base_url: str = "http://localhost:8000"
    backend_cors_origins: str = "http://localhost:5173"
    data_dir: str = "data"
    backup_dir: str = "backups"
    session_cookie_name: str = "archive_session"
    session_ttl_days: int = 90
    capture_timeout_ms: int = 30_000

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.backend_cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

- [ ] **Step 7: Create `backend/app/main.py`**

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Personal Web Archive", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
```

- [ ] **Step 8: Create `backend/tests/test_health.py`**

```python
from fastapi.testclient import TestClient

from app.main import app


def test_health_returns_ok():
    response = TestClient(app).get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

- [ ] **Step 9: Run backend health test**

Run:

```powershell
cd backend
python -m pip install -e ".[dev]"
pytest tests/test_health.py -v
```

Expected:

```text
tests/test_health.py::test_health_returns_ok PASSED
```

- [ ] **Step 10: Commit**

```powershell
git add .gitignore .env.example docker-compose.yml backend
git commit -m "chore: scaffold archive services"
```

---

### Task 2: Database Models And Bootstrap Admin

**Files:**
- Create: `backend/app/db/__init__.py`
- Create: `backend/app/db/session.py`
- Create: `backend/app/db/models.py`
- Create: `backend/app/db/init_db.py`
- Create: `backend/tests/test_db_bootstrap.py`

- [ ] **Step 1: Write failing bootstrap test**

```python
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.db.init_db import bootstrap_database
from app.db.models import Base, User


def test_bootstrap_creates_admin_user():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        bootstrap_database(session, admin_email="admin@example.local", admin_password="secret-password")
        user = session.scalar(select(User).where(User.email == "admin@example.local"))

    assert user is not None
    assert user.password_hash != "secret-password"
    assert user.is_admin is True
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
cd backend
pytest tests/test_db_bootstrap.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'app.db'`.

- [ ] **Step 3: Create `backend/app/db/models.py`**

```python
import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class ItemStatus(str, enum.Enum):
    inbox = "inbox"
    queued = "queued"
    processing = "processing"
    preserved = "preserved"
    classification_needed = "classification_needed"
    failed = "failed"


class JobStatus(str, enum.Enum):
    queued = "queued"
    running = "running"
    complete = "complete"
    failed = "failed"


class ArtifactType(str, enum.Enum):
    html = "html"
    screenshot = "screenshot"
    pdf = "pdf"
    transcript = "transcript"
    original_file = "original_file"
    text = "text"


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)


class SessionToken(Base):
    __tablename__ = "session_tokens"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)


class Topic(Base):
    __tablename__ = "topics"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    parent_id: Mapped[str | None] = mapped_column(ForeignKey("topics.id"), nullable=True)
    confidence: Mapped[int] = mapped_column(Integer, nullable=False, default=100)


class Tag(Base):
    __tablename__ = "tags"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)


class Item(Base):
    __tablename__ = "items"
    __table_args__ = (UniqueConstraint("normalized_url", name="uq_items_normalized_url"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    original_url: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_url: Mapped[str] = mapped_column(Text, nullable=False)
    source_domain: Mapped[str] = mapped_column(String(255), nullable=False)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    body_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_recommendation_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[ItemStatus] = mapped_column(Enum(ItemStatus), nullable=False, default=ItemStatus.inbox)
    classification_status: Mapped[str] = mapped_column(String(40), nullable=False, default="pending")
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    saved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    last_processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    artifacts: Mapped[list["Artifact"]] = relationship(back_populates="item", cascade="all, delete-orphan")


class Artifact(Base):
    __tablename__ = "artifacts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    item_id: Mapped[str] = mapped_column(ForeignKey("items.id", ondelete="CASCADE"), nullable=False)
    artifact_type: Mapped[ArtifactType] = mapped_column(Enum(ArtifactType), nullable=False)
    path: Mapped[str] = mapped_column(Text, nullable=False)
    mime_type: Mapped[str] = mapped_column(String(120), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)

    item: Mapped[Item] = relationship(back_populates="artifacts")


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    job_type: Mapped[str] = mapped_column(String(80), nullable=False)
    item_id: Mapped[str | None] = mapped_column(ForeignKey("items.id", ondelete="CASCADE"), nullable=True)
    status: Mapped[JobStatus] = mapped_column(Enum(JobStatus), nullable=False, default=JobStatus.queued)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    run_after: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)


class BackupRun(Base):
    __tablename__ = "backup_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    path: Mapped[str | None] = mapped_column(Text, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
```

- [ ] **Step 4: Create `backend/app/db/session.py`**

```python
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

settings = get_settings()
engine = create_engine(settings.database_url, pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def get_db() -> Generator[Session, None, None]:
    with SessionLocal() as session:
        yield session
```

- [ ] **Step 5: Create `backend/app/db/init_db.py`**

```python
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Base, User
from app.db.session import engine

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def bootstrap_database(session: Session, admin_email: str, admin_password: str) -> None:
    existing = session.scalar(select(User).where(User.email == admin_email))
    if existing is not None:
        return
    session.add(
        User(
            email=admin_email,
            password_hash=pwd_context.hash(admin_password),
            is_admin=True,
        )
    )
    session.commit()


def create_tables() -> None:
    Base.metadata.create_all(engine)
```

- [ ] **Step 6: Update `backend/app/main.py` startup**

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.db.init_db import bootstrap_database, create_tables
from app.db.session import SessionLocal


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Personal Web Archive", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.on_event("startup")
    def startup() -> None:
        create_tables()
        with SessionLocal() as session:
            bootstrap_database(session, settings.admin_email, settings.admin_password)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
```

- [ ] **Step 7: Run bootstrap test**

Run:

```powershell
cd backend
pytest tests/test_db_bootstrap.py -v
```

Expected:

```text
tests/test_db_bootstrap.py::test_bootstrap_creates_admin_user PASSED
```

- [ ] **Step 8: Commit**

```powershell
git add backend/app backend/tests/test_db_bootstrap.py
git commit -m "feat: add database models and admin bootstrap"
```

---

### Task 3: Authentication API

**Files:**
- Create: `backend/app/core/security.py`
- Create: `backend/app/schemas/auth.py`
- Create: `backend/app/api/auth.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_auth_api.py`

- [ ] **Step 1: Write auth API tests**

```python
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.db.init_db import bootstrap_database
from app.db.models import Base
from app.db.session import get_db
from app.main import create_app


def make_client():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    TestingSession = sessionmaker(bind=engine, future=True)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        bootstrap_database(session, "admin@example.local", "secret-password")

    app = create_app()

    def override_db():
        with TestingSession() as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    return TestClient(app)


def test_login_sets_session_cookie():
    client = make_client()
    response = client.post("/api/auth/login", json={"email": "admin@example.local", "password": "secret-password"})
    assert response.status_code == 200
    assert response.json()["email"] == "admin@example.local"
    assert get_settings().session_cookie_name in response.cookies


def test_me_requires_session():
    response = make_client().get("/api/auth/me")
    assert response.status_code == 401
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
cd backend
pytest tests/test_auth_api.py -v
```

Expected: FAIL with `404 Not Found` for `/api/auth/login`.

- [ ] **Step 3: Create `backend/app/core/security.py`**

```python
import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import SessionToken, User

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, password_hash: str) -> bool:
    return pwd_context.verify(plain_password, password_hash)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_session(session: Session, user: User) -> str:
    settings = get_settings()
    raw_token = secrets.token_urlsafe(48)
    session.add(
        SessionToken(
            user_id=user.id,
            token_hash=hash_token(raw_token),
            expires_at=datetime.now(timezone.utc) + timedelta(days=settings.session_ttl_days),
        )
    )
    session.commit()
    return raw_token


def get_user_for_token(session: Session, raw_token: str | None) -> User | None:
    if not raw_token:
        return None
    token = session.scalar(select(SessionToken).where(SessionToken.token_hash == hash_token(raw_token)))
    if token is None or token.expires_at <= datetime.now(timezone.utc):
        return None
    return session.get(User, token.user_id)
```

- [ ] **Step 4: Create `backend/app/schemas/auth.py`**

```python
from pydantic import BaseModel, EmailStr


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: str
    email: EmailStr
    is_admin: bool
```

- [ ] **Step 5: Create `backend/app/api/auth.py`**

```python
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import create_session, get_user_for_token, verify_password
from app.db.models import User
from app.db.session import get_db
from app.schemas.auth import LoginRequest, UserResponse

router = APIRouter(prefix="/api/auth", tags=["auth"])


def current_user(request: Request, db: Session = Depends(get_db)) -> User:
    settings = get_settings()
    user = get_user_for_token(db, request.cookies.get(settings.session_cookie_name))
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return user


@router.post("/login", response_model=UserResponse)
def login(payload: LoginRequest, response: Response, db: Session = Depends(get_db)) -> User:
    settings = get_settings()
    user = db.scalar(select(User).where(User.email == payload.email))
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    token = create_session(db, user)
    response.set_cookie(
        settings.session_cookie_name,
        token,
        httponly=True,
        samesite="lax",
        secure=settings.app_env == "production",
        max_age=settings.session_ttl_days * 24 * 60 * 60,
    )
    return user


@router.get("/me", response_model=UserResponse)
def me(user: User = Depends(current_user)) -> User:
    return user


@router.post("/logout")
def logout(response: Response) -> dict[str, str]:
    response.delete_cookie(get_settings().session_cookie_name)
    return {"status": "ok"}
```

- [ ] **Step 6: Include auth router in `backend/app/main.py`**

```python
from app.api.auth import router as auth_router

# inside create_app(), before health route:
app.include_router(auth_router)
```

- [ ] **Step 7: Run auth tests**

Run:

```powershell
cd backend
pytest tests/test_auth_api.py -v
```

Expected:

```text
tests/test_auth_api.py::test_login_sets_session_cookie PASSED
tests/test_auth_api.py::test_me_requires_session PASSED
```

- [ ] **Step 8: Commit**

```powershell
git add backend/app backend/tests/test_auth_api.py
git commit -m "feat: add admin session authentication"
```

---

### Task 4: URL Normalization, Save API, And Job Queue

**Files:**
- Create: `backend/app/services/url_normalize.py`
- Create: `backend/app/services/jobs.py`
- Create: `backend/app/services/items.py`
- Create: `backend/app/schemas/items.py`
- Create: `backend/app/api/items.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_url_normalize.py`
- Create: `backend/tests/test_items_api.py`

- [ ] **Step 1: Write URL normalization tests**

```python
from app.services.url_normalize import normalize_url


def test_normalize_removes_tracking_params():
    result = normalize_url("https://example.com/post/?utm_source=x&id=123")
    assert result.normalized == "https://example.com/post?id=123"
    assert result.domain == "example.com"


def test_normalize_youtube_variants():
    first = normalize_url("https://youtu.be/abc123?si=tracking")
    second = normalize_url("https://www.youtube.com/watch?v=abc123&utm_source=x")
    assert first.normalized == "https://www.youtube.com/watch?v=abc123"
    assert second.normalized == "https://www.youtube.com/watch?v=abc123"
```

- [ ] **Step 2: Write save API tests**

```python
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.db.init_db import bootstrap_database
from app.db.models import Base, Item, Job
from app.db.session import get_db
from app.main import create_app


def make_client():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    TestingSession = sessionmaker(bind=engine, future=True)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        bootstrap_database(session, "admin@example.local", "secret-password")
    app = create_app()

    def override_db():
        with TestingSession() as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    client = TestClient(app)
    client.post("/api/auth/login", json={"email": "admin@example.local", "password": "secret-password"})
    return client, TestingSession


def test_save_url_creates_item_and_capture_job():
    client, TestingSession = make_client()
    response = client.post("/api/items/save", json={"url": "https://example.com/a?utm_source=x"})
    assert response.status_code == 201

    with TestingSession() as session:
        item = session.scalar(select(Item))
        job = session.scalar(select(Job))

    assert item.normalized_url == "https://example.com/a"
    assert job.job_type == "capture_item"
    assert job.item_id == item.id


def test_save_duplicate_returns_existing_item():
    client, TestingSession = make_client()
    first = client.post("/api/items/save", json={"url": "https://example.com/a"}).json()
    second_response = client.post("/api/items/save", json={"url": "https://example.com/a?utm_campaign=x"})
    assert second_response.status_code == 200
    assert second_response.json()["id"] == first["id"]
```

- [ ] **Step 3: Run tests to verify they fail**

Run:

```powershell
cd backend
pytest tests/test_url_normalize.py tests/test_items_api.py -v
```

Expected: FAIL with missing service modules.

- [ ] **Step 4: Create `backend/app/services/url_normalize.py`**

```python
from dataclasses import dataclass
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

TRACKING_PREFIXES = ("utm_",)
TRACKING_KEYS = {"fbclid", "gclid", "mc_cid", "mc_eid", "si"}


@dataclass(frozen=True)
class NormalizedUrl:
    original: str
    normalized: str
    domain: str


def normalize_url(url: str) -> NormalizedUrl:
    parsed = urlparse(url.strip())
    scheme = parsed.scheme or "https"
    netloc = parsed.netloc.lower()
    path = parsed.path or ""

    if netloc == "youtu.be":
        video_id = path.strip("/")
        normalized = f"https://www.youtube.com/watch?v={video_id}"
        return NormalizedUrl(original=url, normalized=normalized, domain="youtube.com")

    if netloc in {"youtube.com", "www.youtube.com", "m.youtube.com"} and path == "/watch":
        params = dict(parse_qsl(parsed.query, keep_blank_values=False))
        video_id = params.get("v")
        if video_id:
            return NormalizedUrl(
                original=url,
                normalized=f"https://www.youtube.com/watch?v={video_id}",
                domain="youtube.com",
            )

    filtered = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=False)
        if not key.startswith(TRACKING_PREFIXES) and key not in TRACKING_KEYS
    ]
    query = urlencode(filtered)
    path = path.rstrip("/") if path != "/" else ""
    normalized = urlunparse((scheme.lower(), netloc.removeprefix("www."), path, "", query, ""))
    return NormalizedUrl(original=url, normalized=normalized, domain=netloc.removeprefix("www."))
```

- [ ] **Step 5: Create `backend/app/services/jobs.py`**

```python
import json
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Job, JobStatus


def enqueue_job(db: Session, job_type: str, item_id: str | None = None, payload: dict | None = None) -> Job:
    job = Job(job_type=job_type, item_id=item_id, payload_json=json.dumps(payload or {}))
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def claim_next_job(db: Session) -> Job | None:
    job = db.scalar(
        select(Job)
        .where(Job.status == JobStatus.queued, Job.run_after <= datetime.now(timezone.utc))
        .order_by(Job.created_at)
        .limit(1)
    )
    if job is None:
        return None
    job.status = JobStatus.running
    job.attempts += 1
    job.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(job)
    return job


def complete_job(db: Session, job: Job) -> None:
    job.status = JobStatus.complete
    job.error = None
    job.updated_at = datetime.now(timezone.utc)
    db.commit()


def fail_job(db: Session, job: Job, error: str) -> None:
    job.status = JobStatus.failed
    job.error = error
    job.updated_at = datetime.now(timezone.utc)
    db.commit()
```

- [ ] **Step 6: Create `backend/app/schemas/items.py`**

```python
from datetime import datetime

from pydantic import BaseModel, HttpUrl


class SaveUrlRequest(BaseModel):
    url: HttpUrl


class SaveManyRequest(BaseModel):
    urls: list[HttpUrl]


class ItemResponse(BaseModel):
    id: str
    original_url: str
    normalized_url: str
    source_domain: str
    title: str | None
    status: str
    saved_at: datetime
    failure_reason: str | None


class ItemListResponse(BaseModel):
    items: list[ItemResponse]
```

- [ ] **Step 7: Create `backend/app/services/items.py`**

```python
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.db.models import Item, ItemStatus, JobStatus
from app.services.jobs import enqueue_job
from app.services.url_normalize import normalize_url


def save_url(db: Session, url: str) -> tuple[Item, bool]:
    normalized = normalize_url(url)
    existing = db.scalar(select(Item).where(Item.normalized_url == normalized.normalized))
    if existing is not None:
        return existing, False

    item = Item(
        original_url=normalized.original,
        normalized_url=normalized.normalized,
        source_domain=normalized.domain,
        status=ItemStatus.queued,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    enqueue_job(db, "capture_item", item_id=item.id)
    return item, True


def list_items(db: Session, query: str | None = None, status: str | None = None) -> list[Item]:
    stmt = select(Item).order_by(Item.saved_at.desc())
    if query:
        like = f"%{query}%"
        stmt = stmt.where(or_(Item.title.ilike(like), Item.normalized_url.ilike(like), Item.body_text.ilike(like)))
    if status:
        stmt = stmt.where(Item.status == status)
    return list(db.scalars(stmt).all())


def retry_item(db: Session, item_id: str) -> Item:
    item = db.get(Item, item_id)
    if item is None:
        raise ValueError("Item not found")
    item.status = ItemStatus.queued
    item.failure_reason = None
    db.commit()
    enqueue_job(db, "capture_item", item_id=item.id)
    db.refresh(item)
    return item
```

- [ ] **Step 8: Create `backend/app/api/items.py`**

```python
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from app.api.auth import current_user
from app.db.models import User
from app.db.session import get_db
from app.schemas.items import ItemListResponse, ItemResponse, SaveManyRequest, SaveUrlRequest
from app.services.items import list_items, retry_item, save_url

router = APIRouter(prefix="/api/items", tags=["items"])


@router.post("/save", response_model=ItemResponse)
def save_one(payload: SaveUrlRequest, response: Response, db: Session = Depends(get_db), _: User = Depends(current_user)):
    item, created = save_url(db, str(payload.url))
    response.status_code = 201 if created else 200
    return item


@router.post("/save-many", response_model=ItemListResponse)
def save_many(payload: SaveManyRequest, db: Session = Depends(get_db), _: User = Depends(current_user)):
    saved = [save_url(db, str(url))[0] for url in payload.urls]
    return {"items": saved}


@router.get("", response_model=ItemListResponse)
def index(
    q: str | None = Query(default=None),
    status: str | None = Query(default=None),
    db: Session = Depends(get_db),
    _: User = Depends(current_user),
):
    return {"items": list_items(db, query=q, status=status)}


@router.post("/{item_id}/retry", response_model=ItemResponse)
def retry(item_id: str, db: Session = Depends(get_db), _: User = Depends(current_user)):
    try:
        return retry_item(db, item_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
```

- [ ] **Step 9: Include items router**

In `backend/app/main.py`:

```python
from app.api.items import router as items_router

app.include_router(items_router)
```

- [ ] **Step 10: Run item tests**

Run:

```powershell
cd backend
pytest tests/test_url_normalize.py tests/test_items_api.py -v
```

Expected: all tests PASS.

- [ ] **Step 11: Commit**

```powershell
git add backend/app backend/tests/test_url_normalize.py backend/tests/test_items_api.py
git commit -m "feat: add url save pipeline"
```

---

### Task 5: Capture Worker And Preservation Artifacts

**Files:**
- Create: `backend/app/services/capture.py`
- Create: `backend/app/worker.py`
- Create: `backend/Dockerfile`
- Create: `backend/tests/test_capture_service.py`

- [ ] **Step 1: Write capture service test**

```python
from pathlib import Path
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.db.models import Artifact, ArtifactType, Base, Item, ItemStatus
from app.services.capture import store_capture_result


def test_store_capture_result_writes_artifacts(tmp_path: Path):
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        item = Item(original_url="https://example.com", normalized_url="https://example.com", source_domain="example.com")
        session.add(item)
        session.commit()
        session.refresh(item)

        store_capture_result(
            session,
            item,
            data_dir=tmp_path,
            title="Example",
            description="A page",
            body_text="Readable body",
            html="<html><body>Readable body</body></html>",
            screenshot_bytes=b"fake-png",
        )

        artifacts = session.scalars(select(Artifact).where(Artifact.item_id == item.id)).all()

    assert item.status == ItemStatus.preserved
    assert item.title == "Example"
    assert item.body_text == "Readable body"
    assert {artifact.artifact_type for artifact in artifacts} == {ArtifactType.html, ArtifactType.screenshot}
    assert all((tmp_path / artifact.path).exists() for artifact in artifacts)
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
cd backend
pytest tests/test_capture_service.py -v
```

Expected: FAIL with missing `app.services.capture`.

- [ ] **Step 3: Create `backend/app/services/capture.py`**

```python
from pathlib import Path

from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
from readability import Document
from sqlalchemy.orm import Session

from app.db.models import Artifact, ArtifactType, Item, ItemStatus


def item_artifact_dir(data_dir: Path, item: Item) -> Path:
    path = data_dir / "items" / item.id
    path.mkdir(parents=True, exist_ok=True)
    return path


def store_capture_result(
    db: Session,
    item: Item,
    data_dir: Path,
    title: str | None,
    description: str | None,
    body_text: str | None,
    html: str | None,
    screenshot_bytes: bytes | None,
) -> None:
    artifact_dir = item_artifact_dir(data_dir, item)
    item.title = title
    item.description = description
    item.body_text = body_text
    item.status = ItemStatus.preserved
    item.failure_reason = None

    if html:
        html_path = artifact_dir / "snapshot.html"
        html_path.write_text(html, encoding="utf-8")
        db.add(Artifact(item_id=item.id, artifact_type=ArtifactType.html, path=str(html_path.relative_to(data_dir)), mime_type="text/html"))

    if screenshot_bytes:
        screenshot_path = artifact_dir / "screenshot.png"
        screenshot_path.write_bytes(screenshot_bytes)
        db.add(
            Artifact(
                item_id=item.id,
                artifact_type=ArtifactType.screenshot,
                path=str(screenshot_path.relative_to(data_dir)),
                mime_type="image/png",
            )
        )
    db.commit()


def extract_text(html: str) -> tuple[str | None, str | None, str]:
    document = Document(html)
    title = document.short_title()
    summary_html = document.summary()
    soup = BeautifulSoup(summary_html, "html.parser")
    body_text = soup.get_text("\n", strip=True)
    description_node = BeautifulSoup(html, "html.parser").find("meta", attrs={"name": "description"})
    description = description_node.get("content") if description_node else None
    return title, description, body_text


async def capture_url(url: str, timeout_ms: int) -> tuple[str | None, str | None, str | None, str | None, bytes | None]:
    screenshot_bytes: bytes | None = None
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch()
        page = await browser.new_page()
        await page.goto(url, wait_until="networkidle", timeout=timeout_ms)
        html = await page.content()
        screenshot_bytes = await page.screenshot(full_page=True)
        await browser.close()
    title, description, body_text = extract_text(html)
    return title, description, body_text, html, screenshot_bytes
```

- [ ] **Step 4: Create `backend/app/worker.py`**

```python
import asyncio
from pathlib import Path
from time import sleep

from app.core.config import get_settings
from app.db.models import Item, ItemStatus
from app.db.session import SessionLocal
from app.services.capture import capture_url, store_capture_result
from app.services.jobs import claim_next_job, complete_job, fail_job


async def process_capture_item(item_id: str) -> None:
    settings = get_settings()
    with SessionLocal() as db:
        item = db.get(Item, item_id)
        if item is None:
            return
        item.status = ItemStatus.processing
        db.commit()
        try:
            title, description, body_text, html, screenshot = await capture_url(item.normalized_url, settings.capture_timeout_ms)
            store_capture_result(db, item, Path(settings.data_dir), title, description, body_text, html, screenshot)
        except Exception as exc:
            item.status = ItemStatus.failed
            item.failure_reason = str(exc)
            db.commit()
            raise


async def run_once() -> bool:
    with SessionLocal() as db:
        job = claim_next_job(db)
        if job is None:
            return False
        try:
            if job.job_type == "capture_item" and job.item_id:
                await process_capture_item(job.item_id)
            complete_job(db, job)
        except Exception as exc:
            fail_job(db, job, str(exc))
    return True


def main() -> None:
    while True:
        did_work = asyncio.run(run_once())
        if not did_work:
            sleep(2)


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Create `backend/Dockerfile`**

```dockerfile
FROM python:3.12-slim

WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libxml2-dev \
    libxslt1-dev \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml /app/pyproject.toml
RUN pip install --no-cache-dir -e ".[dev]"
RUN python -m playwright install --with-deps chromium
COPY app /app/app

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 6: Run capture test**

Run:

```powershell
cd backend
pytest tests/test_capture_service.py -v
```

Expected: PASS.

- [ ] **Step 7: Commit**

```powershell
git add backend/app/services/capture.py backend/app/worker.py backend/Dockerfile backend/tests/test_capture_service.py
git commit -m "feat: add capture worker"
```

---

### Task 6: AI Topic Tree And Recommendation Feed MVP

**Files:**
- Create: `backend/app/services/ai.py`
- Create: `backend/app/api/topics.py`
- Create: `backend/app/api/recommendations.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_ai_recommendations.py`

- [ ] **Step 1: Write AI recommendation tests**

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.models import Base, Item, ItemStatus
from app.services.ai import build_recommendation_reason, suggest_topic_name


def test_suggest_topic_name_uses_content_keywords():
    item = Item(
        original_url="https://example.com",
        normalized_url="https://example.com",
        source_domain="example.com",
        title="Local LLM on Ubuntu",
        body_text="Run local AI models on Ubuntu with GPU support.",
        status=ItemStatus.preserved,
    )
    assert suggest_topic_name(item) == "AI"


def test_recommendation_reason_mentions_recent_saved_item():
    item = Item(
        original_url="https://example.com",
        normalized_url="https://example.com",
        source_domain="example.com",
        title="Example",
        status=ItemStatus.preserved,
    )
    assert build_recommendation_reason(item) == "Recently saved and preserved."
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
cd backend
pytest tests/test_ai_recommendations.py -v
```

Expected: FAIL with missing `app.services.ai`.

- [ ] **Step 3: Create `backend/app/services/ai.py`**

```python
from app.db.models import Item


def suggest_topic_name(item: Item) -> str:
    text = " ".join(filter(None, [item.title, item.body_text, item.source_domain])).lower()
    if any(keyword in text for keyword in ["ai", "llm", "model", "agent", "prompt"]):
        return "AI"
    if any(keyword in text for keyword in ["ubuntu", "windows", "docker", "python", "react"]):
        return "Development"
    if "youtube" in text:
        return "YouTube"
    return "Unsorted"


def build_summary(item: Item) -> str | None:
    if item.body_text:
        return item.body_text[:280]
    return item.description


def build_recommendation_reason(item: Item) -> str:
    if item.status.value == "failed":
        return "Needs retry before it can be preserved."
    return "Recently saved and preserved."
```

- [ ] **Step 4: Create topics API**

`backend/app/api/topics.py`:

```python
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.auth import current_user
from app.db.models import Item, User
from app.db.session import get_db
from app.services.ai import suggest_topic_name

router = APIRouter(prefix="/api/topics", tags=["topics"])


@router.get("/tree")
def topic_tree(db: Session = Depends(get_db), _: User = Depends(current_user)) -> dict:
    counts: dict[str, int] = {}
    for item in db.scalars(select(Item)).all():
        topic = suggest_topic_name(item)
        counts[topic] = counts.get(topic, 0) + 1
    return {"topics": [{"id": name.lower(), "name": name, "count": count, "children": []} for name, count in sorted(counts.items())]}
```

`backend/app/api/recommendations.py`:

```python
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.auth import current_user
from app.db.models import Item, User
from app.db.session import get_db
from app.services.ai import build_recommendation_reason, build_summary, suggest_topic_name

router = APIRouter(prefix="/api/recommendations", tags=["recommendations"])


@router.get("")
def recommendations(db: Session = Depends(get_db), _: User = Depends(current_user)) -> dict:
    items = db.scalars(select(Item).order_by(Item.saved_at.desc()).limit(20)).all()
    return {
        "items": [
            {
                "id": item.id,
                "title": item.title or item.normalized_url,
                "source_domain": item.source_domain,
                "summary": build_summary(item),
                "reason": build_recommendation_reason(item),
                "topic": suggest_topic_name(item),
                "status": item.status.value,
            }
            for item in items
        ]
    }
```

- [ ] **Step 5: Include routers in `main.py`**

```python
from app.api.recommendations import router as recommendations_router
from app.api.topics import router as topics_router

app.include_router(topics_router)
app.include_router(recommendations_router)
```

- [ ] **Step 6: Run tests**

Run:

```powershell
cd backend
pytest tests/test_ai_recommendations.py -v
```

Expected: PASS.

- [ ] **Step 7: Commit**

```powershell
git add backend/app backend/tests/test_ai_recommendations.py
git commit -m "feat: add topic and recommendation endpoints"
```

---

### Task 7: Frontend MVP Shell

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/index.html`
- Create: `frontend/src/main.tsx`
- Create: `frontend/src/App.tsx`
- Create: `frontend/src/api/client.ts`
- Create: `frontend/src/features/auth/Login.tsx`
- Create: `frontend/src/features/items/SaveUrlDialog.tsx`
- Create: `frontend/src/features/items/ItemList.tsx`
- Create: `frontend/src/features/topics/TopicTree.tsx`
- Create: `frontend/src/features/recommendations/RecommendationFeed.tsx`
- Create: `frontend/src/styles.css`
- Create: `frontend/Dockerfile`

- [ ] **Step 1: Create `frontend/package.json`**

```json
{
  "name": "personal-web-archive-frontend",
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc && vite build",
    "test": "vitest run"
  },
  "dependencies": {
    "@vitejs/plugin-react": "^4.3.1",
    "vite": "^5.4.0",
    "typescript": "^5.5.4",
    "react": "^18.3.1",
    "react-dom": "^18.3.1",
    "lucide-react": "^0.468.0"
  },
  "devDependencies": {
    "vitest": "^2.0.5",
    "@types/react": "^18.3.3",
    "@types/react-dom": "^18.3.0"
  }
}
```

- [ ] **Step 2: Create frontend source files**

`frontend/src/api/client.ts`:

```ts
const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    credentials: "include",
    headers: { "Content-Type": "application/json", ...(options.headers ?? {}) },
    ...options,
  });
  if (!response.ok) throw new Error(await response.text());
  return response.json() as Promise<T>;
}
```

`frontend/src/App.tsx`:

```tsx
import { useEffect, useState } from "react";
import { Login } from "./features/auth/Login";
import { SaveUrlDialog } from "./features/items/SaveUrlDialog";
import { ItemList } from "./features/items/ItemList";
import { TopicTree } from "./features/topics/TopicTree";
import { RecommendationFeed } from "./features/recommendations/RecommendationFeed";
import { api } from "./api/client";

type User = { id: string; email: string };

export function App() {
  const [user, setUser] = useState<User | null>(null);
  const [selectedTopic, setSelectedTopic] = useState<string | null>(null);

  useEffect(() => {
    api<User>("/api/auth/me").then(setUser).catch(() => setUser(null));
  }, []);

  if (!user) return <Login onLogin={setUser} />;

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <h1>Archive</h1>
        <TopicTree onSelect={setSelectedTopic} />
      </aside>
      <main className="main">
        <header className="toolbar">
          <input className="search" placeholder="Search title, URL, body, source, status" />
          <SaveUrlDialog />
        </header>
        {selectedTopic ? <ItemList topic={selectedTopic} /> : <RecommendationFeed />}
      </main>
    </div>
  );
}
```

`frontend/src/features/auth/Login.tsx`:

```tsx
import { FormEvent, useState } from "react";
import { api } from "../../api/client";

export function Login({ onLogin }: { onLogin: (user: { id: string; email: string }) => void }) {
  const [email, setEmail] = useState("admin@example.local");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError("");
    try {
      onLogin(await api("/api/auth/login", { method: "POST", body: JSON.stringify({ email, password }) }));
    } catch {
      setError("Login failed");
    }
  }

  return (
    <main className="login-screen">
      <form onSubmit={submit} className="login-form">
        <h1>Personal Archive</h1>
        <input value={email} onChange={(event) => setEmail(event.target.value)} />
        <input type="password" value={password} onChange={(event) => setPassword(event.target.value)} />
        <button>Log in</button>
        {error && <p className="error">{error}</p>}
      </form>
    </main>
  );
}
```

- [ ] **Step 3: Create item UI files**

`frontend/src/features/items/SaveUrlDialog.tsx`:

```tsx
import { useState } from "react";
import { Plus } from "lucide-react";
import { api } from "../../api/client";

export function SaveUrlDialog() {
  const [url, setUrl] = useState("");
  const [message, setMessage] = useState("");

  async function save() {
    const urls = url.split(/\s+/).filter(Boolean);
    if (urls.length === 1) {
      await api("/api/items/save", { method: "POST", body: JSON.stringify({ url: urls[0] }) });
    } else {
      await api("/api/items/save-many", { method: "POST", body: JSON.stringify({ urls }) });
    }
    setUrl("");
    setMessage("Saved to queue");
  }

  return (
    <div className="save-box">
      <textarea value={url} onChange={(event) => setUrl(event.target.value)} placeholder="Paste one or many URLs" />
      <button onClick={save}><Plus size={16} /> Save URL</button>
      {message && <span>{message}</span>}
    </div>
  );
}
```

`frontend/src/features/items/ItemList.tsx`:

```tsx
import { useEffect, useState } from "react";
import { api } from "../../api/client";

type Item = {
  id: string;
  original_url: string;
  normalized_url: string;
  source_domain: string;
  title: string | null;
  status: string;
  saved_at: string;
  failure_reason: string | null;
};

export function ItemList({ topic }: { topic: string }) {
  const [items, setItems] = useState<Item[]>([]);

  useEffect(() => {
    api<{ items: Item[] }>("/api/items").then((result) => setItems(result.items));
  }, [topic]);

  return (
    <section>
      <h2>{topic}</h2>
      {items.map((item) => (
        <article className="card" key={item.id}>
          <h3>{item.title ?? item.normalized_url}</h3>
          <p className="muted">{item.source_domain} · {item.status}</p>
          {item.failure_reason && <p className="error">{item.failure_reason}</p>}
          <a href={item.normalized_url} target="_blank" rel="noreferrer">Open original</a>
        </article>
      ))}
    </section>
  );
}
```

- [ ] **Step 4: Create topic and recommendation UI files**

`frontend/src/features/topics/TopicTree.tsx`:

```tsx
import { useEffect, useState } from "react";
import { api } from "../../api/client";

type Topic = { id: string; name: string; count: number; children: Topic[] };

export function TopicTree({ onSelect }: { onSelect: (topic: string) => void }) {
  const [topics, setTopics] = useState<Topic[]>([]);

  useEffect(() => {
    api<{ topics: Topic[] }>("/api/topics/tree").then((result) => setTopics(result.topics));
  }, []);

  return (
    <nav className="topic-tree">
      {topics.map((topic) => (
        <button key={topic.id} onClick={() => onSelect(topic.name)} className="topic-button">
          <span>{topic.name}</span>
          <span>{topic.count}</span>
        </button>
      ))}
    </nav>
  );
}
```

`frontend/src/features/recommendations/RecommendationFeed.tsx`:

```tsx
import { useEffect, useState } from "react";
import { api } from "../../api/client";

type Recommendation = {
  id: string;
  title: string;
  source_domain: string;
  summary: string | null;
  reason: string;
  topic: string;
  status: string;
};

export function RecommendationFeed() {
  const [items, setItems] = useState<Recommendation[]>([]);

  useEffect(() => {
    api<{ items: Recommendation[] }>("/api/recommendations").then((result) => setItems(result.items));
  }, []);

  return (
    <section>
      <h2>Recommended</h2>
      {items.map((item) => (
        <article className="card" key={item.id}>
          <h3>{item.title}</h3>
          <p className="muted">{item.source_domain} · {item.topic} · {item.status}</p>
          {item.summary && <p>{item.summary}</p>}
          <p className="muted">{item.reason}</p>
        </article>
      ))}
    </section>
  );
}
```

- [ ] **Step 5: Create `frontend/src/styles.css`**

```css
body { margin: 0; font-family: Inter, system-ui, sans-serif; background: #f6f8fa; color: #202124; }
button { cursor: pointer; }
.app-shell { display: grid; grid-template-columns: 280px 1fr; min-height: 100vh; }
.sidebar { border-right: 1px solid #d8dee4; background: #fff; padding: 20px; }
.main { padding: 20px; }
.toolbar { display: flex; gap: 12px; align-items: flex-start; margin-bottom: 20px; }
.search { flex: 1; padding: 12px; border: 1px solid #d8dee4; border-radius: 6px; }
.save-box { display: grid; gap: 8px; width: 320px; }
.save-box textarea { min-height: 72px; padding: 10px; border: 1px solid #d8dee4; border-radius: 6px; }
.save-box button { display: inline-flex; gap: 8px; align-items: center; justify-content: center; padding: 10px 12px; border: 0; border-radius: 6px; background: #0f766e; color: white; }
.topic-tree { display: grid; gap: 8px; }
.topic-button { display: flex; justify-content: space-between; width: 100%; border: 1px solid #d8dee4; border-radius: 6px; background: #fff; padding: 10px; color: #202124; }
.card { background: white; border: 1px solid #d8dee4; border-radius: 8px; padding: 16px; margin-bottom: 12px; }
.muted { color: #5f6368; }
.login-screen { min-height: 100vh; display: grid; place-items: center; }
.login-form { display: grid; gap: 12px; width: 320px; background: white; border: 1px solid #d8dee4; border-radius: 8px; padding: 24px; }
.login-form input { padding: 10px; border: 1px solid #d8dee4; border-radius: 6px; }
.error { color: #b42318; }
```

- [ ] **Step 6: Create `frontend/src/main.tsx`, `index.html`, and Dockerfile**

```tsx
import React from "react";
import ReactDOM from "react-dom/client";
import { App } from "./App";
import "./styles.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
```

```html
<div id="root"></div>
<script type="module" src="/src/main.tsx"></script>
```

```dockerfile
FROM node:22-slim
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm install
COPY . .
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
```

- [ ] **Step 7: Run frontend build**

Run:

```powershell
cd frontend
npm install
npm run build
```

Expected: build exits with code 0 and creates `frontend/dist`.

- [ ] **Step 8: Commit**

```powershell
git add frontend
git commit -m "feat: add archive web UI"
```

---

### Task 8: Browser Extension Current Page Save

**Files:**
- Create: `extension/manifest.json`
- Create: `extension/src/popup.html`
- Create: `extension/src/popup.ts`
- Create: `extension/src/background.ts`
- Create: `extension/package.json`

- [ ] **Step 1: Create extension manifest**

```json
{
  "manifest_version": 3,
  "name": "Personal Archive Saver",
  "version": "0.1.0",
  "description": "Save the current page to the personal web archive.",
  "permissions": ["activeTab", "storage"],
  "host_permissions": ["http://localhost:8000/*", "http://127.0.0.1:8000/*"],
  "action": {
    "default_popup": "popup.html",
    "default_title": "Save to Archive"
  },
  "background": {
    "service_worker": "background.js"
  }
}
```

- [ ] **Step 2: Create popup implementation**

`extension/src/popup.html`:

```html
<main>
  <h1>Save to Archive</h1>
  <button id="save">Save current page</button>
  <p id="status"></p>
</main>
<script type="module" src="./popup.ts"></script>
```

`extension/src/popup.ts`:

```ts
const status = document.querySelector<HTMLParagraphElement>("#status")!;
const button = document.querySelector<HTMLButtonElement>("#save")!;

button.addEventListener("click", async () => {
  status.textContent = "Saving...";
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab.url) {
    status.textContent = "No URL found.";
    return;
  }
  const response = await fetch("http://localhost:8000/api/items/save", {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url: tab.url }),
  });
  status.textContent = response.ok ? "Saved to queue." : "Save failed. Open the archive app and log in.";
});
```

- [ ] **Step 3: Create build package**

```json
{
  "name": "personal-archive-extension",
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "build": "vite build"
  },
  "devDependencies": {
    "@types/chrome": "^0.0.268",
    "typescript": "^5.5.4",
    "vite": "^5.4.0"
  }
}
```

- [ ] **Step 4: Build extension**

Run:

```powershell
cd extension
npm install
npm run build
```

Expected: `extension/dist` contains bundled extension files.

- [ ] **Step 5: Commit**

```powershell
git add extension
git commit -m "feat: add browser save extension"
```

---

### Task 9: Local Backup Job

**Files:**
- Create: `backend/app/services/backup.py`
- Create: `backend/app/api/backups.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_backup_service.py`

- [ ] **Step 1: Write backup manifest test**

```python
import json
from pathlib import Path

from app.services.backup import create_backup_manifest, create_database_snapshot


def test_create_backup_manifest(tmp_path: Path):
    data_dir = tmp_path / "data"
    backup_dir = tmp_path / "backups"
    data_dir.mkdir()
    (data_dir / "sample.txt").write_text("saved", encoding="utf-8")

    database_path = create_database_snapshot(backup_dir=backup_dir, rows={"items": [{"id": "1"}]})
    manifest_path = create_backup_manifest(data_dir=data_dir, backup_dir=backup_dir, database_dump_name=database_path.name)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert manifest["database_dump"] == "database.json"
    assert manifest["artifact_file_count"] == 1
    assert json.loads(database_path.read_text(encoding="utf-8"))["items"] == [{"id": "1"}]
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
cd backend
pytest tests/test_backup_service.py -v
```

Expected: FAIL with missing `app.services.backup`.

- [ ] **Step 3: Create `backend/app/services/backup.py`**

```python
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path


def create_backup_manifest(data_dir: Path, backup_dir: Path, database_dump_name: str) -> Path:
    backup_dir.mkdir(parents=True, exist_ok=True)
    artifact_count = sum(1 for path in data_dir.rglob("*") if path.is_file()) if data_dir.exists() else 0
    manifest = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "database_dump": database_dump_name,
        "artifact_file_count": artifact_count,
    }
    manifest_path = backup_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest_path


def create_database_snapshot(backup_dir: Path, rows: dict[str, list[dict]]) -> Path:
    backup_dir.mkdir(parents=True, exist_ok=True)
    path = backup_dir / "database.json"
    path.write_text(json.dumps(rows, indent=2, default=str), encoding="utf-8")
    return path


def copy_artifacts(data_dir: Path, backup_dir: Path) -> Path:
    target = backup_dir / "data"
    if target.exists():
        shutil.rmtree(target)
    if data_dir.exists():
        shutil.copytree(data_dir, target)
    else:
        target.mkdir(parents=True)
    return target
```

- [ ] **Step 4: Create backup API**

```python
from pathlib import Path

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.auth import current_user
from app.core.config import get_settings
from app.db.models import Item, User
from app.db.session import get_db
from app.services.backup import copy_artifacts, create_backup_manifest, create_database_snapshot

router = APIRouter(prefix="/api/backups", tags=["backups"])


@router.post("/run")
def run_backup(db: Session = Depends(get_db), _: User = Depends(current_user)) -> dict[str, str]:
    settings = get_settings()
    backup_root = Path(settings.backup_dir) / "manual"
    copy_artifacts(Path(settings.data_dir), backup_root)
    items = db.scalars(select(Item)).all()
    database = create_database_snapshot(
        backup_root,
        {
            "items": [
                {
                    "id": item.id,
                    "original_url": item.original_url,
                    "normalized_url": item.normalized_url,
                    "source_domain": item.source_domain,
                    "title": item.title,
                    "status": item.status.value,
                    "saved_at": item.saved_at.isoformat(),
                }
                for item in items
            ]
        },
    )
    manifest = create_backup_manifest(Path(settings.data_dir), backup_root, database.name)
    return {"status": "complete", "manifest": str(manifest)}
```

Include router in `main.py`:

```python
from app.api.backups import router as backups_router
app.include_router(backups_router)
```

- [ ] **Step 5: Run backup test**

Run:

```powershell
cd backend
pytest tests/test_backup_service.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add backend/app backend/tests/test_backup_service.py
git commit -m "feat: add local backup manifest"
```

---

### Task 10: End-To-End Verification

**Files:**
- Modify only if verification reveals defects in files created by prior tasks.

- [ ] **Step 1: Create local `.env`**

Copy `.env.example` to `.env` and set:

```env
APP_SECRET_KEY=local-development-secret-key
ADMIN_EMAIL=admin@example.local
ADMIN_PASSWORD=secret-password
```

- [ ] **Step 2: Start services**

Run:

```powershell
docker compose up --build
```

Expected:

```text
backend  | Uvicorn running on http://0.0.0.0:8000
frontend | Local: http://localhost:5173/
worker   | running without repeated tracebacks
db       | database system is ready to accept connections
```

- [ ] **Step 3: Verify backend health**

Run:

```powershell
Invoke-WebRequest -Uri http://localhost:8000/health -UseBasicParsing
```

Expected status code: `200`.

- [ ] **Step 4: Verify UI manually**

Open `http://localhost:5173`.

Expected:

- Login form appears.
- Login succeeds with `admin@example.local` and `secret-password`.
- Main layout shows left topic sidebar, search, URL save box, and recommendation area.

- [ ] **Step 5: Save a URL**

In the UI, save:

```text
https://example.com
```

Expected:

- UI shows "Saved to queue".
- Item appears in the item list or recommendation feed after refresh.
- Backend DB has one item with normalized URL `https://example.com`.
- Worker creates `data/items/<item-id>/snapshot.html`.

- [ ] **Step 6: Run all automated tests**

Run:

```powershell
cd backend
pytest -v
cd ..\frontend
npm run build
cd ..\extension
npm run build
```

Expected: all commands exit with code 0.

- [ ] **Step 7: Commit verification fixes**

If defects were fixed:

```powershell
git add .
git commit -m "fix: stabilize archive mvp verification"
```

If no defects were found:

```powershell
git status --short
```

Expected: clean working tree.

---

## Self-Review

Spec coverage:

- Capture links quickly: Tasks 4, 7, and 8.
- Preserve content: Task 5.
- Search and browse: Tasks 4, 6, and 7.
- AI classification/recommendation MVP: Task 6.
- Tailscale-compatible single admin login: Task 3.
- Local backup: Task 9.
- Docker Compose deployment: Tasks 1 and 10.
- OpenClaw boundary: covered by keeping all write operations behind authenticated HTTP APIs that can later be exposed as limited OpenClaw commands.

Known deliberate MVP limits:

- Topic tree and recommendation feed use deterministic AI stubs so the UI and data flow are testable before external or local model configuration.
