# services/billing.py
"""
services/billing.py — Modular SaaS Billing & Subscription Service for UQMS.

Features:
- Free-tier / zero-cost compatible.
- Environment variable configuration (never hardcoded).
- 2-day grace period to prevent false lockouts during UPI Autopay retries.
- Razorpay Payment Links (manual renewal) and Subscriptions (UPI AutoPay).
- Explicit HMAC-SHA256 signature verification for webhooks.
- Calm, Notion/Linear style display metadata.
- Fully isolated and decoupled from existing core logic.
"""

import os
import hmac
import hashlib
import json
import base64
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, Tuple
from sqlalchemy.orm import Session
from models.university import University

# ── Grace Period Configuration ────────────────────────────────────────────────
# 2-day buffer after expiry for bank/UPI retry settlement before locking service
GRACE_PERIOD_DAYS = 2

# ── Pricing Plans ─────────────────────────────────────────────────────────────
DEFAULT_STARTER_PRICE_INR = 4999
DEFAULT_PLAN_NAME = "Starter Plan"
_MANAGED_PLAN_NOTE = "uqms_starter_monthly"


def get_razorpay_credentials() -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """Retrieve Razorpay keys strictly from environment variables."""
    key_id = (os.getenv("RAZORPAY_KEY_ID") or "").strip() or None
    key_secret = (os.getenv("RAZORPAY_KEY_SECRET") or "").strip() or None
    webhook_secret = (os.getenv("RAZORPAY_WEBHOOK_SECRET") or "").strip() or None
    return key_id, key_secret, webhook_secret


def coerce_notes_dict(value: Any) -> Dict[str, Any]:
    """Razorpay sometimes returns notes as {}, sometimes as []."""
    if isinstance(value, dict):
        return value
    if isinstance(value, list):
        merged: Dict[str, Any] = {}
        for entry in value:
            if isinstance(entry, dict):
                merged.update(entry)
        return merged
    return {}


def _plan_item_dict(plan: Dict[str, Any]) -> Dict[str, Any]:
    item = plan.get("item", {})
    if isinstance(item, list):
        item = next((entry for entry in item if isinstance(entry, dict)), {})
    return item if isinstance(item, dict) else {}


def _razorpay_error_message(resp: Any, fallback: str) -> str:
    if not isinstance(resp, dict):
        return fallback
    err = resp.get("error")
    if isinstance(err, dict):
        return err.get("description") or err.get("reason") or fallback
    if isinstance(err, list) and err:
        first = err[0]
        if isinstance(first, dict):
            return first.get("description") or first.get("reason") or fallback
        return str(first)
    if isinstance(err, str) and err.strip():
        return err
    return fallback


# ── Entitlement & Status Checking ─────────────────────────────────────────────

def is_subscription_active(university: University) -> bool:
    """
    Check if a university's AI queries and admin access are entitled.
    Returns True if:
    1. Active or Trial and before subscription_expires_at, OR
    2. Within the 2-day grace period buffer after subscription_expires_at.
    """
    if not university:
        return False

    now = datetime.now(timezone.utc)
    expires_at = university.subscription_expires_at or university.trial_ends_at

    # If no date is set, allow default trial window
    if not expires_at:
        return True

    # Ensure timezone awareness
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    cutoff_with_grace = expires_at + timedelta(days=GRACE_PERIOD_DAYS)
    return now <= cutoff_with_grace


def get_subscription_summary(university: University) -> Dict[str, Any]:
    """
    Return calm, Linear/Notion-style metadata for rendering the billing tab.
    Urgency is subtle:
    - 'normal': > 3 days left
    - 'amber': <= 3 days left (subtle warning)
    - 'grace': within 48h after expiry (renewal processing)
    - 'expired': after grace period (calm paused state)
    """
    now = datetime.now(timezone.utc)
    raw_status = (university.subscription_status or "trial").lower()
    plan_name = university.subscription_plan or "14-Day Free Trial"
    expires_at = university.subscription_expires_at or university.trial_ends_at

    if not expires_at:
        expires_at = now + timedelta(days=14)
    elif expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    days_left = (expires_at.date() - now.date()).days
    grace_cutoff = expires_at + timedelta(days=GRACE_PERIOD_DAYS)

    if now > grace_cutoff:
        status_label = "Paused"
        urgency = "expired"
        badge_style = "color: #71717A; background: #F4F4F5; border: 1px solid #E4E4E7;"
        headline = "Subscription paused"
        subtext = f"Plan expired on {expires_at.strftime('%d %b %Y')}. Renew to restore AI queries."
    elif now > expires_at:
        status_label = "Grace Period"
        urgency = "grace"
        badge_style = "color: #D97706; background: #FEF3C7; border: 1px solid #FDE68A;"
        headline = "Renewal in progress"
        subtext = f"Services remain fully active. Grace period ends {grace_cutoff.strftime('%d %b %Y')}."
    elif days_left <= 3:
        status_label = "Trial Expiring Soon" if "trial" in raw_status else "Renewing Soon"
        urgency = "amber"
        badge_style = "color: #D97706; background: #FFFBEB; border: 1px solid #FDE68A;"
        headline = f"{days_left} day{'s' if days_left != 1 else ''} remaining"
        subtext = f"Valid through {expires_at.strftime('%d %b %Y')}."
    else:
        status_label = "Active Trial" if "trial" in raw_status else "Active"
        urgency = "normal"
        badge_style = "color: #10B981; background: #ECFDF5; border: 1px solid #A7F3D0;"
        headline = "Subscription active"
        subtext = f"Renews on {expires_at.strftime('%d %b %Y')}."

    return {
        "plan_name": plan_name,
        "status_label": status_label,
        "raw_status": raw_status,
        "urgency": urgency,
        "days_left": max(0, days_left),
        "expires_at": expires_at,
        "expires_at_formatted": expires_at.strftime("%B %d, %Y"),
        "badge_style": badge_style,
        "headline": headline,
        "subtext": subtext,
        "has_autopay": bool(university.razorpay_subscription_id),
    }


