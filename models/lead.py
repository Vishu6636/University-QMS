# models/lead.py
"""
Lead — captures prospective inquirer contact info from the public RAG chat.

Each lead is scoped to a university_id for multi-tenant isolation.
"""

from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from models.base import Base


class Lead(Base):
    __tablename__ = "leads"

    id = Column(Integer, primary_key=True, index=True)
    university_id = Column(
        Integer, ForeignKey("universities.id"), nullable=False, index=True
    )
    name = Column(String(255), nullable=True)              # optional
    email = Column(String(255), nullable=False)             # required for follow-up
    phone = Column(String(50), nullable=True)               # optional
    inquiry_summary = Column(Text, nullable=False)          # gist of the conversation
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    university = relationship("University", back_populates="leads")

    def __repr__(self) -> str:
        return f"<Lead id={self.id} email={self.email!r} university_id={self.university_id}>"
