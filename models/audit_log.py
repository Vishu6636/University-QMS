# models/audit_log.py
"""
AuditLog — immutable record of significant system actions.

Each entry captures who did what, to which object, and when.
Scoped to university_id for tenant-level audit views; super admin
actions may have university_id=None for cross-tenant operations.
"""

from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from models.base import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    university_id = Column(
        Integer, ForeignKey("universities.id"), nullable=True, index=True
    )
    actor_user_id = Column(
        Integer, ForeignKey("users.id"), nullable=True
    )
    action = Column(String(100), nullable=False, index=True)
    target_type = Column(String(50), nullable=True)
    target_id = Column(Integer, nullable=True)
    details = Column(Text, nullable=True)       # JSON string with extra context
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )

    # Relationships (optional — for joining display names)
    university = relationship("University", foreign_keys=[university_id])
    actor = relationship("User", foreign_keys=[actor_user_id])

    def __repr__(self) -> str:
        return f"<AuditLog id={self.id} action={self.action!r} target={self.target_type}:{self.target_id}>"