# ── Razorpay API Integration (Zero-Cost REST Client) ─────────────────────────

def _razorpay_request(method: str, endpoint: str, data: Optional[Dict] = None) -> Tuple[bool, Dict[str, Any]]:
    """
    Execute authenticated HTTP request to Razorpay API without heavy dependencies.
    Uses standard library urllib or requests.
    """
    import urllib.request
    import urllib.error

    key_id, key_secret, _ = get_razorpay_credentials()
    if not key_id or not key_secret:
        return False, {"error": "Razorpay credentials not configured. Please set RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET in .env."}

    url = f"https://api.razorpay.com/v1/{endpoint.lstrip('/')}"
    auth_str = f"{key_id}:{key_secret}"
    auth_header = f"Basic {base64.b64encode(auth_str.encode()).decode()}"

    headers = {
        "Authorization": auth_header,
        "Content-Type": "application/json",
    }

    body = json.dumps(data).encode("utf-8") if data else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            resp_body = resp.read().decode("utf-8")
            return True, json.loads(resp_body)
    except urllib.error.HTTPError as e:
        err_msg = e.read().decode("utf-8")
        try:
            return False, json.loads(err_msg)
        except Exception:
            return False, {"error": err_msg}
    except Exception as e:
        return False, {"error": str(e)}


