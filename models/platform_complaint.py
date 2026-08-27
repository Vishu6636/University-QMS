# models/platform_complaint.py
"""
PlatformComplaint — system complaint raised by an admin or super admin
to platform engineering / super admin team.
"""

import enum
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Enum
from sqlalchemy.orm import relationship
from models.base import Base


class ComplaintStatus(str, enum.Enum):
    open = "open"
    in_progress = "in_progress"
    resolved = "resolved"


class PlatformComplaint(Base):
    __tablename__ = "platform_complaints"

    id = Column(Integer, primary_key=True, index=True)
    university_id = Column(
        Integer,
        ForeignKey("universities.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    raised_by_user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    subject = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    status = Column(
        Enum(ComplaintStatus, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=ComplaintStatus.open,
    )
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )
    resolved_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    university = relationship("University", back_populates="platform_complaints")
    raised_by_user = relationship("User", foreign_keys=[raised_by_user_id])

    def __repr__(self) -> str:
        return f"<PlatformComplaint id={self.id} status={self.status!r} subject={self.subject!r}>"
