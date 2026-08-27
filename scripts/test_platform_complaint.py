# scripts/test_platform_complaint.py
"""
Test Suite for Phase 5: Platform Complaints.
Verifies model persistence, status transitions, and notification dispatch.
"""

import sys, os, pathlib
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from models.base import SessionLocal, Base, engine
from models.platform_complaint import PlatformComplaint, ComplaintStatus
from models.university import University
from models.user import User, UserRole
from services.email_service import send_complaint_notification_email


def run_tests():
    print("[START] Running Platform Complaint Test Suite...")
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        # 1. Fetch or create a test university & admin
        uni = db.query(University).filter(University.slug == "alpha-uni").first()
        if not uni:
            uni = University(name="Alpha University", slug="alpha-uni", status="approved", departments=["CS"])
            db.add(uni)
            db.commit()
            db.refresh(uni)

        admin = db.query(User).filter(User.email == "admin@alpha.edu").first()
        if not admin:
            admin = User(
                university_id=uni.id,
                name="Admin Alpha",
                email="admin@alpha.edu",
                password_hash="fakehash",
                role=UserRole.admin,
            )
            db.add(admin)
            db.commit()
            db.refresh(admin)

        # 2. Test Creating Platform Complaint
        print("[TEST] Creating Platform Complaint...")
        complaint = PlatformComplaint(
            university_id=uni.id,
            raised_by_user_id=admin.id,
            subject="Test Bug: RAG system slow response",
            message="The RAG system took over 10 seconds to respond to student inquiry.",
            status=ComplaintStatus.open,
        )
        db.add(complaint)
        db.commit()
        db.refresh(complaint)
        assert complaint.id is not None
        assert complaint.status == ComplaintStatus.open
        print(f"   [PASS] Created complaint ID={complaint.id} with status '{complaint.status.value}'.")

        # 3. Test Updating Status
        print("[TEST] Updating Complaint Status...")
        complaint.status = ComplaintStatus.in_progress
        db.commit()
        db.refresh(complaint)
        assert complaint.status == ComplaintStatus.in_progress
        print("   [PASS] Transitioned status to 'in_progress'.")

        complaint.status = ComplaintStatus.resolved
        from datetime import datetime, timezone
        complaint.resolved_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(complaint)
        assert complaint.status == ComplaintStatus.resolved
        assert complaint.resolved_at is not None
        print("   [PASS] Transitioned status to 'resolved' with resolved_at timestamp.")

        # 4. Test Notification Helper Execution (mock/dry-run)
        print("[TEST] Testing Email Notification Helper...")
        sent, msg = send_complaint_notification_email(
            to_email="platform.owner@test.com",
            submitted_by_name=admin.name,
            submitted_by_email=admin.email,
            university_name=uni.name,
            subject_text=complaint.subject,
            message_text=complaint.message,
        )
        # Note: sent may be True or False depending on Brevo key, but function must run without crashing.
        print(f"   [PASS] Notification function executed without error (Sent: {sent}, Message: {msg!r}).")

        # Clean up test complaint
        db.delete(complaint)
        db.commit()

        print("\n[SUCCESS] ALL PLATFORM COMPLAINT TESTS PASSED SUCCESSFULLY! [OK]")

    except Exception as e:
        db.rollback()
        print(f"\n[FAIL] Test suite failed: {e}")
        raise e
    finally:
        db.close()


if __name__ == "__main__":
    run_tests()
