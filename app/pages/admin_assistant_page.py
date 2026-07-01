# app/pages/admin_assistant_page.py
"""
Admin Assistant page.
Provides real-time answers to administration queries.
Uses rule-based matching for operational stats (ticket counts, leads, resolution time),
and falls back to Groq RAG for other questions.
"""

import streamlit as st
import re
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from sqlalchemy import func

from models.ticket import Ticket, TicketStatus
from models.lead import Lead
from services.rag_chat import answer_query


def classify_and_execute(query: str, db: Session, uni_id: int) -> str | None:
    """
    Check if query matches one of the 5 rule-based operational intents.
    If matched, execute DB query and return answer string. Otherwise return None.
    """
    q = query.lower().strip()

    # 1. Open ticket count
    # e.g. "how many open tickets", "number of open tickets", "open tickets count"
    if "open" in q and "ticket" in q:
        count = db.query(Ticket).filter(
            Ticket.university_id == uni_id,
            Ticket.status.in_([TicketStatus.open, TicketStatus.in_progress, TicketStatus.reopened])
        ).count()
        return f"There are currently **{count}** open/pending tickets in the queue."

    # 2. Escalated ticket count
    # e.g. "how many escalated tickets", "number of escalated tickets", "escalated tickets"
    if "escalated" in q and ("ticket" in q or "count" in q):
        count = db.query(Ticket).filter(
            Ticket.university_id == uni_id,
            Ticket.status == TicketStatus.escalated
        ).count()
        return f"There are currently **{count}** escalated tickets requiring immediate administrative attention."

    # 3. Average resolution time
    # e.g. "average resolution time", "avg resolution time", "how long to resolve"
    if ("resolution" in q and "time" in q) or "avg resolution" in q or "average resolution" in q:
        tickets = db.query(Ticket).filter(Ticket.university_id == uni_id).all()
        
        def _make_utc(dt):
            if dt is None:
                return None
            if dt.tzinfo is None:
                return dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)

        resolution_times = []
        for t in tickets:
            if t.status in (TicketStatus.resolved, TicketStatus.closed):
                res_time = t.resolved_at or t.created_at
                created_aware = _make_utc(t.created_at)
                res_aware = _make_utc(res_time)
                hrs = (res_aware - created_aware).total_seconds() / 3600.0
                if hrs < 0:
                    hrs = 1.0
                resolution_times.append(hrs)
        
        if resolution_times:
            avg_res = sum(resolution_times) / len(resolution_times)
            return f"The average resolution time for resolved tickets at this institution is **{avg_res:.1f} hours**."
        else:
            return "No tickets have been resolved yet under this institution, so the average resolution time is not available."

    # 4. Tickets by department
    # e.g. "tickets by department", "department tickets", "tickets per department"
    if "ticket" in q and "department" in q:
        results = db.query(Ticket.department, func.count(Ticket.id)).filter(
            Ticket.university_id == uni_id
        ).group_by(Ticket.department).all()
        
        lines = []
        for dept, count in results:
            dept_name = dept or "General"
            lines.append(f"- **{dept_name}**: {count} ticket(s)")
        
        if lines:
            dept_str = "\n".join(lines)
            return f"Here is the ticket volume breakdown by department:\n\n{dept_str}"
        else:
            return "No tickets have been registered under this institution."

    # 5. Weekly leads
    # e.g. "weekly leads", "leads this week", "leads registered this week", "new leads"
    if "lead" in q and ("week" in q or "weekly" in q or "new" in q):
        seven_days_ago = datetime.now(timezone.utc) - timedelta(days=7)
        leads_count = db.query(Lead).filter(
            Lead.university_id == uni_id,
            Lead.created_at >= seven_days_ago
        ).count()
        return f"There are **{leads_count}** prospective student leads registered in the last 7 days."

    return None


def render(uni, user) -> None:
    db = st.session_state.db
    st.markdown("<h2>Admin Query Assistant</h2>", unsafe_allow_html=True)
    st.markdown(
        f"<p style='color:#6B6B6B; font-size:14px; margin-bottom: 1.5rem;'>"
        f"Ask questions about your university's operations (tickets, departments, leads) "
        f"or search general institution documentation."
        f"</p>",
        unsafe_allow_html=True,
    )

    # Init chat history
    history_key = f"admin_assistant_history_{uni.id}_{user.id}"
    if history_key not in st.session_state:
        st.session_state[history_key] = []

    history = st.session_state[history_key]

    # Render previous messages
    for msg in history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Input box
    query = st.chat_input("Ask a question about operations or documentation…", key=f"admin_assistant_input_{uni.id}_{user.id}")

    if query:
        # Show user message
        with st.chat_message("user"):
            st.markdown(query)
        history.append({"role": "user", "content": query})

        # Process message
        with st.chat_message("assistant"):
            with st.spinner("Processing query…"):
                # First check rule-based match
                answer_text = classify_and_execute(query, db, uni.id)
                
                # Fallback to general RAG if no match
                if answer_text is None:
                    result = answer_query(uni.id, query)
                    answer_text = result["answer"]
                    st.markdown(answer_text)
                    st.markdown(
                        f"<p style='font-size:12px; color:#6B6B6B; margin: 4px 0 0 0;'>"
                        f"🤖 Generated via Groq RAG — {result['chunks_used']} chunk(s) used"
                        f"</p>",
                        unsafe_allow_html=True
                    )
                else:
                    st.markdown(answer_text)
                    st.markdown(
                        f"<p style='font-size:12px; color:#6B6B6B; margin: 4px 0 0 0;'>"
                        f"⚡ SQL Direct Query Result"
                        f"</p>",
                        unsafe_allow_html=True
                    )

        history.append({"role": "assistant", "content": answer_text})

    # Clear chat button
    if history:
        st.markdown("<div style='margin-top:1.5rem;'>", unsafe_allow_html=True)
        if st.button("Clear chat history", key=f"clear_admin_assistant_{uni.id}_{user.id}", use_container_width=True):
            st.session_state[history_key] = []
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
