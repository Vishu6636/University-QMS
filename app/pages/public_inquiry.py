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


def render() -> None:
    """Render the public inquiry page."""
    db = st.session_state.get("db") or SessionLocal()

    st.markdown("<h2>Ask About a University</h2>", unsafe_allow_html=True)
    st.markdown(
        "<p style='color:#6B6B6B; font-size:14px; margin-bottom: 1.5rem;'>"
        "Explore any university's knowledge base — no account needed. "
        "Ask about admissions, fees, courses, deadlines, and more."
        "</p>",
        unsafe_allow_html=True,
    )

    # ── University Selector (approved only) ──────────────────────────────────
    all_universities = AuthService.list_universities(db)
    approved_universities = [u for u in all_universities if u.status == "approved"]

    if not approved_universities:
        st.markdown(
            "<div class='uqms-card' style='text-align:center; padding: 2rem;'>"
            "<p style='color:#6B6B6B;'>No universities are currently accepting public inquiries. "
            "Please check back later.</p>"
            "</div>",
            unsafe_allow_html=True,
        )
        return

    uni_names = [u.name for u in approved_universities]
    selected_name = st.selectbox(
        "Select a University",
        uni_names,
        key="public_inquiry_uni_select",
    )
    uni = next(u for u in approved_universities if u.name == selected_name)

    st.markdown(
        f"<div class='uqms-card' style='padding: 12px 16px;'>"
        f"<p style='margin:0; font-size:13px; color:#6B6B6B;'>"
        f"Chatting with <b>{uni.name}</b>'s knowledge base. "
        f"Answers are generated from the university's uploaded documents.</p>"
        f"</div>",
        unsafe_allow_html=True,
    )

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
    query = st.chat_input(
        "Ask a question about this university…",
        key=f"public_chat_input_{uni.id}",
    )

    if query:
        # Show user message
        with st.chat_message("user"):
            st.markdown(query)
        history.append({"role": "user", "content": query})

        # Get answer — NO db/student_id so no ticket auto-escalation
        with st.chat_message("assistant"):
            with st.spinner("Searching knowledge base…"):
                result = answer_query(uni.id, query, db=None, student_id=None)

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
            "Leave your contact info and we'll connect you with the university's admissions team. "
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
