"""SQLAlchemy persistence model and deterministic in-memory test database setup."""

from __future__ import annotations

from sqlalchemy import Column, Integer, String, create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker


Base = declarative_base()


class User(Base):
    """Persistence model used by repository and transaction-focused tests."""

    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    name = Column(String)
    email = Column(String)


def get_engine(echo: bool = False) -> Engine:
    """Create an isolated in-memory SQLite engine for a single test session."""
    return create_engine("sqlite:///:memory:", echo=echo, future=True)


def init_db(engine: Engine) -> None:
    """Create the schema and seed deterministic baseline records."""
    Base.metadata.create_all(engine)

    session_factory = sessionmaker(bind=engine, future=True)
    with session_factory() as session:
        session.add_all(
            [
                User(name="Alice", email="alice@example.com"),
                User(name="Bob", email="bob@example.com"),
                User(name="Charlie", email="charlie@example.com"),
            ]
        )
        session.commit()


def get_all_users(session: Session) -> list[User]:
    """Return users in deterministic primary-key order."""
    return session.query(User).order_by(User.id).all()
