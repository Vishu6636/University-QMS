# services/audit_service.py
"""
AuditService — lightweight helper to write audit log entries.

Usage:
    AuditService.log(db,
        university_id=uni.id,
        actor_user_id=user.id,
        action="kb_doc_upload",
        target_type="KBDocument",
        target_id=doc.id,
        details='{"filename": "handbook.pdf"}',
    )
"""

import json
import logging
from typing import Any, Optional

from sqlalchemy.orm import Session

from models.audit_log import AuditLog

log = logging.getLogger(__name__)


class AuditService:
    """Write-only audit log helper. All methods are static — no instance needed."""

    @staticmethod
    def log(
        db: Session,
        *,
        university_id: Optional[int] = None,
        actor_user_id: Optional[int] = None,
        action: str,
        target_type: Optional[str] = None,
        target_id: Optional[int] = None,
        details: Optional[Any] = None,
    ) -> AuditLog:
        """
        Record an audit event.

        Args:
            db:              Active SQLAlchemy session.
            university_id:   Tenant scope (None for cross-tenant super admin actions).
            actor_user_id:   User who performed the action (None for system actions).
            action:          Short action identifier, e.g. 'kb_doc_upload'.
            target_type:     Model name, e.g. 'KBDocument', 'Ticket'.
            target_id:       Primary key of the affected record.
            details:         Extra context — accepts dict (auto-serialised to JSON) or string.

        Returns:
            The persisted AuditLog entry.
        """
        # Serialise dict/list details to JSON string
        if details is not None and not isinstance(details, str):
            try:
                details = json.dumps(details, default=str)
            except (TypeError, ValueError):
                details = str(details)

        entry = AuditLog(
            university_id=university_id,
            actor_user_id=actor_user_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            details=details,
        )
        db.add(entry)
        db.commit()
        log.info(
            "Audit: action=%s target=%s:%s actor=%s uni=%s",
            action, target_type, target_id, actor_user_id, university_id,
        )
        return entry
