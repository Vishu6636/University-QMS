#!/usr/bin/env python
"""
scripts/test_otp_and_email.py

Regression test suite for OTP verification & Brevo email service.
Tests:
  1. OTP generation, 5-minute TTL, and verification logic.
  2. Rate limiting (max 3 OTP requests per email per 10 minutes).
  3. Brevo email API payloads for OTP and Welcome Emails (Admin & Student).
  4. Assertion that unverified OTP flows leave zero orphaned rows in DB.
"""

import sys
import os
import pathlib
import io
import time
from unittest.mock import patch, MagicMock

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv()

from models.base import SessionLocal
from models.university import University
from models.user import User, UserRole
from services.otp_service import OTPService, otp_service
from services.rate_limiter import RateLimiter, otp_limiter
from services.email_service import send_otp_email, send_welcome_email, _send_brevo_email


def test_otp_service():
    print(f"\n{'='*65}")
    print("  1. TEST — OTP Generation & Expiry")
    print(f"{'='*65}")

    svc = OTPService(ttl_seconds=2)
    email = "test_otp@university.edu"
    payload = {"name": "Test User", "role": "student"}

    code = svc.generate_otp(email, pending_data=payload)
    assert len(code) == 6 and code.isdigit(), f"Expected 6-digit OTP, got {code}"
    print(f"  [PASS] Generated 6-digit OTP: {code}")

    # Wrong code test
    ok, msg, _ = svc.verify_otp(email, "000000")
    assert not ok, "Wrong OTP should have failed!"
    print(f"  [PASS] Mismatched OTP correctly rejected")

    # Correct code test
    ok, msg, res_payload = svc.verify_otp(email, code)
    assert ok, f"Correct OTP failed: {msg}"
    assert res_payload.get("name") == "Test User", f"Payload mismatch: {res_payload}"
    print(f"  [PASS] Correct OTP verified & payload retrieved: {res_payload}")

    # Expiry test
    code_exp = svc.generate_otp(email, pending_data=payload)
    time.sleep(2.1)
    ok_exp, msg_exp, _ = svc.verify_otp(email, code_exp)
    assert not ok_exp, "Expired OTP should have failed!"
    print(f"  [PASS] Expired OTP correctly rejected")


def test_otp_rate_limiter():
    print(f"\n{'='*65}")
    print("  2. TEST — Rate Limiting (max 3 OTP requests / 10 min)")
    print(f"{'='*65}")

    limiter = RateLimiter(max_attempts=3, window_seconds=600)
    email = "rate_limit_test@university.edu"

    for i in range(1, 4):
        allowed, retry = limiter.record_attempt(email)
        assert allowed, f"Attempt {i} should be allowed"
        print(f"  [PASS] OTP request attempt {i}/3 allowed")

    allowed_4th, retry_4th = limiter.record_attempt(email)
    assert not allowed_4th, "4th attempt must be rate-limited!"
    assert retry_4th > 0, "retry_after seconds must be > 0"
    print(f"  [PASS] 4th request blocked cleanly (retry after {retry_4th}s)")


def test_brevo_email_service():
    print(f"\n{'='*65}")
    print("  3. TEST — Brevo Email Service & Welcome Copy")
    print(f"{'='*65}")

    # 3.1 Graceful failure when missing keys
    with patch.dict(os.environ, {"BREVO_API_KEY": "", "BREVO_SENDER_EMAIL": ""}):
        ok, err = send_otp_email("test@example.com", "123456")
        assert not ok, "Expected failure when BREVO keys missing"
        assert "configuration missing" in err.lower(), f"Expected missing config msg, got: {err}"
        print("  [PASS] Missing BREVO keys failed gracefully without exception")

    # 3.2 Mocked Brevo API success calls
    with patch.dict(os.environ, {"BREVO_API_KEY": "fake_key", "BREVO_SENDER_EMAIL": "sender@uqms.edu"}), \
         patch("requests.post") as mock_post:

        mock_resp = MagicMock()
        mock_resp.status_code = 201
        mock_resp.json.return_value = {"messageId": "msg_12345"}
        mock_post.return_value = mock_resp

        # Send OTP email
        ok_otp, msg_otp = send_otp_email("student@university.edu", "654321")
        assert ok_otp, f"send_otp_email failed: {msg_otp}"
        otp_json = mock_post.call_args[1]["json"]
        assert "654321" in otp_json["subject"]
        print("  [PASS] send_otp_email payload formatted & dispatched correctly")

        # Send Admin Welcome email
        ok_admin, msg_admin = send_welcome_email("admin@university.edu", "Alice Admin", role="admin")
        assert ok_admin, f"send_welcome_email admin failed: {msg_admin}"
        admin_json = mock_post.call_args[1]["json"]
        assert admin_json["subject"] == "Welcome to UQMS, Alice Admin!"
        assert "Welcome to UQMS, Alice Admin!" in admin_json["htmlContent"]
        assert "Team UQMS" in admin_json["htmlContent"]
        print("  [PASS] Admin Welcome Email exact copy & subject verified")

        # Send Student Welcome email
        ok_stud, msg_stud = send_welcome_email("student@university.edu", "Jane Student", role="student")
        assert ok_stud, f"send_welcome_email student failed: {msg_stud}"
        stud_json = mock_post.call_args[1]["json"]
        assert stud_json["subject"] == "Welcome to UQMS, Jane Student!"
        assert "Your easier campus experience starts here." in stud_json["htmlContent"]
        assert "Team UQMS" in stud_json["htmlContent"]
        print("  [PASS] Student Welcome Email exact copy & subject verified")


def test_zero_db_bloat():
    print(f"\n{'='*65}")
    print("  4. TEST — Zero DB Bloat for Unverified Registrations")
    print(f"{'='*65}")

    db = SessionLocal()
    try:
        initial_users = db.query(User).count()

        # Simulate requesting OTP
        dummy_email = "unverified_test@university.edu"
        otp_service.generate_otp(dummy_email, pending_data={"name": "Ghost", "password": "pass"})

        users_after_otp = db.query(User).count()
        assert users_after_otp == initial_users, "No User row should be created during OTP generation!"
        print(f"  [PASS] User DB count unchanged ({initial_users}) prior to OTP verification")

        otp_service.clear(dummy_email)
    finally:
        db.close()


def run():
    test_otp_service()
    test_otp_rate_limiter()
    test_brevo_email_service()
    test_zero_db_bloat()

    print(f"\n{'='*65}")
    print("  ALL OTP & EMAIL TESTS PASSED SUCCESSFULLY!")
    print(f"{'='*65}\n")
    return True


if __name__ == "__main__":
    success = run()
    sys.exit(0 if success else 1)
