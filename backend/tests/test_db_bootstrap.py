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
