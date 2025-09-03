from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from sqlalchemy.engine import Engine

# Base class for ORM models
Base = declarative_base()

class User(Base):
    """
    ORM model representing a user record in the database. I define this here so that my tests can insert
    and query users with SQLAlchemy while keeping the schema explicit.
    """
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    name = Column(String)
    email = Column(String)


def get_engine(echo: bool = False) -> Engine:
    """
    Create a new in‑memory SQLite engine.

    The echo flag prints SQL statements for debugging when set to True.
    """
    return create_engine("sqlite:///:memory:", echo=echo, future=True)


def init_db(engine) -> None:
    """
    Create all tables defined on the Base metadata and seed initial users.

    This function is idempotent and can be called multiple times.
    """
    # Create tables
    Base.metadata.create_all(engine)

    # Open a session and insert sample users
    SessionLocal = sessionmaker(bind=engine, future=True)
    with SessionLocal() as session:
        session.add_all([
            User(name="Alice", email="alice@example.com"),
            User(name="Bob", email="bob@example.com"),
            User(name="Charlie", email="charlie@example.com"),
        ])
        session.commit()


def get_all_users(session: Session):
    """
    Retrieve all users from the database ordered by their id.
    """
    return session.query(User).order_by(User.id).all()
