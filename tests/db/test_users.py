"""Database and repository behavior tests."""

import pytest
from sqlalchemy.orm import Session

from src.db import get_all_users
from src.repositories.user_repository import UserRepository


@pytest.mark.db
def test_get_all_users(db_session: Session) -> None:
    """Return seeded users in their expected order."""
    users = get_all_users(db_session)
    assert len(users) == 3
    assert users[0].name == "Alice"
    assert users[1].email == "bob@example.com"


@pytest.mark.db
def test_user_repository_find_by_id() -> None:
    """Retrieve a user by identifier and close repository resources."""
    repo = UserRepository.initialize("sqlite:///:memory:")
    try:
        user = repo.find_by_id(2)
        assert user is not None
        assert user.name == "Bob"
    finally:
        repo.close()
