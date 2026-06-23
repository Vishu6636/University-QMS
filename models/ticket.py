# models/ticket.py
# Ticket — a student's support request, scoped to a university.

import enum
from datetime import datetime, timezone
from sqlalchemy import (
    Column, Integer, String, Text, Float, DateTime,
    ForeignKey, Enum,
)
from sqlalchemy.orm import relationship
from models.base import Base


class TicketStatus(str, enum.Enum):
    open = "open"
    in_progress = "in_progress"
    resolved = "resolved"
    escalated = "escalated"
    closed = "closed"
    reopened = "reopened"


class TicketPriority(str, enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class Ticket(Base):
    __tablename__ = "tickets"

    id = Column(Integer, primary_key=True, index=True)
    university_id = Column(
        Integer,
        ForeignKey("universities.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    student_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title = Column(String(500), nullable=False)
    description = Column(Text, nullable=False)
    department = Column(String(255), nullable=False)
    status = Column(
        Enum(TicketStatus, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=TicketStatus.open,
    )
    priority = Column(
        Enum(TicketPriority, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=TicketPriority.medium,
    )
    # Sentiment score in [-1.0, 1.0] — populated by the sentiment service.
    sentiment_score = Column(Float, nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    resolved_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    university = relationship("University", back_populates="tickets")
    student = relationship("User", back_populates="tickets", foreign_keys=[student_id])
    feedback = relationship("Feedback", back_populates="ticket", uselist=False, cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Ticket id={self.id} status={self.status} priority={self.priority}>"
