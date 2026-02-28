"""
backend.database
----------------
SQLAlchemy database engine and session configuration.

Sets up a SQLite database stored at ``./data/finance.db`` (relative to the
working directory where the backend is started).  The ``get_db`` generator is
used as a FastAPI dependency so each request gets its own database session that
is automatically closed when the request completes.

Usage
~~~~~
Inject ``db: Session = Depends(get_db)`` in any route function to get a
database session.  Use ``Base`` as the declarative base for all ORM models so
that ``Base.metadata.create_all(bind=engine)`` creates every table on startup.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

DATABASE_URL = "sqlite:///./data/finance.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    """Yield a database session and ensure it is closed after each request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
