# models/feedback.py
# Feedback — one-to-one post-resolution satisfaction record for a ticket.

from sqlalchemy import Column, Integer, Float, Text, ForeignKey
from sqlalchemy.orm import relationship
from models.base import Base


class Feedback(Base):
    __tablename__ = "feedback"

    id = Column(Integer, primary_key=True, index=True)
    ticket_id = Column(
        Integer,
        ForeignKey("tickets.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,  # enforces the 1-to-1 relationship at DB level
        index=True,
    )
    # Integer 1-5 star score stored as float to allow fractional aggregations.
    satisfaction_score = Column(Float, nullable=False)
    comment = Column(Text, nullable=True)

    # Relationships
    ticket = relationship("Ticket", back_populates="feedback")

    def __repr__(self) -> str:
        return f"<Feedback id={self.id} ticket_id={self.ticket_id} score={self.satisfaction_score}>"
