from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import (
    create_extension_token,
    create_session,
    get_user_for_extension_token,
    get_user_for_token,
    hash_token,
    has_active_extension_token,
    revoke_extension_tokens,
    verify_password,
)
from app.db.models import SessionToken, User
from app.db.session import get_db
from app.schemas.auth import ExtensionTokenCreatedResponse, ExtensionTokenStatusResponse, LoginRequest, UserResponse

router = APIRouter(prefix="/api/auth", tags=["auth"])


def current_user(request: Request, db: Session = Depends(get_db)) -> User:
    settings = get_settings()
    user = get_user_for_token(db, request.cookies.get(settings.session_cookie_name))
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return user


def current_user_or_extension_save_user(request: Request, db: Session = Depends(get_db)) -> User:
    settings = get_settings()
    user = get_user_for_token(db, request.cookies.get(settings.session_cookie_name))
    if user is not None:
        return user

    authorization = request.headers.get("Authorization", "")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() == "bearer":
        user = get_user_for_extension_token(db, token)
        if user is not None:
            return user

    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")


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


@router.get("/extension-token", response_model=ExtensionTokenStatusResponse)
def extension_token_status(
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> ExtensionTokenStatusResponse:
    return ExtensionTokenStatusResponse(active=has_active_extension_token(db, user))


@router.post("/extension-token", response_model=ExtensionTokenCreatedResponse, status_code=status.HTTP_201_CREATED)
def create_or_rotate_extension_token(
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> ExtensionTokenCreatedResponse:
    token = create_extension_token(db, user)
    return ExtensionTokenCreatedResponse(active=True, token=token)


@router.delete("/extension-token")
def revoke_extension_token(user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict[str, str]:
    revoke_extension_tokens(db, user)
    return {"status": "revoked"}


@router.post("/logout")
def logout(request: Request, response: Response, db: Session = Depends(get_db)) -> dict[str, str]:
    settings = get_settings()
    raw_token = request.cookies.get(settings.session_cookie_name)
    if raw_token:
        token = db.scalar(select(SessionToken).where(SessionToken.token_hash == hash_token(raw_token)))
        if token is not None:
            db.delete(token)
    db.commit()
    response.delete_cookie(settings.session_cookie_name)
    return {"status": "ok"}
