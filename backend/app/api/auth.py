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
