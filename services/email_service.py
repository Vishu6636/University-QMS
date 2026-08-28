# services/email_service.py
"""
Transactional email service using Brevo (formerly Sendinblue) REST API.

Provides:
  • send_otp_email(to_email, otp_code, purpose)
  • send_welcome_email(to_email, name, role)
"""

import os
import logging
import requests
from typing import Tuple
from dotenv import load_dotenv

load_dotenv()

log = logging.getLogger(__name__)

BREVO_API_URL = "https://api.brevo.com/v3/smtp/email"
PRIMARY_COLOR = "#4F46E5"


def _get_brevo_config() -> Tuple[str | None, str | None]:
    api_key = os.getenv("BREVO_API_KEY")
    sender_email = os.getenv("BREVO_SENDER_EMAIL")
    if not api_key or not sender_email:
        load_dotenv()
        api_key = os.getenv("BREVO_API_KEY")
        sender_email = os.getenv("BREVO_SENDER_EMAIL")
    return api_key, sender_email


def _build_html_template(title: str, content_html: str) -> str:
    """Wrap content in a clean, minimal inline-CSS HTML email container."""
    return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
</head>
<body style="margin:0; padding:0; background-color:#F4F4F5; font-family:-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color:#18181B;">
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background-color:#F4F4F5; padding: 30px 10px;">
        <tr>
            <td align="center">
                <table role="presentation" width="100%" style="max-width:560px; background-color:#FFFFFF; border-radius:12px; overflow:hidden; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);">
                    <!-- Header -->
                    <tr>
                        <td style="background-color:{PRIMARY_COLOR}; padding: 24px; text-align: center;">
                            <h1 style="color:#FFFFFF; margin:0; font-size: 22px; font-weight: 700; letter-spacing: 0.5px;">UQMS</h1>
                            <p style="color:#E0E7FF; margin: 4px 0 0 0; font-size: 13px;">University Query Management System</p>
                        </td>
                    </tr>
                    <!-- Body Content -->
                    <tr>
                        <td style="padding: 32px 28px; line-height: 1.6; font-size: 15px; color: #27272A;">
                            {content_html}
                        </td>
                    </tr>
                    <!-- Footer -->
                    <tr>
                        <td style="background-color:#FAFAFA; padding: 16px 28px; border-top: 1px solid #E4E4E7; text-align: center; font-size: 12px; color: #71717A;">
                            &copy; 2026 UQMS Platform &bull; Automated Account Notification
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>
"""


def _send_brevo_email(to_email: str, recipient_name: str | None, subject: str, html_content: str) -> Tuple[bool, str]:
    api_key, sender_email = _get_brevo_config()

    if not api_key or not sender_email:
        err_msg = "Brevo configuration missing: BREVO_API_KEY and BREVO_SENDER_EMAIL must be set in environment."
        log.error(err_msg)
        return False, err_msg

    headers = {
        "accept": "application/json",
        "api-key": api_key.strip(),
        "content-type": "application/json",
    }

    payload = {
        "sender": {
            "name": "UQMS System",
            "email": sender_email.strip(),
        },
        "to": [
            {
                "email": to_email.strip(),
                "name": recipient_name.strip() if recipient_name else to_email.strip(),
            }
        ],
        "subject": subject,
        "htmlContent": html_content,
    }

    try:
        response = requests.post(BREVO_API_URL, json=payload, headers=headers, timeout=10)
        if response.status_code in (200, 201):
            log.info("Brevo email sent successfully to %s. Subject: %s", to_email, subject)
            return True, "Email sent successfully."
        else:
            err = f"Brevo API error ({response.status_code}): {response.text}"
            log.error("Failed to send Brevo email to %s: %s", to_email, err)
            return False, err
    except Exception as e:
        err = f"Exception sending email via Brevo to {to_email}: {e}"
        log.exception(err)
        return False, err


def send_otp_email(to_email: str, otp_code: str, purpose: str = "registration") -> Tuple[bool, str]:
    """
    Send a 6-digit numeric OTP code to the recipient via Brevo API.
    """
    subject = f"Your UQMS Verification Code: {otp_code}"

    content = f"""
        <h2 style="margin-top:0; color:#18181B; font-size:18px;">Email Verification Required</h2>
        <p>Please use the following 6-digit One-Time Password (OTP) to complete your UQMS account registration:</p>
        <div style="text-align: center; margin: 28px 0;">
            <span style="display: inline-block; background-color:#F4F4F5; border: 1px solid #E4E4E7; border-radius: 8px; padding: 12px 24px; font-family: monospace; font-size: 28px; font-weight: 700; letter-spacing: 6px; color: {PRIMARY_COLOR};">
                {otp_code}
            </span>
        </div>
        <p style="font-size:13px; color:#71717A;">
            <strong>Note:</strong> This verification code will expire in <strong>5 minutes</strong>.
            If you did not request this registration, please ignore this email.
        </p>
    """

    html = _build_html_template("UQMS Verification Code", content)
    return _send_brevo_email(to_email, recipient_name=None, subject=subject, html_content=html)


def send_welcome_email(to_email: str, name: str, role: str) -> Tuple[bool, str]:
    """
    Send a branded welcome email to newly verified users (admin or student).
    Uses exact required copy.
    """
    role = (role or "").strip().lower()
    clean_name = name.strip() if name else "User"

    if role == "admin":
        subject = f"Welcome to UQMS, {clean_name}!"
        body_html = f"""
            <h2 style="margin-top:0; color:#18181B; font-size:18px;">Welcome to UQMS, {clean_name}!</h2>
            <p>Thank you for choosing UQMS for your institution.</p>
            <p>Your account is successfully registered. UQMS is designed to make administration, record management, and query handling simpler and more organized.</p>
            <p>If you need any assistance, our support is always here to help.</p>
            <p>Let UQMS make your everyday work easier.</p>
            <p style="margin-top:24px;">&mdash; <strong>Team UQMS</strong></p>
        """
    else:  # Student role
        subject = f"Welcome to UQMS, {clean_name}!"
        body_html = f"""
            <h2 style="margin-top:0; color:#18181B; font-size:18px;">Welcome to UQMS, {clean_name}!</h2>
            <p>Thank you for registering with UQMS.</p>
            <p>Your account is successfully created. You can now use UQMS to access important information, raise queries, and stay connected with your institution more easily.</p>
            <p>If you ever need help, our support team is here for you.</p>
            <p>Your easier campus experience starts here.</p>
            <p style="margin-top:24px;">&mdash; <strong>Team UQMS</strong></p>
        """

    html = _build_html_template(subject, body_html)
    return _send_brevo_email(to_email, recipient_name=clean_name, subject=subject, html_content=html)


def send_complaint_notification_email(
    to_email: str,
    submitted_by_name: str,
    submitted_by_email: str,
    university_name: str,
    subject_text: str,
    message_text: str,
) -> Tuple[bool, str]:
    """
    Send a notification email to the platform owner when an admin/super_admin raises a complaint.
    """
    subject = f"[Platform Complaint] {subject_text}"
    body_html = f"""
        <h2 style="margin-top:0; color:#DC2626; font-size:18px;">New Platform Complaint Submitted</h2>
        <p>A new platform complaint has been submitted by an administrator.</p>
        <div style="background-color:#F4F4F5; border-left:4px solid #DC2626; padding:16px; margin:16px 0; border-radius:4px;">
            <p style="margin:0 0 6px 0;"><strong>Institution:</strong> {university_name}</p>
            <p style="margin:0 0 6px 0;"><strong>Raised By:</strong> {submitted_by_name} ({submitted_by_email})</p>
            <p style="margin:0 0 6px 0;"><strong>Subject:</strong> {subject_text}</p>
        </div>
        <h3 style="font-size:15px; color:#18181B; margin:16px 0 8px 0;">Message / Details:</h3>
        <p style="white-space: pre-wrap; background-color:#FAFAFA; border:1px solid #E4E4E7; padding:12px; border-radius:6px; font-size:14px;">{message_text}</p>
        <p style="font-size:13px; color:#71717A; margin-top:20px;">
            Log into the <strong>Super Admin Console</strong> to manage and resolve this complaint.
        </p>
    """
    html = _build_html_template(subject, body_html)
    return _send_brevo_email(to_email, recipient_name="Platform Owner", subject=subject, html_content=html)
