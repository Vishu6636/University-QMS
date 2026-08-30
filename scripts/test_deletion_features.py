#!/usr/bin/env python
"""
scripts/test_deletion_features.py
Verifies the three new delete capabilities:
1. Student deletes own ticket (authorized vs unauthorized attempt).
2. Admin deletes ticket in own university (authorized vs unauthorized attempt).
3. Student permanent account deletion with cascade & audit logging.
"""

import time
import sys
import os
import pathlib
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv()

from models.base import SessionLocal
from models.user import User, UserRole
from models.ticket import Ticket, TicketStatus, TicketPriority
from models.university import University
from models.audit_log import AuditLog
from services.ticket_service import TicketService
from services.auth_service import AuthService


def get_test_universities(db):
    unis = db.query(University).all()
    if not unis:
        u1 = University(name="Test Uni 1", slug="test-uni-1", domain="test1.edu", departments=["CS", "IT"])
        u2 = University(name="Test Uni 2", slug="test-uni-2", domain="test2.edu", departments=["Finance"])
        db.add(u1)
        db.add(u2)
        db.commit()
        unis = [u1, u2]
    elif len(unis) == 1:
        u2 = University(name="Test Uni 2", slug="test-uni-2", domain="test2.edu", departments=["Finance"])
        db.add(u2)
        db.commit()
        unis.append(u2)
    return unis[0].id, unis[1].id


def test_student_ticket_deletion():
    print(f"\n{'='*65}")
    print("  TEST 1 — Student Ticket Deletion & Authorization Checks")
    print(f"{'='*65}")

    ts = int(time.time())
    db = SessionLocal()
    try:
        uni1_id, _ = get_test_universities(db)
        auth_svc = AuthService(db)

        # 1. Create 2 test students in Uni 1
        s1 = auth_svc.register_user(
            university_id=uni1_id,
            name="Delete Test Student 1",
            email=f"del_test_student1_{ts}@test.com",
            password="Password123",
            role=UserRole.student,
        )
        s2 = auth_svc.register_user(
            university_id=uni1_id,
            name="Delete Test Student 2",
            email=f"del_test_student2_{ts}@test.com",
            password="Password123",
            role=UserRole.student,
        )

        ticket_svc = TicketService(db, uni1_id)
        # Create ticket for Student 1
        t1 = ticket_svc.create_ticket(
            student_id=s1.id,
            title="S1 Library Query",
            description="Cannot log into library account",
        )
        print(f"  Created Ticket #{t1.id} for Student 1 (ID: {s1.id})")

        # Unauthorized attempt: Student 2 tries to delete Student 1's ticket
        unauth_passed = False
        try:
            ticket_svc.delete_ticket_by_student(t1.id, student_id=s2.id)
            print("  [FAIL] Student 2 was able to delete Student 1's ticket!")
        except PermissionError as pe:
            unauth_passed = True
            print(f"  [PASS] Server correctly blocked unauthorized deletion: '{pe}'")

        # Authorized attempt: Student 1 deletes own ticket
        auth_passed = False
        res = ticket_svc.delete_ticket_by_student(t1.id, student_id=s1.id)
        
        # Verify DB removal
        deleted_ticket = db.query(Ticket).filter(Ticket.id == t1.id).first()
        if res and deleted_ticket is None:
            auth_passed = True
            print(f"  [PASS] Student 1 successfully deleted own ticket #{t1.id}.")

        # Verify Audit Log entry
        audit_entry = db.query(AuditLog).filter(
            AuditLog.action == "ticket_deleted_by_student",
            AuditLog.target_id == t1.id,
        ).first()

        audit_passed = False
        if audit_entry and audit_entry.actor_user_id == s1.id:
            audit_passed = True
            print(f"  [PASS] AuditLog recorded: action='{audit_entry.action}' details={audit_entry.details[:80]}...")

        # Cleanup test users
        db.query(AuditLog).filter(AuditLog.actor_user_id.in_([s1.id, s2.id])).update({AuditLog.actor_user_id: None}, synchronize_session=False)
        db.delete(s1)
        db.delete(s2)
        db.commit()

        return unauth_passed and auth_passed and audit_passed

    finally:
        db.close()


