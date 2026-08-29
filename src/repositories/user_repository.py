"""Repository boundary for deterministic User persistence operations."""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from ..db import User, init_db


class UserRepository:
    """Own a SQLAlchemy session and the engine that backs that session."""

    def __init__(self, session: Session, engine: Engine) -> None:
        self._session = session
        self._engine = engine

    @classmethod
    def initialize(cls, db_url: str = "sqlite:///qa_users.db") -> "UserRepository":
        """Create, seed, and own the database resources required by the repository."""
        engine = create_engine(db_url, echo=False, future=True)
        try:
            init_db(engine)
            session = Session(bind=engine)
        except Exception:
            engine.dispose()
            raise
        return cls(session, engine)

    def find_all(self) -> list[User]:
        """Retrieve all users ordered by primary key."""
        return self._session.query(User).order_by(User.id).all()

    def find_by_id(self, user_id: int) -> User | None:
        """Retrieve one user by primary key, or ``None`` when it does not exist."""
        return self._session.query(User).filter(User.id == user_id).one_or_none()

    def close(self) -> None:
        """Release both ORM and pooled DBAPI resources deterministically."""
        self._session.close()
        self._engine.dispose()

    def __enter__(self) -> "UserRepository":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
