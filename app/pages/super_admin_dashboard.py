# app/pages/super_admin_dashboard.py
"""
Super Admin Dashboard.
Allows managing onboarding requests and viewing cross-tenant usage metrics.
"""

import streamlit as st
import pandas as pd
import json
from sqlalchemy.orm import Session
from sqlalchemy import func
from models.university import University
from models.user import User, UserRole
from models.ticket import Ticket
from models.audit_log import AuditLog
from services.audit_service import AuditService
from utils.timezone import to_ist


def render(db: Session, current_user: User) -> None:
    st.markdown("<h2>Super Admin Console</h2>", unsafe_allow_html=True)
    st.markdown(
        "<p style='color:#6B6B6B; font-size:14px; margin-bottom: 1.5rem;'>"
        "Manage institution onboarding requests and view global platform activity."
        "</p>",
        unsafe_allow_html=True,
    )

    tab_pending, tab_all, tab_add_admin, tab_analytics, tab_settings, tab_audit = st.tabs([
        "Pending Requests",
        "All Institutions",
        "Add Admin",
        "Platform Analytics",
        "Console Settings",
        "Audit Log",
    ])

    # ── TAB 1: PENDING REQUESTS ───────────────────────────────────────────────
    with tab_pending:
        pending_unis = (
            db.query(University)
            .filter(University.status == "pending")
            .order_by(University.created_at.desc())
            .all()
        )

        if not pending_unis:
            st.info("No pending onboarding requests.")
        else:
            for uni in pending_unis:
                # Query admin account created for this university
                admin = (
                    db.query(User)
                    .filter(User.university_id == uni.id, User.role == UserRole.admin)
                    .first()
                )

                admin_name = admin.name if admin else "N/A"
                admin_email = admin.email if admin else "N/A"

                # Render Card
                st.markdown(
                    f"<div class='uqms-card'>"
                    f"<h3 style='margin-top:0;'>{uni.name}</h3>"
                    f"<p style='margin: 4px 0; color:#6B6B6B;'><b>Slug:</b> {uni.slug}</p>"
                    f"<p style='margin: 4px 0; color:#6B6B6B;'><b>Administrator:</b> {admin_name} ({admin_email})</p>"
                    f"<p style='margin: 4px 0; color:#6B6B6B;'><b>Requested At:</b> {to_ist(uni.created_at).strftime('%Y-%m-%d %H:%M:%S')}</p>"
                    f"<p style='margin: 4px 0; color:#6B6B6B;'><b>Departments:</b> {', '.join(uni.departments) or 'None specified'}</p>"
                    f"</div>",
                    unsafe_allow_html=True
                )

                col1, col2 = st.columns([1, 4])
                with col1:
                    if st.button("Approve", key=f"btn_app_{uni.id}", use_container_width=True):
                        try:
                            uni.status = "approved"
                            db.commit()
                            AuditService.log(db,
                                university_id=uni.id,
                                actor_user_id=current_user.id,
                                action="admin_approval",
                                target_type="University",
                                target_id=uni.id,
                                details={"university_name": uni.name},
                            )
                            st.success(f"Approved {uni.name}! The admin can now log in.")
                            st.rerun()
                        except Exception as e:
                            db.rollback()
                            st.error(f"Approval failed: {e}")
                with col2:
                    with st.expander("Reject Onboarding Request"):
                        reason = st.text_input(
                            "Rejection Reason (optional)",
                            placeholder="e.g. Invalid domain/email pattern",
                            key=f"reason_{uni.id}"
                        )
                        if st.button("Confirm Rejection", key=f"btn_rej_{uni.id}", type="primary"):
                            try:
                                uni.status = "rejected"
                                uni.rejection_reason = reason.strip() if reason.strip() else None
                                db.commit()
                                AuditService.log(db,
                                    university_id=uni.id,
                                    actor_user_id=current_user.id,
                                    action="admin_rejection",
                                    target_type="University",
                                    target_id=uni.id,
                                    details={"university_name": uni.name, "reason": uni.rejection_reason},
                                )
                                st.success(f"Rejected onboarding request for {uni.name}.")
                                st.rerun()
                            except Exception as e:
                                db.rollback()
                                st.error(f"Rejection failed: {e}")
                st.markdown("<hr style='border:0; border-top:1px solid #E5E5E5; margin: 1.5rem 0;'>", unsafe_allow_html=True)

    # ── TAB 2: ALL INSTITUTIONS ───────────────────────────────────────────────
    with tab_all:
        status_filter = st.selectbox(
            "Filter by Status",
            options=["All", "Approved", "Pending", "Rejected"],
            index=0
        )

        query = db.query(University)
        if status_filter != "All":
            query = query.filter(University.status == status_filter.lower())
        
        unis = query.order_by(University.name).all()

        if not unis:
            st.info(f"No universities found with status '{status_filter}'.")
        else:
            for uni in unis:
                admin = (
                    db.query(User)
                    .filter(User.university_id == uni.id, User.role == UserRole.admin)
                    .first()
                )
                admin_name = admin.name if admin else "N/A"
                admin_email = admin.email if admin else "N/A"

                badge_class = f"badge-{uni.status}"
                # custom styling in main.py does not define badge-pending/approved/rejected,
                # let's define inline style or classes helper
                if uni.status == "approved":
                    badge_style = "background-color: #DCFCE7; color: #16A34A; border: 1px solid #BBF7D0;"
                elif uni.status == "pending":
                    badge_style = "background-color: #FEF3C7; color: #D97706; border: 1px solid #FDE68A;"
                else:
                    badge_style = "background-color: #FEE2E2; color: #DC2626; border: 1px solid #FCA5A5;"

                st.markdown(
                    f"<div class='uqms-card'>"
                    f"<div style='display:flex; justify-content:space-between; align-items:center;'>"
                    f"<h3 style='margin:0;'>{uni.name}</h3>"
                    f"<span class='badge' style='{badge_style}'>{uni.status.upper()}</span>"
                    f"</div>"
                    f"<p style='margin: 6px 0 2px 0; color:#6B6B6B;'><b>Slug:</b> {uni.slug} &bull; <b>Admin:</b> {admin_name} ({admin_email})</p>",
                    unsafe_allow_html=True
                )
                if uni.status == "rejected" and uni.rejection_reason:
                    st.markdown(
                        f"<p style='margin: 4px 0 0 0; font-size:13px; color:#DC2626;'><b>Rejection Reason:</b> {uni.rejection_reason}</p>",
                        unsafe_allow_html=True
                    )
                st.markdown("</div>", unsafe_allow_html=True)

    # ── TAB 3: ADD ADMIN ──────────────────────────────────────────────────────
    with tab_add_admin:
        st.markdown("<h3>Create Additional Admin</h3>", unsafe_allow_html=True)
        st.markdown(
            "<p style='color:#6B6B6B; font-size:14px; margin-bottom: 1.5rem;'>"
            "Manually add an administrator account to an already-approved university."
            "</p>",
            unsafe_allow_html=True,
        )

        # Fetch only approved universities
        approved_unis = (
            db.query(University)
            .filter(University.status == "approved")
            .order_by(University.name)
            .all()
        )

        if not approved_unis:
            st.info("No approved universities found. Approve an institution first from the Pending Requests tab.")
        else:
            # Search / filter approved universities
            search_term = st.text_input(
                "Search University",
                placeholder="Type to filter approved institutions…",
                key="add_admin_search"
            )
            filtered_unis = [
                u for u in approved_unis
                if search_term.strip().lower() in u.name.lower()
            ] if search_term.strip() else approved_unis

            if not filtered_unis:
                st.warning(f"No approved university matches \"{search_term}\".")
            else:
                uni_options = {u.name: u for u in filtered_unis}
                selected_name = st.selectbox(
                    "Select University",
                    options=list(uni_options.keys()),
                    key="add_admin_uni_select"
                )
                selected_uni = uni_options[selected_name]

                # Show existing admins for context
                existing_admins = (
                    db.query(User)
                    .filter(User.university_id == selected_uni.id, User.role == UserRole.admin)
                    .order_by(User.name)
                    .all()
                )
                if existing_admins:
                    admin_list_html = "".join(
                        f"<li style='margin:2px 0;'>{a.name} — <code>{a.email}</code></li>"
                        for a in existing_admins
                    )
                    st.markdown(
                        f"<div class='uqms-card'>"
                        f"<p style='margin:0 0 6px 0; font-weight:600; font-size:14px;'>Existing Admins ({len(existing_admins)})</p>"
                        f"<ul style='margin:0; padding-left:1.2rem; color:#6B6B6B; font-size:13px;'>{admin_list_html}</ul>"
                        f"</div>",
                        unsafe_allow_html=True
                    )
                else:
                    st.caption("ℹ️ This university currently has no admin accounts.")

                # Department options from the university's configured departments
                dept_options = selected_uni.departments or []

                # Form to create a new admin
                st.markdown("<div class='uqms-card'>", unsafe_allow_html=True)
                st.write("#### New Admin Details")

                with st.form("add_admin_form", clear_on_submit=True):
                    admin_name = st.text_input("Full Name", placeholder="e.g. Dr. Jane Smith", key="new_admin_name")
                    admin_email = st.text_input("Email Address", placeholder="e.g. jane.smith@university.edu", key="new_admin_email")
                    admin_password = st.text_input("Temporary Password", type="password", placeholder="Minimum 6 characters", key="new_admin_pass")
                    admin_password_confirm = st.text_input("Confirm Password", type="password", placeholder="••••••••", key="new_admin_pass_confirm")

                    if dept_options:
                        admin_dept = st.selectbox("Department (optional)", options=["— None —"] + dept_options, key="new_admin_dept")
                        admin_dept = None if admin_dept == "— None —" else admin_dept
                    else:
                        admin_dept = None
                        st.caption("No departments configured for this university.")

                    submit_admin = st.form_submit_button("Create Admin Account", use_container_width=True)

                if submit_admin:
                    errors = []
                    if not admin_name or not admin_name.strip():
                        errors.append("Full Name is required.")
                    if not admin_email or not admin_email.strip():
                        errors.append("Email Address is required.")
                    elif "@" not in admin_email or "." not in admin_email.split("@")[-1]:
                        errors.append("Invalid email address format.")
                    if not admin_password:
                        errors.append("Temporary Password is required.")
                    elif len(admin_password) < 8:
                        errors.append("Password must be at least 8 characters.")
                    elif not any(ch.isdigit() for ch in admin_password):
                        errors.append("Password must contain at least one number.")
                    elif admin_password != admin_password_confirm:
                        errors.append("Passwords do not match.")

                    if errors:
                        for e in errors:
                            st.error(f"{e}")
                    else:
                        from services.auth_service import AuthService
                        auth_svc = AuthService(db)
                        try:
                            # Pre-check: email already taken in this university?
                            if auth_svc.check_email_exists(selected_uni.id, admin_email.strip()):
                                st.error(
                                    "This email is already registered. "
                                    "Please sign in instead, or use a different email."
                                )
                            else:
                                new_admin = auth_svc.register_user(
                                    university_id=selected_uni.id,
                                    name=admin_name.strip(),
                                    email=admin_email.strip().lower(),
                                    password=admin_password,
                                    role=UserRole.admin,
                                    department=admin_dept,
                                )
                                st.success(
                                    f"Admin account created for **{new_admin.name}** "
                                    f"({new_admin.email}) at **{selected_uni.name}**."
                                )
                                AuditService.log(db,
                                    university_id=selected_uni.id,
                                    actor_user_id=current_user.id,
                                    action="admin_created",
                                    target_type="User",
                                    target_id=new_admin.id,
                                    details={"name": new_admin.name, "email": new_admin.email},
                                )
                                st.info("The new admin can now sign in with the temporary password provided.")
                                st.rerun()
                        except Exception:
                            st.error("Something went wrong creating the admin account. Please try again.")

                st.markdown("</div>", unsafe_allow_html=True)

    # ── TAB 4: PLATFORM ANALYTICS ─────────────────────────────────────────────
    with tab_analytics:
        all_unis = db.query(University).order_by(University.name).all()
        
        if not all_unis:
            st.info("No institutions onboarded.")
        else:
            analytics_data = []
            for uni in all_unis:
                student_count = (
                    db.query(User)
                    .filter(User.university_id == uni.id, User.role == UserRole.student)
                    .count()
                )
                ticket_count = (
                    db.query(Ticket)
                    .filter(Ticket.university_id == uni.id)
                    .count()
                )

                # Compute last activity date
                max_ticket = db.query(func.max(Ticket.created_at)).filter(Ticket.university_id == uni.id).scalar()
                max_user = db.query(func.max(User.created_at)).filter(User.university_id == uni.id).scalar()
                dates = [d for d in [max_ticket, max_user, uni.created_at] if d is not None]
                last_act = max(dates) if dates else uni.created_at
                last_act_str = to_ist(last_act).strftime("%Y-%m-%d %H:%M")

                analytics_data.append({
                    "University Name": uni.name,
                    "Status": uni.status.upper(),
                    "Student Count": student_count,
                    "Ticket Count": ticket_count,
                    "Last Activity": last_act_str
                })

            df = pd.DataFrame(analytics_data)
            
            # Show Metrics Summaries
            c1, c2, c3 = st.columns(3)
            with c1:
                st.metric("Total Institutions", len(all_unis))
            with c2:
                total_students = db.query(User).filter(User.role == UserRole.student).count()
                st.metric("Total Registered Students", total_students)
            with c3:
                total_tickets = db.query(Ticket).count()
                st.metric("Total Support Tickets", total_tickets)

            st.markdown("<h3>Institutional Health & Usage Overview</h3>", unsafe_allow_html=True)
            st.dataframe(df, use_container_width=True, hide_index=True)

    # ── TAB 5: CONSOLE SETTINGS ───────────────────────────────────────────────
    with tab_settings:
        st.markdown("<h3>Console Settings</h3>", unsafe_allow_html=True)
        st.markdown(
            "<p style='color:#6B6B6B; font-size:14px; margin-bottom: 1.5rem;'>"
            "Change your Super Admin account email and/or update your login password."
            "</p>",
            unsafe_allow_html=True,
        )

        st.markdown("<div class='uqms-card'>", unsafe_allow_html=True)
        st.write("#### Account Credentials")

        with st.form("super_admin_settings_form"):
            new_email = st.text_input(
                "Super Admin Email",
                value=current_user.email,
                placeholder="superadmin@uqms.edu"
            )
            current_pass = st.text_input(
                "Current Password (required to save changes)",
                type="password",
                placeholder="••••••••"
            )
            new_pass = st.text_input(
                "New Password (optional)",
                type="password",
                placeholder="Min 8 characters, at least 1 number"
            )
            new_pass_confirm = st.text_input(
                "Confirm New Password (optional)",
                type="password",
                placeholder="••••••••"
            )
            submit_creds = st.form_submit_button("Update Credentials", use_container_width=True)

        if submit_creds:
            errors = []
            if not new_email.strip():
                errors.append("Email address is required.")
            if not current_pass:
                errors.append("Current password is required to save changes.")
            if new_pass:
                if len(new_pass) < 8:
                    errors.append("New password must be at least 8 characters.")
                elif not any(ch.isdigit() for ch in new_pass):
                    errors.append("New password must contain at least one number.")
                if new_pass != new_pass_confirm:
                    errors.append("New passwords do not match.")

            if errors:
                for e in errors:
                    st.error(f"{e}")
            else:
                from services.auth_service import AuthService
                auth_svc = AuthService(db)
                try:
                    updated_user = auth_svc.update_user_credentials(
                        user_id=current_user.id,
                        current_password=current_pass,
                        new_email=new_email,
                        new_password=new_pass if new_pass else None
                    )
                    st.session_state.user = updated_user
                    st.success("Super Admin credentials updated successfully!")
                    st.rerun()
                except ValueError as ve:
                    st.error(f"{ve}")
                except Exception as ex:
                    st.error(f"Error updating credentials: {ex}")
        st.markdown("</div>", unsafe_allow_html=True)

    # ── TAB 6: AUDIT LOG ───────────────────────────────────────────────────────
    with tab_audit:
        st.markdown("<h3>Platform Audit Log</h3>", unsafe_allow_html=True)
        st.markdown(
            "<p style='color:#6B6B6B; font-size:14px; margin-bottom: 1.5rem;'>"
            "Cross-tenant activity log showing all significant platform actions."
            "</p>",
            unsafe_allow_html=True,
        )

        audit_entries = (
            db.query(AuditLog)
            .order_by(AuditLog.created_at.desc())
            .limit(200)
            .all()
        )

        if not audit_entries:
            st.info("No audit events recorded yet.")
        else:
            audit_data = []
            for entry in audit_entries:
                uni_name = entry.university.name if entry.university else "— (System)"
                actor_name = entry.actor.name if entry.actor else "—"
                audit_data.append({
                    "Timestamp": to_ist(entry.created_at).strftime("%Y-%m-%d %H:%M:%S") if entry.created_at else "—",
                    "University": uni_name,
                    "Actor": actor_name,
                    "Action": entry.action,
                    "Target": f"{entry.target_type or ''}#{entry.target_id or ''}",
                    "Details": entry.details or "",
                })

            st.dataframe(
                pd.DataFrame(audit_data),
                use_container_width=True,
                hide_index=True,
            )
