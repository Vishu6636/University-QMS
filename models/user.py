# models/user.py
# User — scoped to a university (student or admin role).

import enum
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Enum
from sqlalchemy.orm import relationship
from models.base import Base


class UserRole(str, enum.Enum):
    student = "student"
    admin = "admin"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    university_id = Column(
        Integer,
        ForeignKey("universities.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=False, index=True)
    password_hash = Column(String(512), nullable=False)
    role = Column(
        Enum(UserRole, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=UserRole.student,
    )
    department = Column(String(255), nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    university = relationship("University", back_populates="users")
    tickets = relationship(
        "Ticket",
        back_populates="student",
        foreign_keys="Ticket.student_id",
        cascade="all, delete-orphan",
    )

    # Per-tenant email uniqueness is enforced at the service layer
    # (SQLite doesn't easily support partial unique indexes via SQLAlchemy).

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email!r} role={self.role}>"
