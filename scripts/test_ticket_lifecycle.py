# scripts/test_ticket_lifecycle.py
"""
Verification script for the Ticket Lifecycle and RAG Escalation pipeline.
"""

import os
import sys
import logging

# Ensure project root is on path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from models.base import SessionLocal
from models.university import University
from models.user import User, UserRole
from models.ticket import Ticket, TicketStatus, TicketPriority
from services.ticket_service import TicketService, get_tickets_for_university
from services.rag_chat import answer_query

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("test_ticket_lifecycle")


def main():
    db = SessionLocal()
    try:
        # 1. Fetch or create a test university and student
        uni = db.query(University).filter(University.slug == "greenfield").first()
        if not uni:
            uni = University(
                name="Greenfield University",
                slug="greenfield",
                department_list='["Computer Science", "Mathematics", "Business", "Law", "Finance & Accounts", "Library"]',
            )
            db.add(uni)
            db.commit()
            db.refresh(uni)

        student = db.query(User).filter(User.role == UserRole.student, User.university_id == uni.id).first()
        if not student:
            student = User(
                university_id=uni.id,
                name="Test Student",
                email="test_student@greenfield.edu",
                password_hash="dummy_hash",
                role=UserRole.student,
            )
            db.add(student)
            db.commit()
            db.refresh(student)

        log.info(f"Using University: {uni.name} (ID: {uni.id})")
        log.info(f"Using Student: {student.name} (ID: {student.id})")

        svc = TicketService(db, uni.id)

        # ── Test 1: Ticket Creation with Auto-Predictions ──
        log.info("\n--- Test 1: create_ticket with ML predictions ---")
        desc = "where is the library and how do I borrow books? I need this info immediately."
        ticket = svc.create_ticket(
            student_id=student.id,
            title="Library Query",
            description=desc,
        )

        log.info(f"Created Ticket ID: {ticket.id}")
        log.info(f"Predicted Department: {ticket.department}")
        log.info(f"Predicted Priority: {ticket.priority}")
        log.info(f"Sentiment Score: {ticket.sentiment_score}")
        log.info(f"Initial Status: {ticket.status}")

        assert ticket.status == TicketStatus.open
        assert ticket.department in uni.departments
        assert ticket.priority in TicketPriority
        assert ticket.sentiment_score is not None

        # ── Test 2: Valid and Invalid Transitions ──
        log.info("\n--- Test 2: Ticket Status Transitions ---")
        
        # Open -> In Progress (Valid)
        ticket = svc.update_ticket_status(ticket.id, TicketStatus.in_progress)
        log.info(f"Transitioned to: {ticket.status} (Expected: in_progress)")
        assert ticket.status == TicketStatus.in_progress

        # In Progress -> Resolved (Valid)
        ticket = svc.update_ticket_status(ticket.id, TicketStatus.resolved)
        log.info(f"Transitioned to: {ticket.status} (Expected: resolved)")
        assert ticket.status == TicketStatus.resolved
        assert ticket.resolved_at is not None

        # Resolved -> Closed (Valid)
        ticket = svc.update_ticket_status(ticket.id, TicketStatus.closed)
        log.info(f"Transitioned to: {ticket.status} (Expected: closed)")
        assert ticket.status == TicketStatus.closed

        # Closed -> In Progress (Invalid)
        try:
            svc.update_ticket_status(ticket.id, TicketStatus.in_progress)
            raise AssertionError("Invalid transition Closed -> In Progress was allowed!")
        except ValueError as e:
            log.info(f"Successfully blocked invalid transition: {e}")

        # ── Test 3: Standalone and Service Filters ──
        log.info("\n--- Test 3: get_tickets_for_university ---")
        all_tickets = get_tickets_for_university(db, uni.id)
        log.info(f"Total tickets for university: {len(all_tickets)}")
        assert len(all_tickets) > 0

        closed_tickets = get_tickets_for_university(db, uni.id, {"status": TicketStatus.closed})
        log.info(f"Closed tickets: {len(closed_tickets)}")
        assert any(t.id == ticket.id for t in closed_tickets)

        # ── Test 4: RAG Escalation to Ticket ──
        log.info("\n--- Test 4: RAG Escalation Auto-Ticket Creation ---")
        # Query that cannot be found (fake query)
        query = "What is the secret code for the back entrance of the math department?"
        res = answer_query(uni.id, query, db=db, student_id=student.id)

        log.info(f"RAG Response Answer:\n{res['answer']}")
        log.info(f"RAG Response Escalated: {res['escalate']}")

        assert res["escalate"] is True
        assert "Ticket #" in res["answer"]

        # Verify ticket was actually created in DB
        created_tickets = db.query(Ticket).filter(
            Ticket.student_id == student.id,
            Ticket.description == query
        ).all()
        assert len(created_tickets) >= 1
        log.info(f"Verified escalation ticket ID: {created_tickets[0].id}")
        log.info(f"Escalation ticket department: {created_tickets[0].department}")
        log.info(f"Escalation ticket priority: {created_tickets[0].priority}")

        log.info("\n✅ All ticket lifecycle and RAG escalation tests passed successfully!")

    finally:
        db.close()


if __name__ == "__main__":
    main()
