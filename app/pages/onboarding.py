# app/pages/onboarding.py
"""
University onboarding — Step 1.
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
from services.auth_service import AuthService


def _slugify(text: str) -> str:
    """Very simple slug: lowercase, replace spaces/special chars with hyphens."""
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")


def render(db: Session) -> None:
    st.markdown("<h2>🎓 Register Your University</h2>", unsafe_allow_html=True)
    st.markdown(
        "<p style='color:#6B6B6B; font-size:14px; margin-bottom: 1.5rem;'>"
        "Fill in the details below to register your university and create your first administrator account."
        "</p>",
        unsafe_allow_html=True,
    )

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

        submitted = st.form_submit_button("Create University & Admin Account", use_container_width=True)
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
    if len(admin_pass) < 6:
        errors.append("Password must be at least 6 characters.")
    if admin_pass != admin_pass2:
        errors.append("Passwords do not match.")

    # Check slug uniqueness
    slug = _slugify(uni_name)
    existing_slug = db.query(University).filter(University.slug == slug).first()
    if existing_slug:
        errors.append(f"A university with slug '{slug}' already exists. Choose a different name.")

    if errors:
        for e in errors:
            st.error(f"⚠️ {e}")
        return

    # ── Parse departments ─────────────────────────────────────────────────────
    departments = [d.strip() for d in dept_raw.split(",") if d.strip()]

    # ── Persist ───────────────────────────────────────────────────────────────
    try:
        uni = University(
            name=uni_name.strip(),
            slug=slug,
            department_list=json.dumps(departments),
        )
        db.add(uni)
        db.flush()  # get uni.id before creating the user

        auth_svc = AuthService(db)
        admin_user = auth_svc.register_user(
            university_id=uni.id,
            name=admin_name.strip(),
            email=admin_email.strip(),
            password=admin_pass,
            role=UserRole.admin,
        )
        # register_user already commits; no second commit needed.

        st.success(
            f"✅ **{uni.name}** has been registered successfully! "
            f"Admin account for **{admin_user.email}** is active."
        )

        # Store in session and rerun to refresh navigation and profile cards
        st.session_state.university = uni
        st.session_state.user = admin_user
        st.rerun()

    except Exception as exc:
        db.rollback()
        st.error(f"⚠️ Something went wrong: {exc}")
