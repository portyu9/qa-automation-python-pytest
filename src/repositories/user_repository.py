"""
UserRepository encapsulates database operations for the User model.
I use SQLAlchemy sessions to abstract queries, returning user objects without exposing
SQL details to my tests. This class provides convenient methods to initialize
an in-memory or file-based database, fetch all users, and fetch a single user
by id.
"""

from sqlalchemy.orm import Session

from sqlalchemy import create_engine

from ..db import get_engine, init_db, User


class UserRepository:
    """Repository layer for User database operations."""

    def __init__(self, session: Session) -> None:
        self.session = session

    @classmethod
    def initialize(cls, db_url: str = "sqlite:///qa_users.db") -> "UserRepository":
        """Initialize the repository by creating an engine, seeding data, and returning a session-wrapped repository.

        Args:
            db_url: Database URL string for SQLite. Defaults to file-based qa_users.db.

        Returns:
            A configured UserRepository instance with an active SQLAlchemy session.
        """
   # 
                engine = create_engine(db_url, echo=False, future=True)

        init_db(engine)
        
                        session = Session(bind=engine)
                return cls(session)

    def find_all(self):
        """Retrieve all users ordered by their primary key.

        Returns:
            List[User]: All user records from the database.
        """
        return self.session.query(User).order_by(User.id).all()

    def find_by_id(self, user_id: int):
        """Retrieve a single user by id.

        Args:
            user_id: The primary key of the user.

        Returns:
            User | None: The user record if found, otherwise None.
        """
        return self.session.query(User).filter(User.id == user_id).one_or_none()

    def close(self) -> None:
        """Close the underlying session.

        It's good practice to explicitly close sessions when the repository is no longer needed.
        """
        self.session.close()
