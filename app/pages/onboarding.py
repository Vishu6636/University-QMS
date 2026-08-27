# app/pages/onboarding.py
"""
University onboarding with OTP email verification.
Creates:
  • a new University row  (name, slug, department_list)
  • a first admin User    (name, email, password_hash)
"""

import re
import json
import streamlit as st
from sqlalchemy.orm import Session

from models.university import University
from models.user import User, UserRole
from services.auth_service import AuthService, validate_password
from services.rate_limiter import registration_limiter, otp_limiter
from services.otp_service import otp_service
from services.email_service import send_otp_email, send_welcome_email


def _slugify(text: str) -> str:
    """Very simple slug: lowercase, replace spaces/special chars with hyphens."""
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")


def render(db: Session) -> None:
    st.markdown("<h2>Register Your University</h2>", unsafe_allow_html=True)
    st.markdown(
        "<p style='color:#6B6B6B; font-size:14px; margin-bottom: 1.5rem;'>"
        "Fill in the details below to register your university and create your first administrator account."
        "</p>",
        unsafe_allow_html=True,
    )

    current_step = st.session_state.get("onboarding_step", 1)

    # ── STEP 2: OTP VERIFICATION ─────────────────────────────────────────────
    if current_step == 2:
        onboarding_email = st.session_state.get("onboarding_email", "")
        st.markdown("<div class='uqms-card'>", unsafe_allow_html=True)
        st.markdown("<h3>Email Verification Required</h3>", unsafe_allow_html=True)
        st.info(
            f"A 6-digit verification code has been sent to **{onboarding_email}**.\n\n"
            f"Please enter the code below to complete your university registration."
        )

        with st.form("onboarding_otp_form"):
            otp_input = st.text_input(
                "6-Digit Verification Code",
                max_chars=6,
                placeholder="123456",
                key="onboarding_otp_input"
            )
            col_v1, col_v2 = st.columns([2, 1])
            with col_v1:
                submit_otp = st.form_submit_button("Verify OTP & Complete Registration", use_container_width=True)
            with col_v2:
                resend_otp = st.form_submit_button("Resend Code", use_container_width=True)

        if st.button("← Change Registration Info", key="btn_back_onboarding"):
            st.session_state.onboarding_step = 1
            st.rerun()

        st.markdown("</div>", unsafe_allow_html=True)

        if resend_otp:
            allowed, retry_after = otp_limiter.record_attempt(onboarding_email)
            if not allowed:
                minutes_left = max(1, retry_after // 60)
                st.error(
                    f"Too many OTP requests. Please wait {minutes_left} minute"
                    f"{'s' if minutes_left != 1 else ''} before requesting another code."
                )
            else:
                pending_data = st.session_state.get("onboarding_data", {})
                new_otp = otp_service.generate_otp(onboarding_email, pending_data)
                sent, send_err = send_otp_email(onboarding_email, new_otp, purpose="admin_registration")
                if sent:
                    st.success("A new verification code has been sent to your email.")
                else:
                    st.error(f"Failed to resend verification email: {send_err}")

        if submit_otp:
            if not otp_input or len(otp_input.strip()) != 6:
                st.error("Please enter a valid 6-digit numeric verification code.")
                return

            ok, msg, payload = otp_service.verify_otp(onboarding_email, otp_input)
            if not ok:
                st.error(msg)
                return

            # OTP verified — Persist University and Admin Account
            try:
                uni_name = payload["uni_name"]
                slug = payload["slug"]
                departments = payload["departments"]
                admin_name = payload["admin_name"]
                admin_email = payload["admin_email"]
                admin_pass = payload["admin_pass"]

                uni = University(
                    name=uni_name.strip(),
                    slug=slug,
                    department_list=json.dumps(departments),
                    status="pending",
                )
                db.add(uni)
                db.flush()

                auth_svc = AuthService(db)
                admin_user = auth_svc.register_user(
                    university_id=uni.id,
                    name=admin_name.strip(),
                    email=admin_email.strip(),
                    password=admin_pass,
                    role=UserRole.admin,
                    privacy_consent_given=True,
                )

                # Reset rate limiters
                registration_limiter.reset(admin_email)
                otp_limiter.reset(admin_email)

                # Send Branded Welcome Email
                send_welcome_email(admin_email, admin_name, role="admin")

                # Clear session onboarding state
                st.session_state.pop("onboarding_step", None)
                st.session_state.pop("onboarding_email", None)
                st.session_state.pop("onboarding_data", None)

                st.success(f"🎉 **{uni.name}** and admin account for **{admin_user.name}** verified successfully!")
                st.info(
                    "Your university registration is under review. "
                    "A confirmation welcome email has been sent to your inbox."
                )

            except Exception as e:
                db.rollback()
                st.error(f"Something went wrong creating the university account: {e}")
        return

    # ── STEP 1: INITIAL REGISTRATION FORM ────────────────────────────────────
    st.markdown("<div class='uqms-card'>", unsafe_allow_html=True)
    with st.form("onboarding_form"):
        st.markdown("<h4 style='margin-top:0;'>University Details</h4>", unsafe_allow_html=True)
        uni_name = st.text_input("University Name", placeholder="e.g. Greenfield University")
        dept_raw = st.text_input(
            "Departments (comma-separated)",
            placeholder="e.g. Computer Science, Law, MBA, Physics",
        )

        st.markdown("<hr style='border:0; border-top:1px solid #E5E5E5; margin: 1.5rem 0;'>", unsafe_allow_html=True)
        st.markdown("<h4 style='margin-top:0;'>Admin Account</h4>", unsafe_allow_html=True)
        admin_name = st.text_input("Your Full Name", placeholder="Alice Admin")
        admin_email = st.text_input("Admin Email", placeholder="admin@university.edu")
        admin_pass = st.text_input("Password", type="password", placeholder="••••••••")
        admin_pass2 = st.text_input("Confirm Password", type="password", placeholder="••••••••")
        onboarding_privacy = st.checkbox("I have read and agree to the Privacy Policy", value=False, key="onboarding_privacy")

        submitted = st.form_submit_button("Send Verification Code", use_container_width=True)
    st.markdown("</div>", unsafe_allow_html=True)

    if not submitted:
        return

    # ── Validation ────────────────────────────────────────────────────────────
    errors = []
    if not uni_name.strip():
        errors.append("University name is required.")
    if not admin_name.strip():
        errors.append("Admin name is required.")
    if not admin_email.strip():
        errors.append("Admin email is required.")
    elif "@" not in admin_email or "." not in admin_email.split("@")[-1]:
        errors.append("Invalid email address format.")
    try:
        validate_password(admin_pass)
    except ValueError as pw_err:
        errors.append(str(pw_err))
    if admin_pass != admin_pass2:
        errors.append("Passwords do not match.")
    if not onboarding_privacy:
        errors.append("You must agree to the Privacy Policy to register.")

    # Check slug uniqueness
    slug = _slugify(uni_name)
    existing_slug = db.query(University).filter(University.slug == slug).first()
    if existing_slug:
        errors.append(f"A university with slug '{slug}' already exists. Choose a different name.")

    if errors:
        for e in errors:
            st.error(f"{e}")
        return

    # ── Parse departments ─────────────────────────────────────────────────────
    departments = [d.strip() for d in dept_raw.split(",") if d.strip()]

    # ── Pre-check email existence in DB ──────────────────────────────────────
    auth_svc = AuthService(db)
    # Per-tenant email uniqueness is enforced when the new university is created in Step 2.

    # ── Rate limit check ──────────────────────────────────────────────────────
    allowed, retry_after = otp_limiter.record_attempt(admin_email)
    if not allowed:
        minutes_left = max(1, retry_after // 60)
        st.error(
            f"Too many verification requests for {admin_email}. "
            f"Please try again in {minutes_left} minute{'s' if minutes_left != 1 else ''}."
        )
        return

    # ── Prepare pending data & Dispatch OTP Email ─────────────────────────────
    pending_data = {
        "uni_name": uni_name.strip(),
        "slug": slug,
        "departments": departments,
        "admin_name": admin_name.strip(),
        "admin_email": admin_email.strip(),
        "admin_pass": admin_pass,
    }

    otp_code = otp_service.generate_otp(admin_email, pending_data)
    sent, send_err = send_otp_email(admin_email, otp_code, purpose="admin_registration")

    if not sent:
        otp_service.clear(admin_email)
        st.error(f"Failed to send verification email: {send_err}")
        return

    # Transition to Step 2
    st.session_state.onboarding_step = 2
    st.session_state.onboarding_email = admin_email.strip()
    st.session_state.onboarding_data = pending_data
    st.rerun()
