# app/pages/student_dashboard.py
"""
Student-facing portal views.
Renders tickets list, submit ticket form, and feedback forms inside a clean tabbed layout.
"""

import streamlit as st
from sqlalchemy.orm import Session

from models.university import University
from models.user import User
from models.ticket import TicketStatus, TicketPriority
from services.ticket_service import TicketService
from utils.timezone import to_ist


def render(db: Session, university: University, user: User) -> None:
    """Main student portal layout with tabs."""
    st.markdown(f"<h2>Student Portal &mdash; {university.name}</h2>", unsafe_allow_html=True)
    st.markdown(
        f"<p style='color:#6B6B6B; font-size:14px; margin-bottom: 1.5rem;'>"
        f"Manage your support requests and feedback."
        f"</p>",
        unsafe_allow_html=True,
    )

    tab1, tab2, tab3 = st.tabs([
        "My Support Tickets",
        "Submit New Ticket",
        "Give Feedback"
    ])

    with tab1:
        render_my_tickets(db, university, user)

    with tab2:
        render_submit_ticket(db, university, user)

    with tab3:
        render_feedback(db, university, user)


def render_my_tickets(db: Session, university: University, user: User) -> None:
    """List student tickets with high contrast cards and badges."""
    svc = TicketService(db, university.id)
    tickets = svc.list_tickets(student_id=user.id)

    if not tickets:
        st.markdown(
            "<div style='padding: 2rem; border: 1px dashed #E5E5E5; border-radius: 8px; text-align: center; color: #6B6B6B;'>"
            "You haven't raised any tickets yet."
            "</div>",
            unsafe_allow_html=True
        )
        return

    for t in tickets:
        status_value = t.status.value
        prio_value = t.priority.value

        # Badges
        status_badge = f"<span class='badge badge-{status_value}'>{status_value.replace('_', ' ')}</span>"
        prio_badge = f"<span class='prio-badge prio-{prio_value}'>{prio_value}</span>"

        # Created date formatting
        created_date = to_ist(t.created_at).strftime("%B %d, %Y at %I:%M %p")

        # Feedback block
        feedback_status = ""
        if status_value == "resolved":
            resolution_html = ""
            if getattr(t, "resolution_text", None):
                resolution_html = (
                    f"<div style='margin-top:12px; margin-bottom:12px; padding:10px 14px; background:#EEF2FF; "
                    f"border-radius:6px; border:1px solid #C7D2FE; font-size:13px; color:#1E1B4B;'>"
                    f"<b>Admin's Answer:</b> {t.resolution_text}"
                    f"</div>"
                )
            if t.feedback:
                feedback_status = (
                    f"{resolution_html}"
                    f"<div style='margin-top: 12px; padding: 10px 14px; background: #DCFCE7; "
                    f"border-radius: 6px; border: 1px solid #BBF7D0; font-size: 13px; color: #16A34A;'>"
                    f"<b>Feedback Submitted:</b> "
                    f"{t.feedback.satisfaction_score}/5 &mdash; <i>{t.feedback.comment or 'No comment'}</i>"
                    f"</div>"
                )
            else:
                feedback_status = (
                    f"{resolution_html}"
                    f"<div style='margin-top: 12px; padding: 10px 14px; background: #FEF3C7; "
                    f"border-radius: 6px; border: 1px solid #FDE68A; font-size: 13px; color: #D97706;'>"
                    f"<b>Awaiting Feedback:</b> "
                    f"Please rate this ticket under the 'Give Feedback' tab above."
                    f"</div>"
                )

        # Sentiment block
        sentiment_html = ""
        if t.sentiment_score is not None:
            sentiment_color = "#16A34A" if t.sentiment_score >= 0 else "#DC2626"
            sentiment_label = "Positive" if t.sentiment_score >= 0 else "Negative"
            sentiment_html = (
                f" | <b>Sentiment:</b> <span style='color:{sentiment_color}'>{t.sentiment_score:.2f} ({sentiment_label})</span>"
            )

        st.markdown(
            f"<div class='uqms-card'>"
            f"<div style='display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;'>"
            f"<h3 style='margin: 0; font-size: 1.1rem; color: #1A1A1A;'>#{t.id} &mdash; {t.title}</h3>"
            f"<div>{status_badge}{prio_badge}</div>"
            f"</div>"
            f"<p style='color: #6B6B6B; font-size: 0.85rem; margin: 0 0 12px 0;'>"
            f"<b>Created:</b> {created_date} | <b>Department:</b> {t.department}{sentiment_html}"
            f"</p>"
            f"<p style='margin: 10px 0 0 0; color: #1A1A1A; line-height: 1.5; font-size: 0.95rem;'>"
            f"{t.description}"
            f"</p>"
            f"{feedback_status}"
            f"</div>",
            unsafe_allow_html=True,
        )