def test_admin_ticket_deletion():
    print(f"\n{'='*65}")
    print("  TEST 2 — Admin Ticket Deletion & Tenant Scope Enforcement")
    print(f"{'='*65}")

    ts = int(time.time())
    db = SessionLocal()
    try:
        uni1_id, uni2_id = get_test_universities(db)
        auth_svc = AuthService(db)

        # Create admin for Uni 1 and admin for Uni 2
        admin1 = auth_svc.register_user(
            university_id=uni1_id,
            name="Uni 1 Admin",
            email=f"uni1_admin_del_{ts}@test.com",
            password="Password123",
            role=UserRole.admin,
        )
        student_uni2 = auth_svc.register_user(
            university_id=uni2_id,
            name="Uni 2 Student",
            email=f"uni2_student_del_{ts}@test.com",
            password="Password123",
            role=UserRole.student,
        )

        t_uni2_svc = TicketService(db, uni2_id)
        t_uni2 = t_uni2_svc.create_ticket(
            student_id=student_uni2.id,
            title="Uni 2 Fee Issue",
            description="Fee discrepancy on portal",
        )
        print(f"  Created Ticket #{t_uni2.id} under University {uni2_id}")

        # Cross-tenant unauthorized attempt: Admin 1 (Uni 1) tries to delete Uni 2 ticket
        t_uni1_svc = TicketService(db, uni1_id)
        cross_tenant_blocked = False
        try:
            t_uni1_svc.delete_ticket_by_admin(t_uni2.id, admin_user_id=admin1.id)
            print("  [FAIL] Admin 1 was able to delete Uni 2 ticket!")
        except (ValueError, PermissionError) as ex:
            cross_tenant_blocked = True
            print(f"  [PASS] Cross-tenant deletion blocked by server: '{ex}'")

        # Authorized deletion: Uni 2 Admin deletes Uni 2 ticket
        admin2 = auth_svc.register_user(
            university_id=uni2_id,
            name="Uni 2 Admin",
            email=f"uni2_admin_del_{ts}@test.com",
            password="Password123",
            role=UserRole.admin,
        )
        auth_admin_passed = False
        res = t_uni2_svc.delete_ticket_by_admin(t_uni2.id, admin_user_id=admin2.id)
        
        deleted_t2 = db.query(Ticket).filter(Ticket.id == t_uni2.id).first()
        if res and deleted_t2 is None:
            auth_admin_passed = True
            print(f"  [PASS] Admin 2 successfully deleted Uni 2 ticket #{t_uni2.id}.")

        audit_entry = db.query(AuditLog).filter(
            AuditLog.action == "ticket_deleted_by_admin",
            AuditLog.target_id == t_uni2.id,
        ).first()

        audit_passed = False
        if audit_entry and audit_entry.actor_user_id == admin2.id:
            audit_passed = True
            print(f"  [PASS] AuditLog recorded: action='{audit_entry.action}' actor={audit_entry.actor_user_id}")

        # Cleanup
        db.query(AuditLog).filter(AuditLog.actor_user_id.in_([admin1.id, admin2.id, student_uni2.id])).update({AuditLog.actor_user_id: None}, synchronize_session=False)
        db.delete(admin1)
        db.delete(admin2)
        db.delete(student_uni2)
        db.commit()

        return cross_tenant_blocked and auth_admin_passed and audit_passed

    finally:
        db.close()


def test_student_account_deletion():
    print(f"\n{'='*65}")
    print("  TEST 3 — Student Permanent Account Deletion")
    print(f"{'='*65}")

    ts = int(time.time())
    db = SessionLocal()
    try:
        uni1_id, _ = get_test_universities(db)
        auth_svc = AuthService(db)

        student = auth_svc.register_user(
            university_id=uni1_id,
            name="Account Delete Test",
            email=f"acc_del_student_{ts}@test.com",
            password="Password123",
            role=UserRole.student,
        )

        ticket_svc = TicketService(db, uni1_id)
        t = ticket_svc.create_ticket(
            student_id=student.id,
            title="Ticket before account deletion",
            description="This ticket should cascade delete when account is removed",
        )

        # Invalid confirmation text check
        invalid_confirm_blocked = False
        try:
            auth_svc.delete_student_account(student.id, uni1_id, confirmation_text="wrong")
            print("  [FAIL] Account deleted without typing 'DELETE'!")
        except ValueError as ve:
            invalid_confirm_blocked = True
            print(f"  [PASS] Blocked deletion with invalid confirmation: '{ve}'")

        # Valid deletion check
        res = auth_svc.delete_student_account(student.id, uni1_id, confirmation_text="DELETE")
        
        # Verify user is deleted
        deleted_user = db.query(User).filter(User.id == student.id).first()
        # Verify cascaded ticket deletion
        deleted_ticket = db.query(Ticket).filter(Ticket.id == t.id).first()

        account_deleted_passed = False
        if res and deleted_user is None and deleted_ticket is None:
            account_deleted_passed = True
            print(f"  [PASS] Student account and cascaded ticket #{t.id} permanently deleted.")

        # Verify AuditLog entry
        audit_entry = db.query(AuditLog).filter(
            AuditLog.action == "account_deleted",
            AuditLog.target_id == student.id,
        ).first()

        audit_passed = False
        if audit_entry:
            audit_passed = True
            print(f"  [PASS] AuditLog recorded: action='{audit_entry.action}' target_id={audit_entry.target_id} details={audit_entry.details[:80]}...")

        return invalid_confirm_blocked and account_deleted_passed and audit_passed

    finally:
        db.close()


def main():
    print("Running Deletion Capabilities Test Suite...\n")
    t1 = test_student_ticket_deletion()
    t2 = test_admin_ticket_deletion()
    t3 = test_student_account_deletion()

    print(f"\n{'='*65}")
    if t1 and t2 and t3:
        print("  ALL DELETION TESTS PASSED PERFECTLY!")
    else:
        print("  SOME TESTS FAILED — Check output above.")
    print(f"{'='*65}\n")

    return t1 and t2 and t3


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
