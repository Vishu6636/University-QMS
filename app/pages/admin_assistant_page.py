# app/pages/admin_assistant_page.py
"""
Admin Assistant page — operational data analytics (admin-only).

Answers questions about the university's OWN operational data by querying
the SQL database directly (NOT ChromaDB). Supports structured query intents:
- Pending/open ticket count
- Escalated ticket count
- Average resolution time
- Tickets by department
- Dashboard summary (combined stats)
- Student/user count
- Feedback/satisfaction stats
- Weekly leads
- Most asked questions (TODO: Phase 3 — student-question logging)

All queries are strictly scoped to st.session_state.university.id for
tenant isolation. No raw LLM-generated SQL — hardcoded query intents
with keyword matching to avoid SQL injection risk.
"""

import streamlit as st
import re
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from sqlalchemy import func

from models.ticket import Ticket, TicketStatus, TicketPriority
from models.feedback import Feedback
from models.user import User, UserRole
from models.lead import Lead


def classify_and_execute(query: str, db: Session, uni_id: int) -> str | None:
    """
    Check if query matches one of the structured operational intents.
    If matched, execute DB query and return answer string. Otherwise return None.

    All queries are scoped to uni_id for tenant isolation.
    """
    q = query.lower().strip()

    # ── 1. Dashboard summary ──────────────────────────────────────────────────
    # e.g. "summarize the dashboard", "dashboard summary", "give me an overview"
    if ("dashboard" in q and ("summar" in q or "overview" in q)) or \
       ("summary" in q and ("dashboard" in q or "overview" in q)) or \
       ("overview" in q) or \
       ("summarize" in q and ("dashboard" in q or "data" in q or "status" in q)):
        return _dashboard_summary(db, uni_id)

    # ── 2. Open / pending ticket count ────────────────────────────────────────
    # e.g. "how many open tickets", "pending tickets", "active tickets"
    if ("ticket" in q or "tickets" in q) and \
       any(kw in q for kw in ["open", "pending", "active", "unresolved"]):
        count = db.query(Ticket).filter(
            Ticket.university_id == uni_id,
            Ticket.status.in_([
                TicketStatus.open,
                TicketStatus.in_progress,
                TicketStatus.escalated,
                TicketStatus.reopened,
            ])
        ).count()
        return (
            f"There are currently **{count}** pending ticket(s) in the queue "
            f"(includes open, in-progress, escalated, and reopened statuses)."
        )

    # ── 3. Escalated ticket count ─────────────────────────────────────────────
    # e.g. "how many escalated tickets", "escalated tickets count"
    if "escalated" in q and ("ticket" in q or "count" in q or "how many" in q):
        count = db.query(Ticket).filter(
            Ticket.university_id == uni_id,
            Ticket.status == TicketStatus.escalated
        ).count()
        return (
            f"There are currently **{count}** escalated ticket(s) "
            f"requiring immediate administrative attention."
        )

    # ── 4. Average resolution time ────────────────────────────────────────────
    # e.g. "average resolution time", "how long to resolve", "resolution speed"
    if ("resolution" in q and ("time" in q or "speed" in q or "long" in q)) or \
       "avg resolution" in q or "average resolution" in q or \
       ("how long" in q and "resolve" in q):
        return _avg_resolution_time(db, uni_id)

    # ── 5. Tickets by department ──────────────────────────────────────────────
    # e.g. "tickets by department", "department breakdown", "tickets per department"
    if "ticket" in q and ("department" in q or "dept" in q):
        return _tickets_by_department(db, uni_id)

    # ── 6. Tickets by priority ────────────────────────────────────────────────
    # e.g. "tickets by priority", "priority breakdown", "how many high priority"
    if "ticket" in q and "priority" in q:
        return _tickets_by_priority(db, uni_id)

    # ── 7. Student / user count ───────────────────────────────────────────────
    # e.g. "how many students", "registered students", "student count", "total users"
    if any(kw in q for kw in ["student", "students", "user", "users"]) and \
       any(kw in q for kw in ["how many", "count", "total", "registered", "number"]):
        return _user_count(db, uni_id)

    # ── 8. Feedback / satisfaction stats ──────────────────────────────────────
    # e.g. "average satisfaction", "feedback score", "satisfaction rating"
    if any(kw in q for kw in ["feedback", "satisfaction", "rating"]) and \
       any(kw in q for kw in ["average", "avg", "score", "how", "what", "rating"]):
        return _feedback_stats(db, uni_id)

    # ── 9. Weekly leads ───────────────────────────────────────────────────────
    # e.g. "weekly leads", "leads this week", "new leads"
    if "lead" in q and ("week" in q or "weekly" in q or "new" in q or "recent" in q):
        seven_days_ago = datetime.now(timezone.utc) - timedelta(days=7)
        leads_count = db.query(Lead).filter(
            Lead.university_id == uni_id,
            Lead.created_at >= seven_days_ago
        ).count()
        total_leads = db.query(Lead).filter(
            Lead.university_id == uni_id,
        ).count()
        return (
            f"There are **{leads_count}** new prospective student lead(s) "
            f"registered in the last 7 days, out of **{total_leads}** total leads."
        )

    # ── 10. Most asked questions ──────────────────────────────────────────────
    # TODO: Phase 3 — student-question logging feature.
    # Once a student_questions table exists to log every RAG query, this intent
    # should surface the top N categories/questions from that table, scoped to
    # university_id. Until then, return an honest message.
    if ("most asked" in q or "frequently asked" in q or "common question" in q or
        "top question" in q or "popular question" in q):
        return (
            "The **most-asked questions** feature is not yet available. "
            "It requires the student-question logging system (Phase 3) to track "
            "and aggregate queries. Once that's implemented, I'll be able to "
            "surface the top categories and questions students are asking."
        )

    # No match — return None so the caller can show a helpful redirect message
    return None


