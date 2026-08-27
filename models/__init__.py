# models/__init__.py
# Re-export all models and the shared Base + engine for convenience

from models.base import Base, engine, SessionLocal
from models.university import University
from models.user import User
from models.ticket import Ticket
from models.kb_document import KBDocument
from models.feedback import Feedback
from models.lead import Lead
from models.audit_log import AuditLog
from models.student_query_log import StudentQueryLog
from models.platform_complaint import PlatformComplaint, ComplaintStatus

__all__ = [
    "Base",
    "engine",
    "SessionLocal",
    "University",
    "User",
    "Ticket",
    "KBDocument",
    "Feedback",
    "Lead",
    "AuditLog",
    "StudentQueryLog",
    "PlatformComplaint",
    "ComplaintStatus",
]
