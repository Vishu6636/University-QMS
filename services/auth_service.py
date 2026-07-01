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


class DuplicateEmailError(ValueError):
    """Raised when a registration is attempted with an email that already
    exists within the same university_id scope."""
    pass


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
        if password_hash.startswith("$2b$") or password_hash.startswith("$2a$") or password_hash.startswith("$2y$"):
            return bcrypt.checkpw(password.encode(), password_hash.encode())
        return hashlib.sha256(password.encode()).hexdigest() == password_hash
    except (ImportError, ValueError):
        return hashlib.sha256(password.encode()).hexdigest() == password_hash


def validate_password(password: str) -> None:
    """Enforce password policy: >= 8 characters, at least one digit.

    Raises:
        ValueError: if password does not meet the policy requirements.
    """
    if len(password) < 8:
        raise ValueError("Password must be at least 8 characters.")
    if not any(ch.isdigit() for ch in password):
        raise ValueError("Password must contain at least one number.")


class AuthService:
    """Handles user registration and authentication scoped to a university."""

    def __init__(self, db: Session) -> None:
        self.db = db

    # ── Registration ───────────────────────────────────────────────────────────

    def check_email_exists(self, university_id: Optional[int], email: str) -> bool:
        """Return True if a user with *email* already exists in this university scope.

        Email uniqueness is scoped per-university_id (multi-tenant isolation).
        Super-admin accounts (university_id=None) share a global scope.
        """
        return (
            self.db.query(User)
            .filter(User.university_id == university_id, User.email == email.strip().lower())
            .first()
        ) is not None

    def register_user(
        self,
        *,
        university_id: Optional[int] = None,
        name: str,
        email: str,
        password: str,
        role: UserRole = UserRole.student,
        department: Optional[str] = None,
    ) -> User:
        """
        Create a new user.

        Raises:
            DuplicateEmailError: if a user with the same email already exists
                                 within the same university_id scope.
        """
        validate_password(password)
        email = email.strip().lower()
        if self.check_email_exists(university_id, email):
            raise DuplicateEmailError(
                "This email is already registered. "
                "Please sign in instead, or use a different email."
            )

        user = User(
            university_id=university_id,
            name=name,
            email=email,
            password_hash=_hash_password(password),
            role=role,
            department=department,
        )
        try:
            self.db.add(user)
            self.db.commit()
            self.db.refresh(user)
        except Exception as e:
            self.db.rollback()
            log.exception("Failed to register user in SQLite: %s", e)
            raise
        log.info("Registered user id=%s email=%s role=%s", user.id, email, role)
        return user

    # ── Authentication ─────────────────────────────────────────────────────────

    def authenticate(
        self, *, university_id: Optional[int] = None, email: str, password: str
    ) -> Optional[User]:
        """
        Verify credentials and return the User on success, or None on failure.

        Deliberately does NOT raise on failure to avoid leaking information.
        """
        email = email.strip().lower()
        # First check if there is a super admin user with this email
        user = (
            self.db.query(User)
            .filter(User.role == UserRole.super_admin, User.email == email)
            .first()
        )
        if not user and university_id is not None:
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

    def update_user_credentials(
        self,
        user_id: int,
        *,
        current_password: str,
        new_email: str,
        new_password: Optional[str] = None,
    ) -> User:
        """
        Securely update a user's email and/or password.
        Validates current password. Enforces uniqueness constraint for new email.
        """
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            raise ValueError("User not found.")

        # Verify current password
        if not _verify_password(current_password, user.password_hash):
            raise ValueError("Incorrect current password.")

        new_email = new_email.strip().lower()
        if not new_email:
            raise ValueError("Email cannot be empty.")

        # If email changed, check uniqueness within scope
        if user.email.lower() != new_email:
            if user.role == UserRole.super_admin:
                # Super Admin emails must be unique globally among other super admins
                dup = (
                    self.db.query(User)
                    .filter(User.role == UserRole.super_admin, User.email == new_email, User.id != user_id)
                    .first()
                )
            else:
                # Scoped uniqueness to the same university
                dup = (
                    self.db.query(User)
                    .filter(User.university_id == user.university_id, User.email == new_email, User.id != user_id)
                    .first()
                )
            if dup:
                raise ValueError(f"Email '{new_email}' is already in use.")
            user.email = new_email

        # Update password if provided
        if new_password:
            validate_password(new_password)
            user.password_hash = _hash_password(new_password)

        try:
            self.db.commit()
            self.db.refresh(user)
        except Exception as e:
            self.db.rollback()
            log.exception("Failed to update user credentials in SQLite: %s", e)
            raise
        log.info("Updated credentials for user id=%s role=%s", user.id, user.role)
        return user

    # ── University helpers ─────────────────────────────────────────────────────

    @staticmethod
    def list_universities(db: Session) -> list[University]:
        """Return all universities (used at the login/landing page)."""
        return db.query(University).order_by(University.name).all()

    @staticmethod
    def get_university_by_slug(db: Session, slug: str) -> Optional[University]:
        return db.query(University).filter(University.slug == slug).first()