# ── Structured query helper functions ─────────────────────────────────────────

def _dashboard_summary(db: Session, uni_id: int) -> str:
    """Combine key operational metrics into a natural-language summary."""

    # Ticket counts by status
    status_counts = {}
    for status in TicketStatus:
        count = db.query(Ticket).filter(
            Ticket.university_id == uni_id,
            Ticket.status == status,
        ).count()
        status_counts[status.value] = count
    total_tickets = sum(status_counts.values())

    # Ticket counts by priority
    priority_counts = {}
    for prio in TicketPriority:
        count = db.query(Ticket).filter(
            Ticket.university_id == uni_id,
            Ticket.priority == prio,
        ).count()
        priority_counts[prio.value] = count

    # Average resolution time
    avg_res_str = _calc_avg_resolution(db, uni_id)

    # Average feedback satisfaction
    avg_sat = db.query(func.avg(Feedback.satisfaction_score)).join(
        Ticket, Feedback.ticket_id == Ticket.id
    ).filter(
        Ticket.university_id == uni_id
    ).scalar()

    feedback_count = db.query(Feedback).join(
        Ticket, Feedback.ticket_id == Ticket.id
    ).filter(
        Ticket.university_id == uni_id
    ).count()

    # Student count
    student_count = db.query(User).filter(
        User.university_id == uni_id,
        User.role == UserRole.student,
    ).count()

    # Build summary
    lines = []
    lines.append("### Dashboard Summary\n")

    lines.append(f"**Total Tickets:** {total_tickets}")
    status_parts = [f"{k.replace('_', ' ').title()}: {v}" for k, v in status_counts.items() if v > 0]
    if status_parts:
        lines.append(f"  — By status: {', '.join(status_parts)}")

    prio_parts = [f"{k.title()}: {v}" for k, v in priority_counts.items() if v > 0]
    if prio_parts:
        lines.append(f"  — By priority: {', '.join(prio_parts)}")

    lines.append(f"\n**Avg. Resolution Time:** {avg_res_str}")

    if avg_sat is not None:
        lines.append(f"**Avg. Satisfaction Score:** {avg_sat:.1f}/5.0 ({feedback_count} rating(s))")
    else:
        lines.append("**Avg. Satisfaction Score:** No feedback ratings yet.")

    lines.append(f"\n**Registered Students:** {student_count}")

    return "\n".join(lines)


def _avg_resolution_time(db: Session, uni_id: int) -> str:
    """Calculate and format average resolution time."""
    avg_res_str = _calc_avg_resolution(db, uni_id)
    return f"The average resolution time for resolved tickets is **{avg_res_str}**."


def _calc_avg_resolution(db: Session, uni_id: int) -> str:
    """Internal: compute average resolution hours as formatted string."""
    def _make_utc(dt):
        if dt is None:
            return None
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)

    tickets = db.query(Ticket).filter(
        Ticket.university_id == uni_id,
        Ticket.status.in_([TicketStatus.resolved, TicketStatus.closed]),
    ).all()

    resolution_times = []
    for t in tickets:
        res_time = t.resolved_at or t.created_at
        created_aware = _make_utc(t.created_at)
        res_aware = _make_utc(res_time)
        hrs = (res_aware - created_aware).total_seconds() / 3600.0
        if hrs < 0:
            hrs = 1.0
        resolution_times.append(hrs)

    if resolution_times:
        avg_hrs = sum(resolution_times) / len(resolution_times)
        if avg_hrs < 1:
            return f"{avg_hrs * 60:.0f} minutes"
        return f"{avg_hrs:.1f} hours"
    return "not available (no resolved tickets yet)"


def _tickets_by_department(db: Session, uni_id: int) -> str:
    """Ticket volume breakdown by department."""
    results = db.query(Ticket.department, func.count(Ticket.id)).filter(
        Ticket.university_id == uni_id
    ).group_by(Ticket.department).all()

    if not results:
        return "No tickets have been registered under this institution yet."

    lines = ["Here is the ticket volume breakdown by department:\n"]
    for dept, count in results:
        dept_name = dept or "General"
        lines.append(f"- **{dept_name}**: {count} ticket(s)")
    return "\n".join(lines)


