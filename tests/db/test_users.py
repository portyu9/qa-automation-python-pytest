"""
Database and repository tests.

These tests exercise the SQLAlchemy helpers and the repository abstraction.
"""


import pytest

from sqlalchemy.orm import Session

from src.db import get_engine, init_db, get_all_users, User
from src.repositories.user_repository import UserRepository


@pytest.mark.db
def test_get_all_users(db_session: Session) -> None:
    """Verify that ``get_all_users`` returns the seeded users in order."""
    users = get_all_users(db_session)
    assert len(users) == 3
    assert users[0].name == "Alice"
    assert users[1].email == "bob@example.com"


@pytest.mark.db
def test_user_repository_find_by_id() -> None:
    """Verify that the repository can retrieve users by id and close sessions."""
    repo = UserRepository.initialize("sqlite:///:memory:")
    try:
        user = repo.find_by_id(2)
        assert user is not None
        assert user.name == "Bob"
    finally:
        repo.close()
