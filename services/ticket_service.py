# services/ticket_service.py
"""
TicketService — CRUD and filtering for support tickets.

All queries automatically filter by university_id so tenants can never
see each other's data.
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy import desc

from models.ticket import Ticket, TicketStatus, TicketPriority
from models.feedback import Feedback

log = logging.getLogger(__name__)


class TicketService:
    """Manages ticket lifecycle scoped to a university tenant."""

    def __init__(self, db: Session, university_id: int) -> None:
        self.db = db
        self.university_id = university_id

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _base_query(self):
        """Return a query pre-filtered to this tenant."""
        return self.db.query(Ticket).filter(
            Ticket.university_id == self.university_id
        )

    # ── Create ─────────────────────────────────────────────────────────────────

    def create_ticket(
        self,
        *,
        student_id: int,
        title: str,
        description: str,
        department: Optional[str] = None,
        priority: Optional[TicketPriority] = None,
        sentiment_score: Optional[float] = None,
    ) -> Ticket:
        """
        Open a new ticket. Auto-calls intent classifier and priority predictor
        if department or priority is not provided.
        """
        # 1. Calculate sentiment score if not provided
        if sentiment_score is None:
            try:
                from services.priority_model import sentiment_score as calc_sentiment
                sentiment_score = calc_sentiment(description)
            except Exception as e:
                log.warning("Failed to calculate sentiment score: %s", e)
                sentiment_score = 0.0

        # 2. Determine department if not provided
        if not department:
            try:
                from services.intent_classifier import predict_intent
                from models.university import University
                
                intent = predict_intent(description)
                uni = self.db.query(University).filter(University.id == self.university_id).first()
                uni_depts = uni.departments if uni else []
                department = map_intent_to_department(intent, uni_depts)
            except Exception as e:
                log.warning("Failed to predict intent/department: %s", e)
                # Fallback to first department of university, or "General"
                from models.university import University
                uni = self.db.query(University).filter(University.id == self.university_id).first()
                if uni and uni.departments:
                    department = uni.departments[0]
                else:
                    department = "General"

        # 3. Determine priority if not provided
        if not priority:
            try:
                from services.priority_model import predict_priority
                pred_prio_str = predict_priority(description, department)
                # Convert string "low" / "medium" / "high" to TicketPriority enum
                priority = TicketPriority(pred_prio_str.lower())
            except Exception as e:
                log.warning("Failed to predict priority: %s", e)
                priority = TicketPriority.medium

        ticket = Ticket(
            university_id=self.university_id,
            student_id=student_id,
            title=title,
            description=description,
            department=department,
            priority=priority,
            status=TicketStatus.open,
            sentiment_score=sentiment_score,
        )
        self.db.add(ticket)
        self.db.commit()
        self.db.refresh(ticket)
        log.info("Created ticket id=%s for student_id=%s department=%s priority=%s",
                 ticket.id, student_id, ticket.department, ticket.priority)
        return ticket

    # ── Read ───────────────────────────────────────────────────────────────────

    def get_ticket(self, ticket_id: int) -> Optional[Ticket]:
        """Fetch a single ticket, enforcing tenant scope."""
        return self._base_query().filter(Ticket.id == ticket_id).first()

    def list_tickets(
        self,
        *,
        student_id: Optional[int] = None,
        status: Optional[TicketStatus] = None,
        department: Optional[str] = None,
        priority: Optional[TicketPriority] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Ticket]:
        """
        Return tickets for this university with optional filters.
        Pass student_id to restrict to a single student's tickets.
        """
        q = self._base_query()
        if student_id is not None:
            q = q.filter(Ticket.student_id == student_id)
        if status is not None:
            q = q.filter(Ticket.status == status)
        if department is not None:
            q = q.filter(Ticket.department == department)
        if priority is not None:
            q = q.filter(Ticket.priority == priority)
        return (
            q.order_by(desc(Ticket.created_at))
            .offset(offset)
            .limit(limit)
            .all()
        )

    def count_tickets(self, *, status: Optional[TicketStatus] = None) -> int:
        q = self._base_query()
        if status:
            q = q.filter(Ticket.status == status)
        return q.count()

    def get_tickets_for_university(self, filters: Optional[dict] = None) -> list[Ticket]:
        """
        Fetch tickets for the active university applying a dictionary of filters.
        """
        filters = filters or {}
        return self.list_tickets(
            status=filters.get("status"),
            department=filters.get("department"),
            priority=filters.get("priority"),
            student_id=filters.get("student_id"),
            limit=filters.get("limit", 100),
            offset=filters.get("offset", 0),
        )

    # ── Update ─────────────────────────────────────────────────────────────────

    def update_status(self, ticket_id: int, new_status: TicketStatus) -> Ticket:
        """Change ticket status, validating transition rules."""
        return self.update_ticket_status(ticket_id, new_status)

    def update_ticket_status(self, ticket_id: int, new_status: TicketStatus) -> Ticket:
        """
        Change ticket status enforcing valid transition rules:
          - open -> in_progress
          - in_progress -> resolved or escalated
          - resolved -> closed or reopened (which allows open or reopened status)
          - escalated -> resolved or in_progress
          - reopened -> in_progress
        """
        ticket = self.get_ticket(ticket_id)
        if not ticket:
            raise ValueError(f"Ticket {ticket_id} not found in this university.")

        current = ticket.status
        if isinstance(new_status, str):
            new_status = TicketStatus(new_status)

        # Transition validation rules
        valid = False
        if current == TicketStatus.open:
            valid = (new_status == TicketStatus.in_progress)
        elif current == TicketStatus.in_progress:
            valid = (new_status in (TicketStatus.resolved, TicketStatus.escalated))
        elif current == TicketStatus.resolved:
            valid = (new_status in (TicketStatus.closed, TicketStatus.reopened, TicketStatus.open))
        elif current == TicketStatus.escalated:
            valid = (new_status in (TicketStatus.resolved, TicketStatus.in_progress, TicketStatus.open))
        elif current == TicketStatus.reopened:
            valid = (new_status == TicketStatus.in_progress)
        elif current == TicketStatus.closed:
            valid = False

        if not valid:
            raise ValueError(
                f"Invalid status transition from '{current.value}' to '{new_status.value}'."
            )

        ticket.status = new_status
        if new_status == TicketStatus.resolved and ticket.resolved_at is None:
            ticket.resolved_at = datetime.now(timezone.utc)
            
        self.db.commit()
        self.db.refresh(ticket)
        log.info("Updated ticket id=%s status from %s to %s", ticket.id, current, new_status)
        return ticket

    def update_priority(self, ticket_id: int, new_priority: TicketPriority) -> Ticket:
        ticket = self.get_ticket(ticket_id)
        if not ticket:
            raise ValueError(f"Ticket {ticket_id} not found in this university.")
        ticket.priority = new_priority
        self.db.commit()
        self.db.refresh(ticket)
        return ticket

    def set_sentiment(self, ticket_id: int, score: float) -> Ticket:
        """Store a sentiment score computed by the ML pipeline."""
        ticket = self.get_ticket(ticket_id)
        if not ticket:
            raise ValueError(f"Ticket {ticket_id} not found.")
        ticket.sentiment_score = score
        self.db.commit()
        self.db.refresh(ticket)
        return ticket

    # ── Feedback ───────────────────────────────────────────────────────────────

    def add_feedback(
        self, ticket_id: int, satisfaction_score: float, comment: str = ""
    ) -> Feedback:
        """
        Attach post-resolution feedback to a ticket.

        Raises:
            ValueError: if ticket not found or feedback already submitted.
        """
        ticket = self.get_ticket(ticket_id)
        if not ticket:
            raise ValueError(f"Ticket {ticket_id} not found in this university.")
        if ticket.feedback:
            raise ValueError(f"Feedback already submitted for ticket {ticket_id}.")
        fb = Feedback(
            ticket_id=ticket_id,
            satisfaction_score=satisfaction_score,
            comment=comment,
        )
        self.db.add(fb)
        self.db.commit()
        self.db.refresh(fb)
        return fb

    # ── Stats ──────────────────────────────────────────────────────────────────

    def status_summary(self) -> dict[str, int]:
        """Return a dict of {status: count} for dashboard KPIs."""
        return {
            status.value: self.count_tickets(status=status)
            for status in TicketStatus
        }


# ── Module-level helper functions ───────────────────────────────────────────

def map_intent_to_department(intent: str, departments: list[str]) -> str:
    """Map intent string to the most relevant department in a university's list."""
    mapping_keywords = {
        "scholarship_inquiry": ["finance", "accounts", "bursary", "scholarship", "fees"],
        "fee_payment": ["finance", "accounts", "bursary", "fees", "payment"],
        "exam_schedule": ["exam", "examination", "registry", "academic"],
        "hostel_booking": ["hostel", "residential", "housing", "accommodation"],
        "attendance_policy": ["student affairs", "welfare", "attendance", "admin"],
        "course_registration": ["computer science", "information technology", "engineering", "academic"],
        "library_access": ["library", "digital library", "learning resources"],
        "placement_info": ["placement", "career", "services", "employment"],
        "grievance": ["student affairs", "welfare", "grievance", "complaints"],
        "document_request": ["exam", "examination", "registry", "academic", "office"],
        "admission_query": ["student affairs", "welfare", "admission", "admin"],
        "revaluation_request": ["exam", "examination", "registry", "academic"],
    }
    
    if not departments:
        return "General Support"
        
    keywords = mapping_keywords.get(intent, [])
    for kw in keywords:
        for dept in departments:
            if kw in dept.lower():
                return dept
                
    return departments[0]


def get_tickets_for_university(
    db: Session,
    university_id: int,
    filters: Optional[dict] = None,
) -> list[Ticket]:
    """Standalone helper function to fetch tickets for a university with filters."""
    svc = TicketService(db, university_id)
    return svc.get_tickets_for_university(filters)
