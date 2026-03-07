"""Database session management for CDP 360 Data Model."""

from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.models.base import Base


class DatabaseManager:
    """Manages database connections and sessions."""

    def __init__(self, connection_string: str):
        """Initialize with connection string.

        Args:
            connection_string: PostgreSQL connection string
        """
        self.engine = create_engine(
            connection_string,
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,
            pool_recycle=3600,
        )
        self.SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=self.engine,
        )

    def create_tables(self) -> None:
        """Create all tables defined in the models."""
        Base.metadata.create_all(bind=self.engine)

    def drop_tables(self) -> None:
        """Drop all tables - USE WITH CAUTION."""
        Base.metadata.drop_all(bind=self.engine)

    def get_session(self) -> Session:
        """Get a new database session.

        Caller is responsible for closing the session.
        """
        return self.SessionLocal()

    @contextmanager
    def session_scope(self) -> Generator[Session, None, None]:
        """Provide a transactional scope around a series of operations.

        Usage:
            with db_manager.session_scope() as session:
                session.add(organization)
                # Automatically committed or rolled back
        """
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()


# Global instance - initialize once per application
db_manager: DatabaseManager | None = None


def init_database(connection_string: str) -> DatabaseManager:
    """Initialize the global database manager.

    Args:
        connection_string: PostgreSQL connection string

    Returns:
        DatabaseManager instance
    """
    global db_manager
    db_manager = DatabaseManager(connection_string)
    return db_manager


def get_db_session() -> Session:
    """Get a database session from the global manager.

    Requires init_database() to have been called first.
    """
    if db_manager is None:
        raise RuntimeError("Database not initialized. Call init_database() first.")
    return db_manager.get_session()


@contextmanager
def db_session_scope() -> Generator[Session, None, None]:
    """Get a transactional scope from the global manager.

    Requires init_database() to have been called first.

    Usage:
        with db_session_scope() as session:
            session.add(organization)
    """
    if db_manager is None:
        raise RuntimeError("Database not initialized. Call init_database() first.")
    with db_manager.session_scope() as session:
        yield session
