import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import ExtensionToken, SessionToken, User

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
EXTENSION_TOKEN_SCOPE = "items:save"
EXTENSION_TOKEN_PREFIX = "pwa_ext_"


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


def create_extension_token(session: Session, user: User) -> str:
    revoke_extension_tokens(session, user)
    raw_token = f"{EXTENSION_TOKEN_PREFIX}{secrets.token_urlsafe(48)}"
    session.add(
        ExtensionToken(
            user_id=user.id,
            token_hash=hash_token(raw_token),
            scope=EXTENSION_TOKEN_SCOPE,
        )
    )
    session.commit()
    return raw_token


def revoke_extension_tokens(session: Session, user: User) -> None:
    now = datetime.now(timezone.utc)
    tokens = session.scalars(
        select(ExtensionToken).where(
            ExtensionToken.user_id == user.id,
            ExtensionToken.scope == EXTENSION_TOKEN_SCOPE,
            ExtensionToken.revoked_at.is_(None),
        )
    ).all()
    for token in tokens:
        token.revoked_at = now
    session.commit()


def has_active_extension_token(session: Session, user: User) -> bool:
    return (
        session.scalar(
            select(ExtensionToken).where(
                ExtensionToken.user_id == user.id,
                ExtensionToken.scope == EXTENSION_TOKEN_SCOPE,
                ExtensionToken.revoked_at.is_(None),
            )
        )
        is not None
    )


def get_user_for_extension_token(session: Session, raw_token: str | None) -> User | None:
    if not raw_token or not raw_token.startswith(EXTENSION_TOKEN_PREFIX):
        return None
    token = session.scalar(
        select(ExtensionToken).where(
            ExtensionToken.token_hash == hash_token(raw_token),
            ExtensionToken.scope == EXTENSION_TOKEN_SCOPE,
            ExtensionToken.revoked_at.is_(None),
        )
    )
    if token is None:
        return None
    return session.get(User, token.user_id)


def get_user_for_token(session: Session, raw_token: str | None) -> User | None:
    if not raw_token:
        return None
    token = session.scalar(select(SessionToken).where(SessionToken.token_hash == hash_token(raw_token)))
    if token is None:
        return None
    expires_at = token.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at <= datetime.now(timezone.utc):
        return None
    return session.get(User, token.user_id)
