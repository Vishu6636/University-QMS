# app/pages/public_inquiry.py
"""
Public-facing prospective inquirer page.

Allows anyone (no login required) to:
1. Select an approved university
2. Chat with the university's RAG knowledge base
3. Optionally submit contact info as a lead for admissions follow-up

Security:
- No ticket creation (student_id=None, db=None passed to answer_query)
- No access to tickets, student info, or admin features
- Read-only RAG chat scoped to the selected university's KB
"""

import streamlit as st
from models.base import SessionLocal
from models.lead import Lead
from services.auth_service import AuthService
from services.rag_chat import answer_query
from services.billing import is_subscription_active


def _get_client_ip() -> str:
    """Safely retrieve the client IP from Streamlit headers (Tornado request context)."""
    try:
        # Check newer Streamlit version headers
        headers = getattr(st, "context", None)
        if headers is not None and hasattr(headers, "headers"):
            h = headers.headers
            for key in ["X-Forwarded-For", "X-Real-IP", "x-forwarded-for", "x-real-ip"]:
                val = h.get(key)
                if val:
                    return val.split(",")[0].strip()
    except Exception:
        pass
    return "127.0.0.1"


def render() -> None:
    """Render the public inquiry page."""
    import uuid
    if "session_id" not in st.session_state:
        st.session_state.session_id = str(uuid.uuid4())
    db = st.session_state.get("db") or SessionLocal()


    # ── Institution Resolution & White-Labeling ────────────────────────
    all_universities = AuthService.list_universities(db)
    approved_universities = [u for u in all_universities if u.status == "approved"]

    if not approved_universities:
        st.markdown(
            "<div class='uqms-card' style='text-align:center; padding: 2rem;'>"
            "<p style='color:#6B6B6B;'>No institutions are currently accepting public inquiries. "
            "Please check back later.</p>"
            "</div>",
            unsafe_allow_html=True,
        )
        return

    # Check if a specific college slug was passed in URL (?uni=college-slug)
    query_slug = (st.query_params.get("uni") or "").strip().lower()
    uni = None
    if query_slug:
        uni = next((u for u in approved_universities if (u.slug or "").lower() == query_slug), None)

    if uni:
        # ── Specific institution: show header only, NO generic landing text ──
        lbl = uni.institution_label  # e.g. "School", "University", "Institution"
        logo_path = uni.logo_url or ""
        old_globe = any(fragment in logo_path for fragment in (
            "gstatic.com/faviconV2", "google.com/s2/favicons"
        ))
        if logo_path and not old_globe:
            logo_column, heading_column = st.columns([1, 10], vertical_alignment="center")
            with logo_column:
                st.image(logo_path, width=46)
            with heading_column:
                st.markdown(f"<h3 style='margin:0;'>{uni.name}</h3>", unsafe_allow_html=True)
        else:
            # Text initials placeholder — never a generic globe
            initials = "".join(w[0].upper() for w in uni.name.split()[:2])
            logo_html = (
                f"<div style='width:46px; height:46px; border-radius:8px; background:#EEF2FF; "
                f"border:1px solid #C7D2FE; display:flex; align-items:center; justify-content:center; "
                f"margin-right:14px; font-weight:700; font-size:16px; color:#4F46E5; flex-shrink:0;'>"
                f"{initials}</div>"
            )
        if not (logo_path and not old_globe):
            st.markdown(
                f"""
            <div style='display: flex; align-items: center; margin-bottom: 1.25rem;'>
                {logo_html}
                <h3 style='margin: 0; font-size: 18px; color: #1A1A1A; font-weight: 600;'>{uni.name}</h3>
            </div>
            """,
                unsafe_allow_html=True,
            )
    else:
        # Generic landing view: show heading + explore text + dropdown
        st.markdown("<h2>Ask About an Institution</h2>", unsafe_allow_html=True)
        st.markdown(
            "<p style='color:#6B6B6B; font-size:14px; margin-bottom: 1.5rem;'>"
            "Explore any institution's knowledge base \u2014 no account needed. "
            "Ask about admissions, fees, courses, deadlines, and more."
            "</p>",
            unsafe_allow_html=True,
        )
        uni_names = [u.name for u in approved_universities]
        lbl = "Institution"  # generic label when no specific uni is selected
        selected_name = st.selectbox(
            "Select an Institution",
            uni_names,
            key="public_inquiry_uni_select",
        )
        uni = next(u for u in approved_universities if u.name == selected_name)
        lbl = uni.institution_label
        st.markdown(
            f"<div class='uqms-card' style='padding: 12px 16px;'>"
            f"<p style='margin:0; font-size:13px; color:#6B6B6B;'>"
            f"Chatting with <b>{uni.name}</b>'s knowledge base. "
            f"Answers are generated from the {lbl.lower()}'s uploaded documents.</p>"
            f"</div>",
            unsafe_allow_html=True,
        )

    # ── Subscription Entitlement Check (Calm Paused Notice) ────────────────────
    if not is_subscription_active(uni):
        st.markdown(
            f"""
            <div class='uqms-card' style='padding: 2.5rem 1.5rem; text-align: center; border: 1px solid #E4E4E7; background: #FAFAFA; border-radius: 8px; margin-top: 1rem;'>
                <p style='color: #52525B; font-size: 15px; margin: 0; font-weight: 500;'>
                    The 24/7 AI query service for <b>{uni.name}</b> is temporarily paused pending subscription renewal.
                </p>
                <p style='color: #71717A; font-size: 13px; margin: 8px 0 0 0;'>
                    Please contact the {lbl.lower()} admissions office directly for assistance.
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

    # ── Chat Interface ───────────────────────────────────────────────────────
    history_key = f"public_chat_{uni.id}"
    if history_key not in st.session_state:
        st.session_state[history_key] = []

    history = st.session_state[history_key]

    # Render previous messages
    for msg in history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Input box
    lbl = uni.institution_label
    query = st.chat_input(
        f"Ask a question about this {lbl.lower()}…",
        key=f"public_chat_input_{uni.id}",
    )

    if query:
        # Check rate limiter (session and IP-based)
        from services.rate_limiter import rag_query_limiter
        session_key = st.session_state.get("session_id", "guest_default")
        client_ip = _get_client_ip()
        ip_key = f"ip_{client_ip}"

        allowed_session, retry_session = rag_query_limiter.record_attempt(session_key)
        allowed_ip, retry_ip = rag_query_limiter.record_attempt(ip_key)

        if not allowed_session or not allowed_ip:
            retry_after = max(retry_session, retry_ip)
            st.error(f"Too many requests. Please wait {retry_after} second{'s' if retry_after != 1 else ''} before trying again.")
        else:
            # Show user message
            with st.chat_message("user"):
                st.markdown(query)
            history.append({"role": "user", "content": query})

            # Get answer — NO db/student_id so no ticket auto-escalation
            with st.chat_message("assistant"):
                with st.spinner("Searching knowledge base…"):
                    result = answer_query(uni.id, query, db=db, student_id=None, chat_history=history)

                st.markdown(result["answer"])

                col1, col2 = st.columns([3, 1])
                with col2:
                    st.markdown(
                        f"<p style='font-size:12px; color:#6B6B6B; text-align:right; margin:0;'>"
                        f"{result['chunks_used']} chunk(s) used"
                        f"</p>",
                        unsafe_allow_html=True,
                    )

            history.append({
                "role": "assistant",
                "content": result["answer"],
            })

    # Clear chat button
    if history:
        if st.button("Clear chat", key=f"public_clear_chat_{uni.id}", use_container_width=True):
            st.session_state[history_key] = []
            st.rerun()

    # ── Lead Capture Form ────────────────────────────────────────────────────
    # Show after at least 2 user messages, or always via expander
    user_msg_count = sum(1 for m in history if m["role"] == "user")

    st.markdown(
        "<hr style='border:0; border-top:1px solid #E5E5E5; margin: 2rem 0;'>",
        unsafe_allow_html=True,
    )

    # Auto-expand after a few exchanges for natural lead capture
    expanded = user_msg_count >= 2

    with st.expander("Want more info? Talk to admissions", expanded=expanded):
        st.markdown(
            "<p style='color:#6B6B6B; font-size:13px; margin-bottom:12px;'>"
            f"Leave your contact info and we'll connect you with the {lbl.lower()}'s admissions team. "
            "Only your email is required."
            "</p>",
            unsafe_allow_html=True,
        )

        # Auto-generate inquiry summary from conversation
        conversation_gist = ""
        user_questions = [m["content"] for m in history if m["role"] == "user"]
        if user_questions:
            conversation_gist = "; ".join(user_questions[:5])  # First 5 questions
            if len(conversation_gist) > 500:
                conversation_gist = conversation_gist[:497] + "..."

        with st.form(f"lead_form_{uni.id}", clear_on_submit=True):
            lead_name = st.text_input(
                "Your Name (optional)",
                placeholder="e.g. Jane Doe",
                key=f"lead_name_{uni.id}",
            )
            lead_email = st.text_input(
                "Email Address *",
                placeholder="e.g. jane@example.com",
                key=f"lead_email_{uni.id}",
            )
            lead_phone = st.text_input(
                "Phone Number (optional)",
                placeholder="e.g. +1-555-0123",
                key=f"lead_phone_{uni.id}",
            )
            lead_summary = st.text_area(
                "What are you interested in?",
                value=conversation_gist,
                placeholder="e.g. I'm interested in the MBA program and want to know about application deadlines…",
                height=100,
                key=f"lead_summary_{uni.id}",
            )

            submitted = st.form_submit_button(
                "Submit Inquiry",
                use_container_width=True,
            )

        if submitted:
            # Validate
            errors = []
            if not lead_email.strip():
                errors.append("Email address is required.")
            elif "@" not in lead_email or "." not in lead_email.split("@")[-1]:
                errors.append("Please enter a valid email address.")
            if not lead_summary.strip():
                errors.append("Please describe what you're interested in.")

            if errors:
                for e in errors:
                    st.error(f"{e}")
            else:
                try:
                    new_lead = Lead(
                        university_id=uni.id,
                        name=lead_name.strip() or None,
                        email=lead_email.strip().lower(),
                        phone=lead_phone.strip() or None,
                        inquiry_summary=lead_summary.strip(),
                    )
                    db.add(new_lead)
                    db.commit()
                    st.success(
                        "Thanks! Your inquiry has been submitted. "
                        f"The admissions team at **{uni.name}** will reach out to you soon."
                    )
                except Exception:
                    db.rollback()
                    st.error("Something went wrong submitting your inquiry. Please try again.")