def create_payment_link(
    university: University,
    admin_email: Optional[str] = None,
    amount_in_inr: int = DEFAULT_STARTER_PRICE_INR,
    callback_url: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Generate a Razorpay Payment Link for manual renewal (Option 1).
    Admin clicks -> Pays via UPI/Card/Netbanking -> Redirects back.
    """
    key_id, _, _ = get_razorpay_credentials()
    if not key_id:
        # Fallback simulation link for sandbox / development
        return {
            "success": True,
            "simulated": True,
            "payment_url": None,
            "id": f"plink_sim_{university.id}_{int(datetime.now().timestamp())}",
            "message": "Development mode: Razorpay keys not set. Running in simulation mode.",
        }

    payload = {
        "amount": amount_in_inr * 100,  # Razorpay expects paise
        "currency": "INR",
        "accept_partial": False,
        "description": f"UQMS AI Helpdesk Renewal - {university.name}",
        "customer": {
            "name": university.name,
            "email": admin_email or f"admin@{university.slug}.edu",
        },
        "notify": {"sms": False, "email": True},
        "reminder_enable": True,
        "notes": {
            "university_id": str(university.id),
            "university_slug": university.slug,
            "plan_type": "starter_monthly",
        },
    }
    if callback_url:
        payload["callback_url"] = callback_url
        payload["callback_method"] = "get"

    success, resp = _razorpay_request("POST", "payment_links", payload)
    if success:
        return {
            "success": True,
            "payment_url": resp.get("short_url"),
            "id": resp.get("id"),
        }
    return {
        "success": False,
        "error": _razorpay_error_message(resp, "Failed to create payment link"),
    }


def create_autopay_subscription(
    university: University,
    plan_id: Optional[str] = None,
    customer_email: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Create a recurring subscription mandate (Option 2: UPI AutoPay / Recurring).
    Requires a pre-created plan_id from Razorpay Dashboard or environment.
    """
    key_id, _, _ = get_razorpay_credentials()
    resolved_plan_id = plan_id or (os.getenv("RAZORPAY_STARTER_PLAN_ID") or "").strip() or None

    if not key_id:
        return {
            "success": True,
            "simulated": True,
            "subscription_url": None,
            "id": f"sub_sim_{university.id}",
            "message": "Development mode: Razorpay keys are not configured.",
        }

    # A subscription always needs a Razorpay Plan.  Previously, a missing plan
    # ID produced a local simulation link even when live keys were configured,
    # which made the AutoPay button appear broken.  Reuse a configured plan or
    # create one once on the Razorpay account when the button is first used.
    if not resolved_plan_id:
        resolved_plan_id = _get_or_create_starter_plan()
        if not resolved_plan_id:
            return {
                "success": False,
                "error": "Could not prepare the monthly Razorpay subscription plan. Please check that Subscriptions are enabled for this Razorpay account and try again.",
            }

    payload = {
        "plan_id": resolved_plan_id,
        "total_count": 12,  # 12 monthly cycles (1 year)
        "quantity": 1,
        "customer_notify": 1,
        "notes": {
            "university_id": str(university.id),
            "university_slug": university.slug,
        },
    }

    success, resp = _razorpay_request("POST", "subscriptions", payload)
    if success:
        subscription_url = resp.get("short_url")
        if not subscription_url:
            return {
                "success": False,
                "error": "Razorpay created the subscription but did not return an authorization link. Please confirm that Razorpay Subscriptions are enabled for this account.",
            }
        return {
            "success": True,
            "subscription_id": resp.get("id"),
            "subscription_url": subscription_url,
        }
    return {
        "success": False,
        "error": _razorpay_error_message(resp, "Failed to create subscription mandate"),
    }


def _is_starter_plan(plan: Dict[str, Any]) -> bool:
    item = _plan_item_dict(plan)
    if (
        plan.get("period") != "monthly"
        or plan.get("interval") != 1
        or item.get("amount") != DEFAULT_STARTER_PRICE_INR * 100
        or item.get("currency") != "INR"
    ):
        return False
    notes = coerce_notes_dict(plan.get("notes"))
    if notes.get("managed_by") == _MANAGED_PLAN_NOTE:
        return True
    # Razorpay stores empty notes as [], so also reuse the shared Starter plan by name.
    return item.get("name") == DEFAULT_PLAN_NAME


def _get_or_create_starter_plan() -> Optional[str]:
    """Return the shared UQMS monthly plan, creating it only when necessary."""
    success, response = _razorpay_request("GET", "plans?count=100")
    if not success or not isinstance(response, dict):
        return None

    for plan in response.get("items", []) or []:
        if isinstance(plan, dict) and _is_starter_plan(plan):
            return plan.get("id")

    payload = {
        "period": "monthly",
        "interval": 1,
        "item": {
            "name": DEFAULT_PLAN_NAME,
            "amount": DEFAULT_STARTER_PRICE_INR * 100,
            "currency": "INR",
            "description": "UQMS Starter Plan monthly subscription",
        },
        "notes": {"managed_by": _MANAGED_PLAN_NOTE},
    }
    success, response = _razorpay_request("POST", "plans", payload)
    if success and isinstance(response, dict):
        return response.get("id")
    return None


# ── Webhook Signature Verification ────────────────────────────────────────────

def verify_webhook_signature(raw_body: bytes, signature: str) -> bool:
    """
    Explicitly verify Razorpay HMAC-SHA256 signature from 'X-Razorpay-Signature' header.
    Prevents forged webhook events.
    """
    _, _, webhook_secret = get_razorpay_credentials()
    if not webhook_secret or not signature:
        return False

    computed_signature = hmac.new(
        key=webhook_secret.encode("utf-8"),
        msg=raw_body,
        digestmod=hashlib.sha256,
    ).hexdigest()

    # Constant-time comparison to prevent timing attacks
    return hmac.compare_digest(computed_signature, signature)


# ── Unified Subscription Extension ────────────────────────────────────────────

def extend_subscription(
    db: Session,
    university_id: int,
    days: int = 30,
    plan_name: str = "Starter Plan",
    payment_id: Optional[str] = None,
    subscription_id: Optional[str] = None,
) -> Optional[University]:
    """
    Unified renewal handler for BOTH manual renewal and recurring AutoPay.
    Extends subscription_expires_at by +30 days and sets subscription_status = 'active'.
    """
    university = db.query(University).filter(University.id == university_id).first()
    if not university:
        return None

    now = datetime.now(timezone.utc)
    current_expiry = university.subscription_expires_at

    # If current expiry is in the future, extend from current expiry.
    # Otherwise, extend from today.
    if current_expiry and current_expiry.replace(tzinfo=timezone.utc) > now:
        new_expiry = current_expiry.replace(tzinfo=timezone.utc) + timedelta(days=days)
    else:
        new_expiry = now + timedelta(days=days)

    university.subscription_status = "active"
    university.subscription_plan = plan_name
    university.subscription_expires_at = new_expiry
    if subscription_id:
        university.razorpay_subscription_id = subscription_id

    db.commit()
    db.refresh(university)
    return university
