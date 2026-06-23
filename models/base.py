# models/base.py
# Shared SQLAlchemy engine, session factory, and declarative base.

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./data/university_qms.db")

# SQLite needs check_same_thread=False for Streamlit's multi-thread access.
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    echo=False,  # Set to True for SQL debug logging
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
