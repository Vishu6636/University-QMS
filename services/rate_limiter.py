# services/rate_limiter.py
"""
In-memory sliding-window rate limiter.

Zero external dependencies.  Keyed by email (normalized to lowercase) because
Streamlit doesn't reliably expose client IP behind proxies.

Default policy: max 5 attempts per 10-minute window per email.
Counters reset automatically when the window expires.
State lives in-process and is lost on app restart — acceptable for a
single-process Streamlit deployment.
"""

import math
import threading
import time
from dataclasses import dataclass, field
from typing import Dict, List, Tuple


@dataclass
class _WindowConfig:
    max_attempts: int = 5
    window_seconds: int = 600  # 10 minutes


@dataclass
class _AttemptRecord:
    timestamps: List[float] = field(default_factory=list)


class RateLimiter:
    """Thread-safe, in-memory sliding-window rate limiter."""

    def __init__(
        self,
        max_attempts: int = 5,
        window_seconds: int = 600,
    ) -> None:
        self._config = _WindowConfig(
            max_attempts=max_attempts,
            window_seconds=window_seconds,
        )
        self._records: Dict[str, _AttemptRecord] = {}
        self._lock = threading.Lock()

    # ── Public API ─────────────────────────────────────────────────────────────

    def check(self, key: str) -> Tuple[bool, int]:
        """Check whether *key* is currently rate-limited.

        Returns:
            (allowed, retry_after_seconds)
            - allowed=True, retry_after=0  → request may proceed
            - allowed=False, retry_after=N → blocked, try again in N seconds
        """
        key = key.strip().lower()
        now = time.time()

        with self._lock:
            record = self._records.get(key)
            if record is None:
                return True, 0

            # Prune timestamps outside the current window
            cutoff = now - self._config.window_seconds
            record.timestamps = [t for t in record.timestamps if t > cutoff]

            if len(record.timestamps) < self._config.max_attempts:
                return True, 0

            # Blocked — compute when the oldest attempt in the window expires
            oldest = min(record.timestamps)
            retry_after = math.ceil((oldest + self._config.window_seconds) - now)
            return False, max(retry_after, 1)

    def record_attempt(self, key: str) -> Tuple[bool, int]:
        """Record an attempt for *key* and return the same tuple as check().

        Typical usage:
            allowed, retry_after = limiter.record_attempt(email)
            if not allowed:
                show_error(f"Too many attempts. Try again in {retry_after // 60} min …")
                return
        """
        key = key.strip().lower()
        now = time.time()

        with self._lock:
            record = self._records.setdefault(key, _AttemptRecord())

            # Prune old timestamps
            cutoff = now - self._config.window_seconds
            record.timestamps = [t for t in record.timestamps if t > cutoff]

            if len(record.timestamps) >= self._config.max_attempts:
                oldest = min(record.timestamps)
                retry_after = math.ceil((oldest + self._config.window_seconds) - now)
                return False, max(retry_after, 1)

            record.timestamps.append(now)
            return True, 0

    def reset(self, key: str) -> None:
        """Clear all recorded attempts for *key* (e.g. after a successful login)."""
        key = key.strip().lower()
        with self._lock:
            self._records.pop(key, None)


# ── Module-level singletons ────────────────────────────────────────────────────
# Shared across all Streamlit sessions within the same process.

login_limiter = RateLimiter(max_attempts=5, window_seconds=600)
registration_limiter = RateLimiter(max_attempts=5, window_seconds=600)
