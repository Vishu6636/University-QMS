# services/onboarding.py
"""
services/onboarding.py — Modular Tenant Onboarding Service for UQMS.

Converts (College Name + Website URL) into a fully provisioned, white-labeled
tenant in seconds:
- Auto-extracts real logo from the institution's own website (apple-touch-icon,
  og:image, largest <link rel="icon">, then /favicon.ico). Falls back to None
  so a clean text/initials placeholder is shown instead of a generic globe.
- Auto-generates clean URL slug.
- Provisions university tenant with 14-day free trial.
- Provisions university administrator account with secure temporary credentials.
- Dispatches welcome email via Brevo if configured.
- Fully isolated and modular.
"""

import re
import os
import secrets
import logging
from urllib.parse import urlparse, urljoin
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session

from models.university import University
from models.user import User, UserRole
from services.auth_service import AuthService, _hash_password
from services.email_service import send_welcome_email
from utils.structured_logger import log_event

log = logging.getLogger(__name__)


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


# Known default-globe/placeholder image URLs returned by favicon services
_GLOBE_URL_FRAGMENTS = (
    "gstatic.com/faviconV2",
    "google.com/s2/favicons",
    "icons.duckduckgo.com",
    "favicongrabber.com",
)

_LOGO_DIRECTORY = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "app", "assets", "tenant_logos"
)
_LOGO_RELATIVE_DIRECTORY = os.path.join("app", "assets", "tenant_logos")


def _is_usable_logo(url: str) -> bool:
    """Reject known default-globe service URLs before downloading a candidate."""
    return not any(fragment in url for fragment in _GLOBE_URL_FRAGMENTS)


def _image_details(data: bytes) -> Optional[tuple[int, int, str]]:
    """Return dimensions and extension for supported raster image bytes."""
    if data.startswith(b"\x89PNG\r\n\x1a\n") and len(data) >= 24:
        return int.from_bytes(data[16:20], "big"), int.from_bytes(data[20:24], "big"), "png"

    if data.startswith(b"\xff\xd8"):
        offset = 2
        while offset + 9 < len(data):
            if data[offset] != 0xFF:
                offset += 1
                continue
            marker = data[offset + 1]
            offset += 2
            while marker == 0xFF and offset < len(data):
                marker = data[offset]
                offset += 1
            if marker in (0xD8, 0xD9):
                continue
            if offset + 2 > len(data):
                break
            length = int.from_bytes(data[offset:offset + 2], "big")
            if marker in range(0xC0, 0xC4) or marker in range(0xC5, 0xC8) or marker in range(0xC9, 0xCC):
                return int.from_bytes(data[offset + 5:offset + 7], "big"), int.from_bytes(data[offset + 3:offset + 5], "big"), "jpg"
            offset += length

    if data.startswith(b"RIFF") and data[8:12] == b"WEBP" and len(data) >= 30:
        chunk = data[12:16]
        if chunk == b"VP8X":
            return (
                int.from_bytes(data[24:27], "little") + 1,
                int.from_bytes(data[27:30], "little") + 1,
                "webp",
            )
    return None