def render_submit_ticket(db: Session, university: University, user: User) -> None:
    """Submit ticket form with modern input styling and validation."""
    kb_check_key = f"kb_check_{user.id}"
    show_form_key = f"show_form_{user.id}"
    form_reset_key = f"form_reset_{user.id}"
    
    # Initialize session states
    if kb_check_key not in st.session_state:
        st.session_state[kb_check_key] = None
    if show_form_key not in st.session_state:
        st.session_state[show_form_key] = False
    if form_reset_key not in st.session_state:
        st.session_state[form_reset_key] = 0

    # Step 1: Input title and description outside st.form so we can use buttons/reruns
    st.markdown("<div class='uqms-card'>", unsafe_allow_html=True)
    st.write("#### Tell us about your query")
    
    counter = st.session_state[form_reset_key]
    title_key = f"input_title_{user.id}_{counter}"
    desc_key = f"input_desc_{user.id}_{counter}"
    
    title = st.text_input("Ticket Title", placeholder="e.g. Cannot access library portal", max_chars=200, key=title_key)
    description = st.text_area(
        "Detailed Description",
        placeholder="Please describe your query or problem in detail. This description is analyzed to predict priority and department.",
        height=150,
        key=desc_key
    )
    
    # Check KB button
    if st.button("Check Knowledge Base First", use_container_width=True):
        if not title.strip() or not description.strip():
            st.error("Please fill in both the title and description fields.")
        else:
            with st.spinner("Checking knowledge base..."):
                from services.rag_chat import answer_query
                result = answer_query(university.id, description.strip(), db=None, student_id=None)
                st.session_state[kb_check_key] = result
                # If AI can't answer (escalates), then we skip confirmation and show form
                if result["escalate"]:
                    st.session_state[show_form_key] = True
                else:
                    st.session_state[show_form_key] = False
            st.rerun()
            
    st.markdown("</div>", unsafe_allow_html=True)

    kb_result = st.session_state[kb_check_key]
    show_ticket_form = st.session_state[show_form_key]

    # Step 2: Confirmation Gate
    if kb_result is not None and not kb_result["escalate"] and not show_ticket_form:
        st.markdown(
            f"<div class='uqms-card' style='border-color: #C7D2FE; background-color: #EEF2FF;'>",
            unsafe_allow_html=True
        )
        st.write("#### 🤖 Potential Answer Found in Knowledge Base")
        st.markdown(kb_result["answer"])
        st.markdown("</div>", unsafe_allow_html=True)

        col1, col2 = st.columns(2)
        with col1:
            if st.button("This solves it, no ticket needed", use_container_width=True):
                # Clear all inputs and state
                st.session_state[kb_check_key] = None
                st.session_state[show_form_key] = False
                st.session_state[form_reset_key] += 1
                st.success("Great! Glad we could help resolve your query.")
                st.rerun()
        with col2:
            if st.button("Still raise a ticket", use_container_width=True):
                st.session_state[show_form_key] = True
                st.rerun()
                
    # If we need to show the ticket form
    elif show_ticket_form or (kb_result is not None and kb_result["escalate"]):
        st.markdown("<div class='uqms-card'>", unsafe_allow_html=True)
        st.write("#### Finalize & Submit Ticket")
        with st.form("submit_ticket_form"):
            col1, col2 = st.columns(2)
            with col1:
                depts = ["Auto-detect Department"] + (university.departments or ["General"])
                selected_dept = st.selectbox("Assign to Department", options=depts)
            with col2:
                prio_options = ["Auto-detect Priority"] + [p.value.title() for p in TicketPriority]
                selected_prio = st.selectbox("Assign Priority", options=prio_options)

            submitted = st.form_submit_button("Submit Ticket", use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

        if submitted:
            with st.spinner("Processing query analysis and routing..."):
                # Clean up auto-detect values
                dept_val = None if selected_dept == "Auto-detect Department" else selected_dept
                prio_val = None if selected_prio == "Auto-detect Priority" else TicketPriority(selected_prio.lower())

                svc = TicketService(db, university.id)
                ticket = svc.create_ticket(
                    student_id=user.id,
                    title=title.strip(),
                    description=description.strip(),
                    department=dept_val,
                    priority=prio_val
                )

                st.success(f"Ticket #{ticket.id} successfully created and cataloged!")
                
                # Clear session state
                st.session_state[kb_check_key] = None
                st.session_state[show_form_key] = False
                st.session_state[form_reset_key] += 1
                
                status_val = ticket.status.value
                prio_val = ticket.priority.value
                status_badge = f"<span class='badge badge-{status_val}'>{status_val.replace('_', ' ')}</span>"
                prio_badge = f"<span class='prio-badge prio-{prio_val}'>{prio_val}</span>"
                
                st.markdown(
                    f"<div class='uqms-card' style='margin-top: 1rem; border-color: #BBF7D0; background-color: #F0FDF4;'>"
                    f"<h4 style='margin-top: 0; color: #16A34A;'>Processed Ticket Summary</h4>"
                    f"<p style='color:#1A1A1A;'><b>Ticket ID:</b> #{ticket.id}</p>"
                    f"<p style='color:#1A1A1A;'><b>Title:</b> {ticket.title}</p>"
                    f"<p style='color:#1A1A1A;'><b>Routed Department:</b> {ticket.department}</p>"
                    f"<p style='color:#1A1A1A;'><b>Priority Level:</b> {prio_badge}</p>"
                    f"<p style='color:#1A1A1A;'><b>Status:</b> {status_badge}</p>"
                    f"<p style='color:#1A1A1A;'><b>Calculated Sentiment Score:</b> {ticket.sentiment_score:.2f}</p>"
                    f"</div>",
                    unsafe_allow_html=True
                )


def render_feedback(db: Session, university: University, user: User) -> None:
    """Give feedback on resolved tickets with sliding scale."""
    svc = TicketService(db, university.id)
    # Fetch resolved tickets for this student
    resolved = svc.list_tickets(student_id=user.id, status=TicketStatus.resolved)
    no_feedback = [t for t in resolved if not t.feedback]

    if not no_feedback:
        st.markdown(
            "<div style='padding: 2rem; border: 1px dashed #E5E5E5; border-radius: 8px; text-align: center; color: #6B6B6B;'>"
            "You do not have any resolved tickets awaiting feedback."
            "</div>",
            unsafe_allow_html=True
        )
        return

    # Render feedback form
    ticket_map = {f"#{t.id} — {t.title}": t for t in no_feedback}
    
    with st.container():
        st.markdown("<div class='uqms-card'>", unsafe_allow_html=True)
        
        chosen_ticket_label = st.selectbox("Select a Resolved Ticket", list(ticket_map.keys()))
        selected_ticket = ticket_map[chosen_ticket_label]
        
        st.write(f"**Ticket Description:**")
        st.write(selected_ticket.description)
        st.markdown("<hr style='border:0; border-top:1px solid #E5E5E5; margin: 15px 0;'>", unsafe_allow_html=True)
        
        # Rating (1 to 5 stars)
        score = st.slider(
            "Satisfaction Rating (1 = Very Dissatisfied, 5 = Very Satisfied)", 
            min_value=1.0, 
            max_value=5.0, 
            value=5.0, 
            step=1.0
        )
        
        # Display helpful text matching the score
        score_meanings = {
            1.0: "Very Dissatisfied",
            2.0: "Dissatisfied",
            3.0: "Neutral",
            4.0: "Satisfied",
            5.0: "Extremely Satisfied"
        }
        st.info(f"Your selection: **{score_meanings.get(score, '')}**")
        
        comment = st.text_area("Share your comments or suggestions (optional)", placeholder="How was your experience?")
        
        if st.button("Submit Rating & Review", use_container_width=True):
            svc.add_feedback(selected_ticket.id, score, comment.strip())
            st.success("Thank you! Your feedback has been registered.")
            st.rerun()
            
        st.markdown("</div>", unsafe_allow_html=True)
