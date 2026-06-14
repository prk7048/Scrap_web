from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.auth import router as auth_router
from app.api.backups import router as backups_router
from app.api.items import router as items_router
from app.api.recommendations import router as recommendations_router
from app.api.topics import router as topics_router
from app.core.config import get_settings
from app.db.init_db import bootstrap_database, create_tables
from app.db.session import SessionLocal


def create_app() -> FastAPI:
    settings = get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        create_tables()
        with SessionLocal() as session:
            bootstrap_database(
                session,
                admin_email=settings.admin_email,
                admin_password=settings.admin_password,
            )
        yield

    app = FastAPI(title="Personal Web Archive", version="0.1.0", lifespan=lifespan)
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

    app.include_router(auth_router)
    app.include_router(items_router)
    app.include_router(topics_router)
    app.include_router(recommendations_router)
    app.include_router(backups_router)

    return app


app = create_app()