def _download_logo(candidate: str, storage_name: str) -> Optional[str]:
    """Download, dimension-check, and persist a candidate logo exactly once."""
    import requests
    try:
        response = requests.get(
            candidate, timeout=8, allow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        if response.status_code != 200 or len(response.content) > 5_000_000:
            return None
        image_details = _image_details(response.content)
        if not image_details:
            return None
        width, height, extension = image_details
        if min(width, height) < 64:
            return None

        os.makedirs(_LOGO_DIRECTORY, exist_ok=True)
        filename = f"{storage_name}.{extension}"
        with open(os.path.join(_LOGO_DIRECTORY, filename), "wb") as logo_file:
            logo_file.write(response.content)
        return os.path.join(_LOGO_RELATIVE_DIRECTORY, filename)
    except Exception as exc:
        log.debug("auto_fetch_logo: rejected %s - %s", candidate, exc)
        return None


def auto_fetch_logo(website_url: str, storage_key: Optional[str] = None) -> Optional[str]:
    """
    Fetch the institution's real logo by scraping its own website.

    Priority order:
      1. <link rel="apple-touch-icon"> (typically 180px, high quality)
      2. <meta property="og:image">     (usually a full-resolution banner/logo)
      3. Largest <link rel="icon">       (by sizes= attribute, e.g. 192x192)
      4. /favicon.ico                   (last resort; rejected if too small)

    Rejects:
      - Known default-globe service URLs
      - Images smaller than 64x64 pixels

    Returns None if nothing usable is found — callers should show a text/initials
    placeholder instead of a generic globe.
    """
    import requests
    from html.parser import HTMLParser

    if not website_url:
        return None

    url = website_url.strip()
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    base_url = url

    # --- Parse the homepage HTML for candidate URLs ---
    apple_touch: Optional[str] = None
    og_image: Optional[str] = None
    icon_candidates: List[tuple] = []  # (size_px, url)

    try:
        resp = requests.get(
            url, timeout=8, allow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0"}
        )
        base_url = resp.url  # follow redirects
        html = resp.text[:50_000]  # read only the <head> portion
    except Exception as exc:
        log.debug("auto_fetch_logo: could not fetch %s — %s", url, exc)
        return None

    class _HeadParser(HTMLParser):
        def handle_starttag(self, tag, attrs):
            a = dict(attrs)
            nonlocal apple_touch, og_image
            if tag == "link":
                rel = a.get("rel", "").lower()
                href = a.get("href", "")
                if not href:
                    return
                abs_href = urljoin(base_url, href)
                if "apple-touch-icon" in rel and apple_touch is None:
                    apple_touch = abs_href
                elif "icon" in rel:
                    sizes = a.get("sizes", "0x0")
                    try:
                        px = int(sizes.lower().split("x")[0])
                    except (ValueError, IndexError):
                        px = 0
                    icon_candidates.append((px, abs_href))
            elif tag == "meta":
                prop = a.get("property", "") or a.get("name", "")
                if prop.lower() == "og:image" and og_image is None:
                    og_image = a.get("content", "")
                    if og_image:
                        og_image = urljoin(base_url, og_image)

    _HeadParser().feed(html)

    # --- Try candidates in priority order ---
    candidates: List[str] = []
    if apple_touch:
        candidates.append(apple_touch)
    if og_image:
        candidates.append(og_image)
    # Add icons sorted largest first
    icon_candidates.sort(key=lambda t: t[0], reverse=True)
    candidates.extend(href for _, href in icon_candidates)
    # /favicon.ico as last resort
    parsed = urlparse(base_url)
    candidates.append(f"{parsed.scheme}://{parsed.netloc}/favicon.ico")

    storage_name = slugify(storage_key or extract_domain(base_url)) or "institution"
    for candidate in candidates:
        if _is_usable_logo(candidate):
            local_path = _download_logo(candidate, storage_name)
            if local_path:
                log.info("auto_fetch_logo: saved %s for %s", candidate, website_url)
                return local_path

    log.info("auto_fetch_logo: no usable logo found for %s", website_url)
    return None


def create_tenant_with_trial(
    db: Session,
    name: str,
    website: str,
    admin_email: str,
    admin_name: Optional[str] = None,
    departments: Optional[List[str]] = None,
    trial_days: int = 14,
    base_portal_url: str = "https://uqms-portal.duckdns.org",
    institution_type: str = "institution",
) -> Dict[str, Any]:
    """
    End-to-end automated tenant provisioning.

    1. Creates University tenant with logo and 14-day free trial.
    2. Provisions Admin user with temporary password.
    3. Returns full onboarding summary for instant WhatsApp/Email dispatch.
    """
    clean_name = name.strip()
    slug = slugify(clean_name)
    logo = auto_fetch_logo(website, slug)
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
        # Store website for reference
        if website and not uni.website_url:
            uni.website_url = website.strip()
        # Re-fetch logo if it's missing or is the old gstatic placeholder
        needs_logo_refresh = (
            not uni.logo_url
            or any(frag in (uni.logo_url or "") for frag in _GLOBE_URL_FRAGMENTS)
        )
        if needs_logo_refresh:
            fresh_logo = auto_fetch_logo(website, uni.slug)
            if fresh_logo:
                uni.logo_url = fresh_logo
        if institution_type and institution_type != "institution":
            uni.institution_type = institution_type
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
            website_url=website.strip() if website else None,
            institution_type=institution_type or "institution",
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
