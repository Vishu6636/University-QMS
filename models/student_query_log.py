# models/student_query_log.py
"""
StudentQueryLog — ephemeral record of student RAG chat questions.

Each entry is scoped to a university_id for multi-tenant isolation.
Rows older than 24 hours are auto-purged on admin dashboard load
to keep storage minimal on free-tier hosting.
"""

from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Index
from sqlalchemy.orm import relationship
from models.base import Base


class StudentQueryLog(Base):
    __tablename__ = "student_query_logs"

    id = Column(Integer, primary_key=True, index=True)
    university_id = Column(
        Integer, ForeignKey("universities.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    student_id = Column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    query_text = Column(Text, nullable=False)
    category = Column(String(50), nullable=False, default="general")
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )

    # Composite index for fast tenant-scoped cleanup queries
    __table_args__ = (
        Index("ix_student_query_logs_uni_created", "university_id", "created_at"),
    )

    # Relationships
    university = relationship("University", back_populates="student_query_logs")
    student = relationship("User", foreign_keys=[student_id])

    def __repr__(self) -> str:
        return f"<StudentQueryLog id={self.id} uni={self.university_id} category={self.category!r}>"
