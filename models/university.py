# models/university.py
# University — the root tenant entity.

import json
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, DateTime
from sqlalchemy.orm import relationship
from models.base import Base


class University(Base):
    __tablename__ = "universities"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, unique=True)
    slug = Column(String(100), nullable=False, unique=True, index=True)
    # Stored as a JSON string: ["CS", "MBA", "Law", ...]
    department_list = Column(Text, nullable=False, default="[]")
    status = Column(String(50), nullable=False, default="pending")
    rejection_reason = Column(Text, nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    users = relationship("User", back_populates="university", cascade="all, delete-orphan")
    tickets = relationship("Ticket", back_populates="university", cascade="all, delete-orphan")
    kb_documents = relationship("KBDocument", back_populates="university", cascade="all, delete-orphan")
    leads = relationship("Lead", back_populates="university", cascade="all, delete-orphan")

    # ── Helpers ────────────────────────────────────────────────────────────────

    @property
    def departments(self) -> list[str]:
        """Return department_list as a Python list."""
        try:
            return json.loads(self.department_list or "[]")
        except (ValueError, TypeError):
            return []

    @departments.setter
    def departments(self, value: list[str]) -> None:
        """Accept a list and serialise it to JSON for storage."""
        self.department_list = json.dumps(value)

    def __repr__(self) -> str:
        return f"<University id={self.id} slug={self.slug!r}>"
