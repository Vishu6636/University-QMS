# services/auth_service.py
"""
AuthService — user registration, login, and session helpers.

All operations are scoped to university_id for multi-tenant isolation.
Passwords are hashed with bcrypt (falls back to SHA-256 if bcrypt is unavailable).
"""

import hashlib
import logging
from typing import Optional

from sqlalchemy.orm import Session

from models.user import User, UserRole
from models.university import University

log = logging.getLogger(__name__)


def _hash_password(password: str) -> str:
    """
    Hash a password.
    Uses bcrypt when available; falls back to SHA-256 for environments
    where bcrypt cannot be compiled (e.g. some Windows setups without
    the MSVC toolchain).  Replace with bcrypt-only in production.
    """
    try:
        import bcrypt  # type: ignore
        return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    except ImportError:
        log.warning("bcrypt not available — using SHA-256 (not suitable for production).")
        return hashlib.sha256(password.encode()).hexdigest()


def _verify_password(password: str, password_hash: str) -> bool:
    """Verify a plain-text password against a stored hash."""
    try:
        import bcrypt  # type: ignore
        return bcrypt.checkpw(password.encode(), password_hash.encode())
    except ImportError:
        return hashlib.sha256(password.encode()).hexdigest() == password_hash


class AuthService:
    """Handles user registration and authentication scoped to a university."""

    def __init__(self, db: Session) -> None:
        self.db = db

    # ── Registration ───────────────────────────────────────────────────────────

    def register_user(
        self,
        *,
        university_id: int,
        name: str,
        email: str,
        password: str,
        role: UserRole = UserRole.student,
        department: Optional[str] = None,
    ) -> User:
        """
        Create a new user.

        Raises:
            ValueError: if a user with the same email already exists in this university.
        """
        existing = (
            self.db.query(User)
            .filter(User.university_id == university_id, User.email == email)
            .first()
        )
        if existing:
            raise ValueError(f"Email '{email}' is already registered in this university.")

        user = User(
            university_id=university_id,
            name=name,
            email=email,
            password_hash=_hash_password(password),
            role=role,
            department=department,
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        log.info("Registered user id=%s email=%s role=%s", user.id, email, role)
        return user

    # ── Authentication ─────────────────────────────────────────────────────────

    def authenticate(
        self, *, university_id: int, email: str, password: str
    ) -> Optional[User]:
        """
        Verify credentials and return the User on success, or None on failure.

        Deliberately does NOT raise on failure to avoid leaking information.
        """
        user = (
            self.db.query(User)
            .filter(User.university_id == university_id, User.email == email)
            .first()
        )
        if user and _verify_password(password, user.password_hash):
            return user
        return None

    # ── Lookups ────────────────────────────────────────────────────────────────

    def get_user_by_id(self, user_id: int, university_id: int) -> Optional[User]:
        """Fetch a user, ensuring it belongs to the expected university."""
        return (
            self.db.query(User)
            .filter(User.id == user_id, User.university_id == university_id)
            .first()
        )

    def list_users(self, university_id: int) -> list[User]:
        """Return all users for a university (admin use)."""
        return (
            self.db.query(User)
            .filter(User.university_id == university_id)
            .order_by(User.name)
            .all()
        )

    # ── University helpers ─────────────────────────────────────────────────────

    @staticmethod
    def list_universities(db: Session) -> list[University]:
        """Return all universities (used at the login/landing page)."""
        return db.query(University).order_by(University.name).all()

    @staticmethod
    def get_university_by_slug(db: Session, slug: str) -> Optional[University]:
        return db.query(University).filter(University.slug == slug).first()
