# scripts/test_tenant_isolation.py
"""
Multi-Tenant Isolation Test Suite for UQMS.

This script:
1. Configures a clean temporary database and vector store path.
2. Creates two universities (Alpha and Beta).
3. Creates student and admin accounts for both universities.
4. Asserts that logins across tenants fail.
5. Asserts that TicketService operations for University Alpha cannot retrieve University Beta tickets.
6. Asserts that KB retrieval operations for University Alpha cannot query University Beta's vector database collection.
"""

import os
import sys
import shutil

# 1. Override CHROMA_PATH before importing any services to avoid polluting main data
TEST_CHROMA_PATH = "./data/test_chroma_isolation"
if os.path.exists(TEST_CHROMA_PATH):
    shutil.rmtree(TEST_CHROMA_PATH)
os.environ["CHROMA_PATH"] = TEST_CHROMA_PATH

# Set up test database path
TEST_DB_PATH = "./data/test_tenant_isolation.db"
if os.path.exists(TEST_DB_PATH):
    try:
        os.remove(TEST_DB_PATH)
    except PermissionError:
        pass
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB_PATH}"

# Ensure project root is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models.base import Base
from models.university import University
from models.user import User, UserRole
from models.ticket import Ticket, TicketPriority, TicketStatus
from services.auth_service import AuthService, DuplicateEmailError
from services.ticket_service import TicketService
from services.ingestion import ingest_to_vectorstore, retrieve

