# services/onboarding.py
"""
services/onboarding.py — Modular Tenant Onboarding Service for UQMS.

Converts (College Name + Website URL) into a fully provisioned, white-labeled
tenant in seconds:
- Auto-extracts high-res official logo from Google's favicon service (free, zero-cost).
- Auto-generates clean URL slug.
- Provisions university tenant with 14-day free trial.
- Provisions university administrator account with secure temporary credentials.
- Dispatches welcome email via Brevo if configured.
- Fully isolated and modular.
"""

import re
import os
import secrets
from urllib.parse import urlparse
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session

from models.university import University
from models.user import User, UserRole
from services.auth_service import AuthService, _hash_password
from services.email_service import send_welcome_email
from utils.structured_logger import log_event


def slugify(text: str) -> str:
    """Generate a clean, lowercase URL-safe slug from text."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text)
    return text.strip("-")


def extract_domain(website_url: str) -> str:
    """Extract clean hostname/domain from website URL."""
    url = website_url.strip()
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    parsed = urlparse(url)
    domain = parsed.netloc or parsed.path
    if domain.startswith("www."):
        domain = domain[4:]
    return domain.split("/")[0].strip()


def auto_fetch_logo(website_url: str) -> str:
    """
    Generate high-resolution official logo URL using Google Favicon API.
    Zero-cost, fast, and does not require third-party paid API keys.
    """
    domain = extract_domain(website_url)
    return f"https://t3.gstatic.com/faviconV2?client=SOCIAL&type=FAV&fallback_opts=TYPE,SIZE,URL&url=https://{domain}&size=128"


def create_tenant_with_trial(
    db: Session,
    name: str,
    website: str,
    admin_email: str,
    admin_name: Optional[str] = None,
    departments: Optional[List[str]] = None,
    trial_days: int = 14,
    base_portal_url: str = "https://uqms-portal.duckdns.org",
) -> Dict[str, Any]:
    """
    End-to-end automated tenant provisioning.

    1. Creates University tenant with logo and 14-day free trial.
    2. Provisions Admin user with temporary password.
    3. Returns full onboarding summary for instant WhatsApp/Email dispatch.
    """
    clean_name = name.strip()
    slug = slugify(clean_name)
    logo = auto_fetch_logo(website)
    clean_email = admin_email.strip().lower()
    clean_admin_name = (admin_name or f"{clean_name} Admin").strip()
    dept_list = departments or ["Admissions", "Fees & Accounts", "Academics", "Hostel", "Placement"]

    # 1. Check if University or Slug already exists
    existing_uni = db.query(University).filter(
        (University.name == clean_name) | (University.slug == slug)
    ).first()

    now = datetime.now(timezone.utc)
    trial_end = now + timedelta(days=trial_days)

    if existing_uni:
        uni = existing_uni
        # Update logo or trial if missing
        if not uni.logo_url:
            uni.logo_url = logo
        if not uni.subscription_expires_at:
            uni.subscription_status = "trial"
            uni.trial_ends_at = trial_end
            uni.subscription_expires_at = trial_end
        db.commit()
        is_new = False
    else:
        uni = University(
            name=clean_name,
            slug=slug,
            logo_url=logo,
            status="approved",
            subscription_status="trial",
            subscription_plan="14-Day Free Trial",
            trial_ends_at=trial_end,
            subscription_expires_at=trial_end,
        )
        uni.departments = dept_list
        db.add(uni)
        db.commit()
        db.refresh(uni)
        is_new = True

    # 2. Provision Admin User
    existing_user = db.query(User).filter(User.email == clean_email).first()
    temp_password = None

    if existing_user:
        admin_user = existing_user
    else:
        temp_password = secrets.token_urlsafe(10)
        password_hash = _hash_password(temp_password)
        admin_user = User(
            university_id=uni.id,
            name=clean_admin_name,
            email=clean_email,
            password_hash=password_hash,
            role=UserRole.admin,
        )
        db.add(admin_user)
        db.commit()
        db.refresh(admin_user)

        # Optional welcome email dispatch via Brevo (fails silently if unconfigured)
        try:
            send_welcome_email(clean_email, clean_admin_name, uni.name)
        except Exception:
            pass

    log_event(
        event_name="tenant_onboarded",
        details={
            "university_id": uni.id,
            "slug": uni.slug,
            "is_new": is_new,
            "admin_email": clean_email,
        },
    )

    public_test_url = f"{base_portal_url}?uni={uni.slug}"

    return {
        "success": True,
        "is_new": is_new,
        "university_id": uni.id,
        "name": uni.name,
        "slug": uni.slug,
        "logo_url": uni.logo_url,
        "trial_ends_at": trial_end.strftime("%Y-%m-%d"),
        "admin_email": clean_email,
        "admin_name": clean_admin_name,
        "temp_password": temp_password,
        "public_test_url": public_test_url,
        "admin_login_url": base_portal_url,
    }
