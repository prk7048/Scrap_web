from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Base, User

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
    from app.db.session import engine

    Base.metadata.create_all(engine)
