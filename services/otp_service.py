# services/otp_service.py
"""
In-memory thread-safe OTP (One-Time Password) verification service.

Keyed by email (lowercase) with a 5-minute TTL.
Stores pending registration payload alongside the generated OTP code
so no unverified User row is created in SQLite.
"""

import time
import random
import threading
from typing import Dict, Any, Tuple


class OTPService:
    """Thread-safe in-memory store for OTPs and pending registration payloads."""

    def __init__(self, ttl_seconds: int = 300) -> None:
        self._ttl = ttl_seconds
        self._store: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()

    def generate_otp(self, email: str, pending_data: Dict[str, Any] | None = None) -> str:
        """
        Generate a 6-digit OTP code, store it with an expiry timestamp and optional payload.

        Returns:
            The generated 6-digit numeric OTP code string.
        """
        email_key = email.strip().lower()
        otp_code = f"{random.randint(100000, 999999)}"
        expires_at = time.time() + self._ttl

        with self._lock:
            # Clean up expired items opportunistically
            now = time.time()
            expired_keys = [k for k, v in self._store.items() if v.get("expires_at", 0) < now]
            for k in expired_keys:
                self._store.pop(k, None)

            self._store[email_key] = {
                "otp": otp_code,
                "expires_at": expires_at,
                "data": pending_data or {},
            }

        return otp_code

    def verify_otp(self, email: str, entered_otp: str) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Verify an entered OTP against the stored code for the email.

        Returns:
            (success: bool, message: str, payload: dict)
        """
        email_key = email.strip().lower()
        code = entered_otp.strip()
        now = time.time()

        with self._lock:
            record = self._store.get(email_key)
            if not record:
                return False, "No OTP request found for this email. Please request a new code.", {}

            if now > record["expires_at"]:
                self._store.pop(email_key, None)
                return False, "OTP code has expired. Please request a new verification code.", {}

            if record["otp"] != code:
                return False, "Invalid verification code. Please check and try again.", {}

            # Success: Pop record to prevent re-use
            payload = record.get("data", {})
            self._store.pop(email_key, None)
            return True, "Verification successful.", payload

    def clear(self, email: str) -> None:
        """Remove any pending OTP for email."""
        email_key = email.strip().lower()
        with self._lock:
            self._store.pop(email_key, None)


# Module-level singleton
otp_service = OTPService(ttl_seconds=300)