def run_tests():
    print("[START] Initializing Multi-Tenant Isolation Test Suite...")
    
    # 2. Setup SQLite DB
    engine = create_engine(f"sqlite:///{TEST_DB_PATH}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    try:
        # 3. Create Tenant Universities
        print("[SEED] Seeding test universities...")
        uni_alpha = University(name="University Alpha", slug="uni-alpha", department_list='["CS", "Math"]', status="approved")
        uni_beta = University(name="University Beta", slug="uni-beta", department_list='["Biology", "Chem"]', status="approved")
        db.add_all([uni_alpha, uni_beta])
        db.commit()
        db.refresh(uni_alpha)
        db.refresh(uni_beta)

        print(f"   Created: Alpha (ID={uni_alpha.id}), Beta (ID={uni_beta.id})")

        # 4. Create Users (Students & Admins)
        print("[SEED] Creating user accounts...")
        auth_svc = AuthService(db)
        
        # Alpha users
        student_alpha = auth_svc.register_user(
            university_id=uni_alpha.id,
            name="Alice Student",
            email="alice@alpha.edu",
            password="password123",
            role=UserRole.student,
            department="CS",
            privacy_consent_given=True
        )
        admin_alpha = auth_svc.register_user(
            university_id=uni_alpha.id,
            name="Aaron Admin",
            email="aaron@alpha.edu",
            password="password123",
            role=UserRole.admin,
            privacy_consent_given=True
        )

        # Beta users
        student_beta = auth_svc.register_user(
            university_id=uni_beta.id,
            name="Bob Student",
            email="bob@beta.edu",
            password="password123",
            role=UserRole.student,
            department="Biology",
            privacy_consent_given=True
        )
        admin_beta = auth_svc.register_user(
            university_id=uni_beta.id,
            name="Brenda Admin",
            email="brenda@beta.edu",
            password="password123",
            role=UserRole.admin,
            privacy_consent_given=True
        )
        db.commit()

        # Test Case 4.1: Same email registration across tenants must be allowed
        print("[TEST] Testing multi-tenant email uniqueness...")
        try:
            # Re-registering 'alice@alpha.edu' inside University Beta scope
            student_alpha_in_beta = auth_svc.register_user(
                university_id=uni_beta.id,
                name="Alice in Beta",
                email="alice@alpha.edu",
                password="password123",
                role=UserRole.student,
                department="Biology",
                privacy_consent_given=True
            )
            print("   [PASS] Registered same email ('alice@alpha.edu') in a different tenant (Beta).")
        except DuplicateEmailError:
            print("   [FAIL] Blocked cross-tenant same email registration.")
            assert False, "Same email registration should be allowed across different tenants."

        # Test Case 4.2: Duplicate email inside the SAME tenant must fail
        try:
            auth_svc.register_user(
                university_id=uni_alpha.id,
                name="Alice Duplicate",
                email="alice@alpha.edu",
                password="password123",
                role=UserRole.student,
                department="CS",
                privacy_consent_given=True
            )
            print("   [FAIL] Allowed duplicate email registration in the same tenant.")
            assert False, "Duplicate email registration inside the same tenant must fail."
        except DuplicateEmailError:
            print("   [PASS] Correctly blocked duplicate email in the same tenant.")

        # 5. Test Authentication Isolation
        print("[TEST] Testing Authentication Isolation...")
        
        # Test Case 5.1: Authenticating Alice against University Beta must fail
        user_auth = auth_svc.authenticate(university_id=uni_beta.id, email="alice@alpha.edu", password="password123")
        # Since we registered 'alice@alpha.edu' in beta (Test Case 4.1), this should return the Beta user, not the Alpha user!
        assert user_auth is not None and user_auth.name == "Alice in Beta"
        print("   [PASS] Scoped authentication successfully resolved tenant-specific user record.")

        # Test Case 5.2: Authenticating Aaron Admin against University Beta must return None
        admin_auth_wrong = auth_svc.authenticate(university_id=uni_beta.id, email="aaron@alpha.edu", password="password123")
        assert admin_auth_wrong is None
        print("   [PASS] Scoped authentication returned None for cross-tenant login attempt.")

        # 6. Test Ticket Isolation
        print("[TEST] Testing Ticket isolation...")
        ticket_svc_alpha = TicketService(db, university_id=uni_alpha.id)
        ticket_svc_beta = TicketService(db, university_id=uni_beta.id)

        ticket_alpha = ticket_svc_alpha.create_ticket(
            student_id=student_alpha.id,
            title="Alpha Ticket CS Inquiry",
            description="Need help with python assignment"
        )
        ticket_beta = ticket_svc_beta.create_ticket(
            student_id=student_beta.id,
            title="Beta Ticket Lab Inquiry",
            description="Need help with biology lab keys"
        )
        db.commit()

        # Test Case 6.1: TicketService Alpha must not fetch Beta ticket by ID
        fetched_beta_ticket_via_alpha = ticket_svc_alpha.get_ticket(ticket_beta.id)
        assert fetched_beta_ticket_via_alpha is None, "Alpha TicketService retrieved Beta ticket."
        print("   [PASS] Alpha service returned None for Beta ticket ID query.")

        # Test Case 6.2: Ticket list operations must return only tenant-specific tickets
        alpha_tickets = ticket_svc_alpha.list_tickets()
        beta_tickets = ticket_svc_beta.list_tickets()
        assert all(t.university_id == uni_alpha.id for t in alpha_tickets)
        assert all(t.university_id == uni_beta.id for t in beta_tickets)
        assert len(alpha_tickets) == 1
        assert len(beta_tickets) == 1
        print("   [PASS] List tickets operations strictly isolated by university ID.")

        # 7. Test Vector DB (KB) Isolation
        print("[TEST] Testing Knowledge Base Vector Isolation...")
        
        # Ingest documents
        ingest_alpha = ingest_to_vectorstore(
            university_id=uni_alpha.id,
            doc_id=101,
            text="Alpha University CS course guidelines: Python programming is mandatory."
        )
        ingest_beta = ingest_to_vectorstore(
            university_id=uni_beta.id,
            doc_id=201,
            text="Beta University Chemistry course guidelines: Lab safety rules are strict."
        )
        assert ingest_alpha is True
        assert ingest_beta is True
        print("   Uploaded test vector chunks.")

        # Retrieve using Alpha university_id
        results_alpha = retrieve(university_id=uni_alpha.id, query="course guidelines", k=5)
        # Retrieve using Beta university_id
        results_beta = retrieve(university_id=uni_beta.id, query="course guidelines", k=5)

        # Test Case 7.1: Alpha RAG query must return Alpha document chunks
        assert len(results_alpha) > 0
        assert all(r["university_id"] == uni_alpha.id for r in results_alpha)
        assert "Python" in results_alpha[0]["text"]
        print("   [PASS] Alpha RAG retrieval only returned Alpha document chunks.")

        # Test Case 7.2: Alpha RAG query must NOT return Beta document chunks
        assert not any("Chemistry" in r["text"] for r in results_alpha)
        assert not any(r["university_id"] == uni_beta.id for r in results_alpha)
        print("   [PASS] Alpha RAG query did not leak Beta university chunks.")

        # Test Case 7.3: Beta RAG query must return Beta document chunks
        assert len(results_beta) > 0
        assert all(r["university_id"] == uni_beta.id for r in results_beta)
        assert "Chemistry" in results_beta[0]["text"]
        print("   [PASS] Beta RAG retrieval only returned Beta document chunks.")

        print("\n[SUCCESS] ALL MULTI-TENANT ISOLATION TESTS PASSED SUCCESSFULLY! [OK]")

    finally:
        db.close()
        # Clean up database and vector files
        if os.path.exists(TEST_DB_PATH):
            try:
                os.remove(TEST_DB_PATH)
            except PermissionError:
                pass
        if os.path.exists(TEST_CHROMA_PATH):
            try:
                shutil.rmtree(TEST_CHROMA_PATH)
            except Exception:
                pass

if __name__ == "__main__":
    run_tests()
