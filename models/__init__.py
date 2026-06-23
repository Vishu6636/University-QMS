# models/__init__.py
# Re-export all models and the shared Base + engine for convenience

from models.base import Base, engine, SessionLocal
from models.university import University
from models.user import User
from models.ticket import Ticket
from models.kb_document import KBDocument
from models.feedback import Feedback

__all__ = [
    "Base",
    "engine",
    "SessionLocal",
    "University",
    "User",
    "Ticket",
    "KBDocument",
    "Feedback",
]
