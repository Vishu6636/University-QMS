#!/usr/bin/env python
# scripts/db_init.py
"""
Database initialiser for the University Query Management System.

Run once (or whenever the schema changes) to create all tables:

    python scripts/db_init.py

Optionally seed demo data with:

    python scripts/db_init.py --seed
"""

import argparse
import logging
import sys
import os

# Make sure the project root is on PYTHONPATH when running directly.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from models.base import Base, engine, SessionLocal          # noqa: E402
from models.university import University                    # noqa: E402
from models.user import User, UserRole                      # noqa: E402
from models.ticket import Ticket, TicketStatus, TicketPriority  # noqa: E402
from models.kb_document import KBDocument, DocType          # noqa: E402
from models.feedback import Feedback                        # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)


# ── Schema creation ────────────────────────────────────────────────────────────

def create_tables() -> None:
    """Create all tables defined via SQLAlchemy models."""
    log.info("Creating database tables at: %s", engine.url)
    Base.metadata.create_all(bind=engine)
    log.info("✅  All tables created successfully.")


def drop_tables() -> None:
    """Drop all tables — USE WITH CAUTION."""
    log.warning("⚠️  Dropping all tables!")
    Base.metadata.drop_all(bind=engine)
    log.info("Tables dropped.")


# ── Seed data ──────────────────────────────────────────────────────────────────

def seed_demo_data() -> None:
    """Insert minimal demo data for local development and testing."""
    from services.auth_service import _hash_password as _hash

    db = SessionLocal()
    try:
        # ── Universities ──────────────────────────────────────────────────────
        if db.query(University).count() > 0:
            log.info("Seed data already present — skipping.")
            return

        unis = [
            University(
                name="Greenfield University",
                slug="greenfield",
                department_list='["Computer Science", "Mathematics", "Business", "Law"]',
                status="approved",
            ),
            University(
                name="Silverstone Institute of Technology",
                slug="silverstone",
                department_list='["Engineering", "Physics", "Data Science"]',
                status="approved",
            ),
        ]
        db.add_all(unis)
        db.flush()  # populate IDs

        # ── Super Admin ───────────────────────────────────────────────────────
        from dotenv import load_dotenv
        load_dotenv()
        superadmin_email = os.environ.get("SUPERADMIN_EMAIL")
        superadmin_password = os.environ.get("SUPERADMIN_PASSWORD")
        if superadmin_email and superadmin_password:
            superadmin = User(
                university_id=None,
                name="System Super Admin",
                email=superadmin_email,
                password_hash=_hash(superadmin_password),
                role=UserRole.super_admin,
            )
            db.add(superadmin)
            db.flush()
            log.info("Super Admin seeded successfully.")
        else:
            log.warning("SUPERADMIN_EMAIL and SUPERADMIN_PASSWORD environment variables not set — skipping Super Admin seeding.")

        # ── Admins ────────────────────────────────────────────────────────────
        admins = [
            User(
                university_id=unis[0].id,
                name="Alice Admin",
                email="admin@greenfield.edu",
                password_hash=_hash("admin123"),
                role=UserRole.admin,
            ),
            User(
                university_id=unis[1].id,
                name="Bob Admin",
                email="admin@silverstone.edu",
                password_hash=_hash("admin123"),
                role=UserRole.admin,
            ),
        ]
        db.add_all(admins)
        db.flush()

        # ── Students ──────────────────────────────────────────────────────────
        students = [
            User(
                university_id=unis[0].id,
                name="Carol Student",
                email="carol@greenfield.edu",
                password_hash=_hash("student123"),
                role=UserRole.student,
                department="Computer Science",
            ),
            User(
                university_id=unis[1].id,
                name="Dave Student",
                email="dave@silverstone.edu",
                password_hash=_hash("student123"),
                role=UserRole.student,
                department="Engineering",
            ),
        ]
        db.add_all(students)
        db.flush()

        # ── KB Documents ──────────────────────────────────────────────────────
        docs = [
            KBDocument(
                university_id=unis[0].id,
                filename="greenfield_faq.pdf",
                content_text=(
                    "Q: How do I register for courses?\n"
                    "A: Log in to the student portal and navigate to Course Registration.\n\n"
                    "Q: What is the grading policy?\n"
                    "A: Grades are awarded on a 10-point scale. A grade below 5.0 is a fail."
                ),
                doc_type=DocType.faq,
            ),
            KBDocument(
                university_id=unis[0].id,
                filename="academic_policy_2024.pdf",
                content_text=(
                    "Academic Integrity Policy: All submitted work must be original. "
                    "Plagiarism will result in disciplinary action as per the student handbook."
                ),
                doc_type=DocType.policy,
            ),
            KBDocument(
                university_id=unis[1].id,
                filename="silverstone_circular_june.pdf",
                content_text=(
                    "Circular No. 12/2024: The mid-semester break is scheduled from "
                    "15 July to 22 July. Labs will remain accessible with prior permission."
                ),
                doc_type=DocType.circular,
            ),
        ]
        db.add_all(docs)
        db.flush()

        # ── Tickets ───────────────────────────────────────────────────────────
        tickets = [
            Ticket(
                university_id=unis[0].id,
                student_id=students[0].id,
                title="Cannot access library portal",
                description="I keep getting a 403 error when trying to log in to the digital library.",
                department="Computer Science",
                status=TicketStatus.open,
                priority=TicketPriority.high,
                sentiment_score=-0.45,
            ),
            Ticket(
                university_id=unis[0].id,
                student_id=students[0].id,
                title="Fee receipt not generated",
                description="I paid my fees 3 days ago but still haven't received the receipt.",
                department="Business",
                status=TicketStatus.in_progress,
                priority=TicketPriority.medium,
                sentiment_score=-0.60,
            ),
            Ticket(
                university_id=unis[1].id,
                student_id=students[1].id,
                title="Lab equipment booking",
                description="I need to reserve the spectrometer for my research project next week.",
                department="Physics",
                status=TicketStatus.resolved,
                priority=TicketPriority.low,
                sentiment_score=0.20,
            ),
        ]
        db.add_all(tickets)
        db.flush()

        # ── Feedback ──────────────────────────────────────────────────────────
        fb = Feedback(
            ticket_id=tickets[2].id,
            satisfaction_score=4.5,
            comment="Issue resolved quickly, thank you!",
        )
        db.add(fb)

        db.commit()
        log.info("🌱  Demo data seeded successfully.")

    except Exception:
        db.rollback()
        log.exception("Seed failed — rolled back.")
        raise
    finally:
        db.close()


# ── Entry point ────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Initialise the University QMS database."
    )
    parser.add_argument(
        "--seed",
        action="store_true",
        help="Insert demo universities, users, tickets, documents and feedback.",
    )
    parser.add_argument(
        "--drop",
        action="store_true",
        help="Drop all tables before creating them (destructive!).",
    )
    args = parser.parse_args()

    if args.drop:
        confirm = input("Type 'yes' to confirm dropping all tables: ")
        if confirm.strip().lower() != "yes":
            log.info("Aborted.")
            return
        drop_tables()

    create_tables()

    if args.seed:
        seed_demo_data()


if __name__ == "__main__":
    main()