def _tickets_by_priority(db: Session, uni_id: int) -> str:
    """Ticket volume breakdown by priority."""
    results = db.query(Ticket.priority, func.count(Ticket.id)).filter(
        Ticket.university_id == uni_id
    ).group_by(Ticket.priority).all()

    if not results:
        return "No tickets have been registered under this institution yet."

    lines = ["Here is the ticket breakdown by priority level:\n"]
    for prio, count in results:
        prio_label = prio.value.title() if hasattr(prio, 'value') else str(prio).title()
        lines.append(f"- **{prio_label}**: {count} ticket(s)")
    return "\n".join(lines)


def _user_count(db: Session, uni_id: int) -> str:
    """Count of registered students and admins."""
    student_count = db.query(User).filter(
        User.university_id == uni_id,
        User.role == UserRole.student,
    ).count()
    admin_count = db.query(User).filter(
        User.university_id == uni_id,
        User.role == UserRole.admin,
    ).count()
    total = student_count + admin_count
    return (
        f"There are **{total}** registered user(s) for this institution: "
        f"**{student_count}** student(s) and **{admin_count}** admin(s)."
    )


def _feedback_stats(db: Session, uni_id: int) -> str:
    """Average satisfaction score from feedback."""
    avg_sat = db.query(func.avg(Feedback.satisfaction_score)).join(
        Ticket, Feedback.ticket_id == Ticket.id
    ).filter(
        Ticket.university_id == uni_id
    ).scalar()

    feedback_count = db.query(Feedback).join(
        Ticket, Feedback.ticket_id == Ticket.id
    ).filter(
        Ticket.university_id == uni_id
    ).count()

    if avg_sat is not None:
        return (
            f"The average student satisfaction score is **{avg_sat:.1f}/5.0** "
            f"based on **{feedback_count}** feedback rating(s)."
        )
    return "No feedback ratings have been submitted yet for this institution."


# ── Page renderer ─────────────────────────────────────────────────────────────

def render(uni, user) -> None:
    db = st.session_state.db
    st.markdown("<h2>Admin Assistant</h2>", unsafe_allow_html=True)
    st.markdown(
        f"<p style='color:#6B6B6B; font-size:14px; margin-bottom: 1.5rem;'>"
        f"Ask questions about your university's <b>operational data</b> — tickets, "
        f"students, feedback, and resolution metrics. All answers are queried from "
        f"the live database.<br>"
        f"<i>For document or policy questions, use the <b>RAG Chat</b> page instead.</i>"
        f"</p>",
        unsafe_allow_html=True,
    )

    # Suggested queries
    with st.expander("Example questions you can ask", expanded=False):
        st.markdown("""
- "Summarize the dashboard"
- "How many open/pending tickets are there?"
- "How many escalated tickets?"
- "What is the average resolution time?"
- "Show tickets by department"
- "Show tickets by priority"
- "How many students are registered?"
- "What is the average satisfaction score?"
- "How many new leads this week?"
- "What are the most asked questions?"
""")

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
    query = st.chat_input(
        "Ask about tickets, students, feedback, or metrics…",
        key=f"admin_assistant_input_{uni.id}_{user.id}",
    )

    if query:
        # Check rate limiter
        from services.rate_limiter import rag_query_limiter
        allowed, retry_after = rag_query_limiter.record_attempt(user.email)
        if not allowed:
            st.error(
                f"Too many requests. Please wait {retry_after} "
                f"second{'s' if retry_after != 1 else ''} before trying again."
            )
        else:
            # Show user message
            with st.chat_message("user"):
                st.markdown(query)
            history.append({"role": "user", "content": query})

            # Process message
            with st.chat_message("assistant"):
                with st.spinner("Querying operational data…"):
                    answer_text = classify_and_execute(query, db, uni.id)

                if answer_text is not None:
                    st.markdown(answer_text)
                    st.markdown(
                        f"<p style='font-size:12px; color:#6B6B6B; margin: 4px 0 0 0;'>"
                        f"Data Source: Live Database Query"
                        f"</p>",
                        unsafe_allow_html=True,
                    )
                else:
                    # No rule match — do NOT fall back to RAG. Redirect user.
                    answer_text = (
                        "I can only answer questions about **operational data** "
                        "(tickets, students, feedback, resolution metrics, and leads).\n\n"
                        "For questions about university policies, fees, admissions, "
                        "or other document-based topics, please use the **RAG Chat** page.\n\n"
                        "Try asking something like:\n"
                        "- *\"Summarize the dashboard\"*\n"
                        "- *\"How many open tickets?\"*\n"
                        "- *\"What is the average satisfaction score?\"*"
                    )
                    st.markdown(answer_text)

            history.append({"role": "assistant", "content": answer_text})

    # Clear chat button
    if history:
        st.markdown("<div style='margin-top:1.5rem;'>", unsafe_allow_html=True)
        if st.button(
            "Clear chat history",
            key=f"clear_admin_assistant_{uni.id}_{user.id}",
            use_container_width=True,
        ):
            st.session_state[history_key] = []
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
