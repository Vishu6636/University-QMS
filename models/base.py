# models/base.py
# Shared SQLAlchemy engine, session factory, and declarative base.
# Supports both SQLite (local dev) and Postgres (production) via DATABASE_URL.

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./data/university_qms.db")

# Render / Heroku expose postgres:// but SQLAlchemy 2.x requires postgresql://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# Ensure compatible driver if postgresql URL is used
if DATABASE_URL.startswith("postgresql://"):
    try:
        import psycopg  # noqa: F401
    except ImportError:
        try:
            import psycopg2  # noqa: F401
            DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg2://", 1)
        except ImportError:
            pass
elif DATABASE_URL.startswith("postgresql+psycopg://"):
    try:
        import psycopg  # noqa: F401
    except ImportError:
        try:
            import psycopg2  # noqa: F401
            DATABASE_URL = DATABASE_URL.replace("postgresql+psycopg://", "postgresql+psycopg2://", 1)
        except ImportError:
            pass

# SQLite needs check_same_thread=False for Streamlit's multi-thread access.
# Postgres benefits from pool_pre_ping to handle idle connection drops on free tiers.
is_sqlite = DATABASE_URL.startswith("sqlite")
connect_args = {"check_same_thread": False} if is_sqlite else {}

if is_sqlite:
    engine = create_engine(
        DATABASE_URL,
        connect_args=connect_args,
        echo=False,
    )
else:
    engine = create_engine(
        DATABASE_URL,
        connect_args=connect_args,
        pool_size=10,
        max_overflow=20,
        pool_recycle=1800,
        pool_pre_ping=True,
        echo=False,
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """Dependency-injection style session generator (compatible with FastAPI / Streamlit)."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

