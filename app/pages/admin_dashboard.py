# app/pages/admin_dashboard.py
"""
Admin-facing portal views.
Contains pages for:
1. Overview (KPI metrics and pie chart)
2. Ticket Management (view all university tickets, filter, update status/priority)
3. Analytics & Insights (resolution times, student satisfaction, and intent insights)
4. Portal Settings (edit university department list)
5. Knowledge Base (upload new documents, view existing, delete)

Strictly scopes every query to the logged-in university_id.
"""

import json
import streamlit as st
from sqlalchemy.orm import Session

from models.university import University
from models.user import User
from models.ticket import Ticket, TicketStatus, TicketPriority
from models.feedback import Feedback
from models.kb_document import DocType, KBDocument
from services.ticket_service import TicketService
from services.kb_service import KBService


def render(db: Session, university: University, user: User) -> None:
    """Main admin portal layout with tabs."""
    st.markdown(f"<h2>🛠 Admin Portal &mdash; {university.name}</h2>", unsafe_allow_html=True)
    st.markdown(
        f"<p style='color:#6B6B6B; font-size:14px; margin-bottom: 1.5rem;'>"
        f"Monitor metrics, process tickets, manage knowledge base documents, and configure channels."
        f"</p>",
        unsafe_allow_html=True,
    )

    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📊 Dashboard Overview",
        "🎫 Ticket Management",
        "📈 Analytics & Insights",
        "⚙️ Portal Settings",
        "📚 Knowledge Base"
    ])

    with tab1:
        render_overview(db, university, user)

    with tab2:
        render_tickets(db, university, user)

    with tab3:
        render_analytics(db, university, user)

    with tab4:
        render_settings(db, university, user)

    with tab5:
        render_kb(db, university, user)


def render_overview(db: Session, university: University, user: User) -> None:
    """Page 1: Overview Dashboard."""
    scoped_uni = db.query(University).filter(University.id == university.id).first()
    if not scoped_uni:
        st.error("Access denied: Invalid tenant context.")
        return

    st.markdown("<h3>📊 Operations Overview</h3>", unsafe_allow_html=True)
    st.markdown(
        "<p style='color:#6B6B6B; font-size:14px; margin-bottom: 1.5rem;'>"
        "Real-time operational metrics and query status breakdown."
        "</p>",
        unsafe_allow_html=True,
    )

    svc = TicketService(db, scoped_uni.id)
    summary = svc.status_summary()

    # KPI Row
    k1, k2, k3, k4 = st.columns(4)
    for col, (label, key, color) in zip(
        [k1, k2, k3, k4],
        [
            ("Open", "open", "#4F46E5"),
            ("In Progress", "in_progress", "#D97706"),
            ("Resolved", "resolved", "#16A34A"),
            ("Escalated", "escalated", "#DC2626"),
        ],
    ):
        with col:
            st.markdown(
                f"<div class='uqms-card kpi'>"
                f"<div class='value' style='color:{color}'>{summary.get(key, 0)}</div>"
                f"<div class='label'>{label}</div>"
                f"</div>",
                unsafe_allow_html=True,
            )

    st.markdown("<hr style='border:0; border-top:1px solid #E5E5E5; margin: 2rem 0;'>", unsafe_allow_html=True)

    # Status Distribution Chart
    st.markdown("<h4>Ticket Status Distribution</h4>", unsafe_allow_html=True)
    if sum(summary.values()) == 0:
        st.info("No tickets registered yet under this institution to build status distribution.")
    else:
        try:
            import plotly.graph_objects as go

            labels = [s.value.replace("_", " ").title() for s in TicketStatus]
            values = [summary.get(s.value, 0) for s in TicketStatus]
            colors = ["#4F46E5", "#D97706", "#16A34A", "#DC2626", "#4B5563", "#7C3AED"]
            
            fig = go.Figure(
                go.Pie(
                    labels=labels,
                    values=values,
                    marker_colors=colors,
                    hole=0.45,
                    textinfo="label+percent",
                    textfont_color="#1A1A1A",
                )
            )
            fig.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font_color="#1A1A1A",
                showlegend=True,
                legend=dict(font=dict(color="#1A1A1A")),
                height=380,
                margin=dict(t=20, b=20, l=20, r=20)
            )
            st.plotly_chart(fig, use_container_width=True)
        except ImportError:
            st.info("Install `plotly` to view charts.")


def render_tickets(db: Session, university: University, user: User) -> None:
    """Page 2: Ticket Management."""
    scoped_uni = db.query(University).filter(University.id == university.id).first()
    if not scoped_uni:
        st.error("Access denied: Invalid tenant context.")
        return

    st.markdown("<h3>🎫 Ticket Management</h3>", unsafe_allow_html=True)
    st.markdown(
        "<p style='color:#6B6B6B; font-size:14px; margin-bottom: 1.5rem;'>"
        "Review student tickets, filter by department, priority, or status, and update progress."
        "</p>",
        unsafe_allow_html=True,
    )

    svc = TicketService(db, scoped_uni.id)

    # Filtering Controls Card
    st.markdown("<div class='uqms-card'>", unsafe_allow_html=True)
    fcol1, fcol2, fcol3 = st.columns(3)
    with fcol1:
        status_filter = st.selectbox(
            "Filter by Status",
            ["All"] + [s.value for s in TicketStatus],
        )
    with fcol2:
        dept_options = ["All"] + (scoped_uni.departments or [])
        dept_filter = st.selectbox("Filter by Department", dept_options)
    with fcol3:
        prio_filter = st.selectbox(
            "Filter by Priority",
            ["All"] + [p.value for p in TicketPriority],
        )
    st.markdown("</div>", unsafe_allow_html=True)

    filters = {
        "status": TicketStatus(status_filter) if status_filter != "All" else None,
        "department": dept_filter if dept_filter != "All" else None,
        "priority": TicketPriority(prio_filter) if prio_filter != "All" else None,
    }
    
    tickets = svc.get_tickets_for_university(filters)

    if not tickets:
        st.markdown(
            "<div style='padding: 2rem; border: 1px dashed #E5E5E5; border-radius: 8px; text-align: center; color: #6B6B6B;'>"
            "🔍 No tickets match the selected filters."
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

        # Student info scoped to active university
        student_info = t.student
        student_label = f"{student_info.name} ({student_info.email})" if student_info else f"Student ID: {t.student_id}"

        # Created date formatting
        created_date = t.created_at.strftime("%B %d, %Y at %I:%M %p")

        # Sentiment block
        sentiment_html = ""
        if t.sentiment_score is not None:
            sentiment_color = "#16A34A" if t.sentiment_score >= 0 else "#DC2626"
            sentiment_label = "Positive" if t.sentiment_score >= 0 else "Negative"
            sentiment_html = (
                f" | <b>Sentiment:</b> <span style='color:{sentiment_color}'>{t.sentiment_score:.2f} ({sentiment_label})</span>"
            )

        with st.expander(f"#{t.id} — {t.title} | {status_value.upper()}"):
            st.markdown(
                f"<div style='margin-bottom: 12px;'>"
                f"{status_badge} {prio_badge} <br><br>"
                f"<p style='color:#1A1A1A; margin: 4px 0;'><b>Student:</b> {student_label}</p>"
                f"<p style='color:#6B6B6B; margin: 4px 0; font-size:13px;'><b>Created:</b> {created_date} | <b>Department:</b> {t.department}{sentiment_html}</p>"
                f"</div>",
                unsafe_allow_html=True
            )
            st.markdown("<p style='color:#1A1A1A; font-weight:600; margin-bottom:4px;'>Description:</p>", unsafe_allow_html=True)
            st.write(t.description)

            # Post-resolution feedback if exists
            if t.feedback:
                st.markdown(
                    f"<div style='margin: 12px 0; padding: 10px 14px; background: #DCFCE7; "
                    f"border-radius: 6px; border: 1px solid #BBF7D0; color: #16A34A; font-size:13px;'>"
                    f"<b>⭐ Post-Resolution Feedback:</b> "
                    f"{t.feedback.satisfaction_score}/5 &mdash; <i>{t.feedback.comment or 'No comment'}</i>"
                    f"</div>",
                    unsafe_allow_html=True
                )

            st.markdown("<hr style='border:0; border-top:1px solid #E5E5E5; margin: 15px 0;'>", unsafe_allow_html=True)
            
            # Action Columns: Update Status and Update Priority
            acol1, acol2 = st.columns(2)
            with acol1:
                current_status = t.status
                
                # Determine next valid status options
                valid_next_statuses = []
                if current_status == TicketStatus.open:
                    valid_next_statuses = [TicketStatus.in_progress]
                elif current_status == TicketStatus.in_progress:
                    valid_next_statuses = [TicketStatus.resolved, TicketStatus.escalated]
                elif current_status == TicketStatus.resolved:
                    valid_next_statuses = [TicketStatus.closed, TicketStatus.reopened, TicketStatus.open]
                elif current_status == TicketStatus.escalated:
                    valid_next_statuses = [TicketStatus.resolved, TicketStatus.in_progress, TicketStatus.open]
                elif current_status == TicketStatus.reopened:
                    valid_next_statuses = [TicketStatus.in_progress]
                elif current_status == TicketStatus.closed:
                    valid_next_statuses = []

                if not valid_next_statuses:
                    st.info("Ticket is closed. No further status changes are permitted.")
                else:
                    new_status_str = st.selectbox(
                        "Transition Status To",
                        options=[s.value for s in valid_next_statuses],
                        key=f"status_select_{t.id}"
                    )
                    if st.button("Apply Status Transition", key=f"btn_apply_status_{t.id}", use_container_width=True):
                        try:
                            svc.update_ticket_status(t.id, TicketStatus(new_status_str))
                            st.success(f"✅ Ticket #{t.id} successfully updated to '{new_status_str}'!")
                            st.rerun()
                        except ValueError as e:
                            st.error(f"Cannot update status: {e}")

            with acol2:
                new_prio_str = st.selectbox(
                    "Update Priority Level",
                    options=[p.value for p in TicketPriority],
                    index=[p.value for p in TicketPriority].index(prio_value),
                    key=f"priority_select_{t.id}"
                )
                if st.button("Apply Priority Update", key=f"btn_apply_prio_{t.id}", use_container_width=True):
                    svc.update_priority(t.id, TicketPriority(new_prio_str))
                    st.success(f"✅ Ticket #{t.id} priority updated to '{new_prio_str}'!")
                    st.rerun()


def render_kb(db: Session, university: University, user: User) -> None:
    """Page 3: Knowledge Base Management."""
    scoped_uni = db.query(University).filter(University.id == university.id).first()
    if not scoped_uni:
        st.error("Access denied: Invalid tenant context.")
        return

    st.markdown("<h3>📚 Knowledge Base Management</h3>", unsafe_allow_html=True)
    st.markdown(
        "<p style='color:#6B6B6B; font-size:14px; margin-bottom: 1.5rem;'>"
        "Upload new institutional documents (txt or pdf) to index them into the RAG system, or manage existing records."
        "</p>",
        unsafe_allow_html=True,
    )

    kb_svc = KBService(db, scoped_uni)

    # Document Uploader Card
    st.markdown("<div class='uqms-card'>", unsafe_allow_html=True)
    st.write("#### 📤 Upload Document")
    
    with st.form("upload_kb_doc_form"):
        uploaded_file = st.file_uploader(
            "Choose a .txt or .pdf file",
            type=["txt", "pdf"],
            accept_multiple_files=False,
        )
        doc_type_val = st.selectbox("Document Classification Type", [d.value for d in DocType])
        submit_upload = st.form_submit_button("Index & Embed Document", use_container_width=True)

    if submit_upload:
        if not uploaded_file:
            st.error("Please select a file to upload.")
        else:
            with st.spinner("Extracting content and indexing into vector space..."):
                text_content = ""
                if uploaded_file.name.endswith(".pdf"):
                    try:
                        import pypdf
                        pdf_reader = pypdf.PdfReader(uploaded_file)
                        text_content = "\n\n".join(
                            page.extract_text() or "" for page in pdf_reader.pages
                        )
                    except ImportError:
                        st.error("pdf parsing engine `pypdf` is not installed on this system.")
                else:
                    text_content = uploaded_file.read().decode("utf-8", errors="replace")

                if not text_content.strip():
                    st.error("Could not extract any text from the provided file.")
                else:
                    doc = kb_svc.add_document(
                        filename=uploaded_file.name,
                        content_text=text_content,
                        doc_type=DocType(doc_type_val)
                    )
                    st.success(f"✅ Document '{doc.filename}' uploaded and indexed successfully!")
                    st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)

    # Document List
    st.markdown("<h3>📚 Existing Documents</h3>", unsafe_allow_html=True)
    
    docs = kb_svc.list_documents()
    if not docs:
        st.markdown("<p style='color:#6B6B6B; font-style:italic;'>No documents uploaded yet under this university.</p>", unsafe_allow_html=True)
        return

    for doc in docs:
        created_at_str = doc.uploaded_at.strftime("%B %d, %Y at %I:%M %p")
        with st.expander(f"📄 {doc.filename} ({doc.doc_type.value.upper()})"):
            st.markdown(
                f"<p style='color:#6B6B6B; font-size:0.85rem; margin-bottom:8px;'>"
                f"<b>Uploaded:</b> {created_at_str} | <b>Size:</b> {len(doc.content_text):,} characters"
                f"</p>",
                unsafe_allow_html=True
            )
            st.text_area(
                "Document Content Preview", 
                value=doc.content_text[:400] + "...", 
                height=150, 
                disabled=True, 
                key=f"kb_preview_{doc.id}"
            )
            
            if st.button("🗑 Remove Document", key=f"btn_del_doc_{doc.id}", use_container_width=True):
                if kb_svc.delete_document(doc.id):
                    st.success("✅ Document and its vector index deleted successfully!")
                    st.rerun()
                else:
                    st.error("Failed to delete document.")


def render_settings(db: Session, university: University, user: User) -> None:
    """Page 4: Portal Settings (edit department list)."""
    scoped_uni = db.query(University).filter(University.id == university.id).first()
    if not scoped_uni:
        st.error("Access denied: Invalid tenant context.")
        return

    st.markdown("<h3>⚙️ Portal Settings</h3>", unsafe_allow_html=True)
    st.markdown(
        "<p style='color:#6B6B6B; font-size:14px; margin-bottom: 1.5rem;'>"
        "Manage institutional settings, routing channels, and support departments."
        "</p>",
        unsafe_allow_html=True,
    )

    st.markdown("<div class='uqms-card'>", unsafe_allow_html=True)
    st.write("#### 🏛 Support Departments")
    st.write("Edit the list of support channels. Enter each department name on a new line.")

    current_dept_text = "\n".join(scoped_uni.departments)
    
    with st.form("settings_form"):
        new_dept_text = st.text_area(
            "Department List", 
            value=current_dept_text, 
            height=200,
            placeholder="e.g.\nComputer Science\nMathematics\nFinance\nRegistrar"
        )
        submit_settings = st.form_submit_button("Save Portal Settings", use_container_width=True)

    if submit_settings:
        new_departments = [
            line.strip() 
            for line in new_dept_text.split("\n") 
            if line.strip()
        ]
        
        if not new_departments:
            st.error("The university must have at least one department registered.")
        else:
            scoped_uni.departments = new_departments
            db.commit()
            st.success("✅ Portal settings and support departments updated successfully!")
            st.rerun()
            
    st.markdown("</div>", unsafe_allow_html=True)


def render_analytics(db: Session, university: University, user: User) -> None:
    """Page: Analytics Dashboard."""
    scoped_uni = db.query(University).filter(University.id == university.id).first()
    if not scoped_uni:
        st.error("Access denied: Invalid tenant context.")
        return

    st.markdown("<h3>📈 Analytics & Insights</h3>", unsafe_allow_html=True)
    st.markdown(
        "<p style='color:#6B6B6B; font-size:14px; margin-bottom: 1.5rem;'>"
        "Detailed performance analytics, resolution times, student satisfaction, and intent insights."
        "</p>",
        unsafe_allow_html=True,
    )

    # 1. Scoped Data Queries
    tickets = db.query(Ticket).filter(Ticket.university_id == scoped_uni.id).all()
    feedbacks = db.query(Feedback).join(Ticket).filter(Ticket.university_id == scoped_uni.id).all()

    if not tickets:
        st.info("No tickets registered yet under this university. Analytics will be populated once student tickets are created.")
        return

    # Helper to convert datetimes to UTC-aware to prevent subtracting naive and aware datetimes
    def _make_utc(dt):
        if dt is None:
            return None
        from datetime import timezone
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)

    # 2. Compute Ticket Resolution Times (overall + by department)
    resolution_times = []
    resolution_by_dept = {}
    
    for t in tickets:
        if t.status in (TicketStatus.resolved, TicketStatus.closed):
            res_time = t.resolved_at or t.created_at
            created_aware = _make_utc(t.created_at)
            res_aware = _make_utc(res_time)
            
            hrs = (res_aware - created_aware).total_seconds() / 3600.0
            if hrs < 0:
                hrs = 1.0
            resolution_times.append(hrs)
            
            dept = t.department or "General"
            if dept not in resolution_by_dept:
                resolution_by_dept[dept] = []
            resolution_by_dept[dept].append(hrs)

    avg_resolution_time = sum(resolution_times) / len(resolution_times) if resolution_times else 0.0
    avg_satisfaction = sum(f.satisfaction_score for f in feedbacks) / len(feedbacks) if feedbacks else 0.0

    # KPI Summary Cards
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown(
            f"<div class='uqms-card kpi'>"
            f"<div class='value' style='color:#4F46E5;'>{len(tickets)}</div>"
            f"<div class='label'>Total Tickets</div>"
            f"</div>",
            unsafe_allow_html=True
        )
    with col2:
        st.markdown(
            f"<div class='uqms-card kpi'>"
            f"<div class='value' style='color:#16A34A;'>{avg_satisfaction:.2f} / 5.0</div>"
            f"<div class='label'>Avg Satisfaction</div>"
            f"</div>",
            unsafe_allow_html=True
        )
    with col3:
        st.markdown(
            f"<div class='uqms-card kpi'>"
            f"<div class='value' style='color:#4F46E5;'>{avg_resolution_time:.1f} Hrs</div>"
            f"<div class='label'>Avg Resolution</div>"
            f"</div>",
            unsafe_allow_html=True
        )
    with col4:
        resolved_count = sum(1 for t in tickets if t.status in (TicketStatus.resolved, TicketStatus.closed))
        resolved_rate = (resolved_count / len(tickets)) * 100 if tickets else 0
        st.markdown(
            f"<div class='uqms-card kpi'>"
            f"<div class='value' style='color:#7C3AED;'>{resolved_rate:.1f}%</div>"
            f"<div class='label'>Resolution Rate</div>"
            f"</div>",
            unsafe_allow_html=True
        )

    st.markdown("<hr style='border:0; border-top:1px solid #E5E5E5; margin: 2rem 0;'>", unsafe_allow_html=True)

    # Import Plotly Graph Objects
    import plotly.graph_objects as go
    from collections import Counter

    # Row 1: Charts
    row1_col1, row1_col2 = st.columns(2)

    with row1_col1:
        # Chart 1: Pending vs Resolved vs Escalated ticket counts (Bar)
        pending_count = sum(1 for t in tickets if t.status in (TicketStatus.open, TicketStatus.in_progress, TicketStatus.reopened))
        resolved_count = sum(1 for t in tickets if t.status in (TicketStatus.resolved, TicketStatus.closed))
        escalated_count = sum(1 for t in tickets if t.status == TicketStatus.escalated)

        fig_status = go.Figure(
            go.Bar(
                x=["Pending", "Resolved", "Escalated"],
                y=[pending_count, resolved_count, escalated_count],
                marker_color=["#D97706", "#16A34A", "#DC2626"],
                text=[pending_count, resolved_count, escalated_count],
                textposition="auto",
            )
        )
        fig_status.update_layout(
            title="Pending vs Resolved vs Escalated Counts",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font_color="#1A1A1A",
            xaxis=dict(gridcolor="rgba(0,0,0,0.05)"),
            yaxis=dict(gridcolor="rgba(0,0,0,0.05)"),
            height=320,
            margin=dict(t=40, b=20, l=20, r=20),
        )
        st.plotly_chart(fig_status, use_container_width=True)

    with row1_col2:
        # Chart 2: Department-wise ticket volume (Pie/Donut)
        dept_counts = Counter(t.department or "General" for t in tickets)
        fig_dept = go.Figure(
            go.Pie(
                labels=list(dept_counts.keys()),
                values=list(dept_counts.values()),
                hole=0.4,
                textinfo="percent+label",
                marker=dict(colors=["#4F46E5", "#D97706", "#16A34A", "#DC2626", "#7C3AED", "#EC4899", "#A78BFA"])
            )
        )
        fig_dept.update_layout(
            title="Department-wise Ticket Volume",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font_color="#1A1A1A",
            height=320,
            margin=dict(t=40, b=20, l=20, r=20),
            showlegend=False
        )
        st.plotly_chart(fig_dept, use_container_width=True)

    # Row 2: Charts
    row2_col1, row2_col2 = st.columns(2)

    with row2_col1:
        # Chart 3: Average Resolution Time by Department (Horizontal Bar)
        if not resolution_by_dept:
            st.info("No resolved tickets available to calculate department resolution times.")
        else:
            dept_avgs = {dept: sum(times)/len(times) for dept, times in resolution_by_dept.items()}
            sorted_dept_avgs = sorted(dept_avgs.items(), key=lambda x: x[1])
            
            fig_res_dept = go.Figure(
                go.Bar(
                    x=[item[1] for item in sorted_dept_avgs],
                    y=[item[0] for item in sorted_dept_avgs],
                    orientation="h",
                    marker_color="#4F46E5"
                )
            )
            fig_res_dept.update_layout(
                title="Avg Resolution Time by Dept (Hours)",
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font_color="#1A1A1A",
                xaxis=dict(title="Hours", gridcolor="rgba(0,0,0,0.05)"),
                yaxis=dict(gridcolor="rgba(0,0,0,0.05)"),
                height=320,
                margin=dict(t=40, b=20, l=20, r=20),
            )
            st.plotly_chart(fig_res_dept, use_container_width=True)

    with row2_col2:
        # Chart 4: Student Satisfaction Trend (Line chart)
        if not feedbacks:
            st.info("No feedback registered yet to display satisfaction trends.")
        else:
            fb_trend_raw = []
            for f in feedbacks:
                res_time = f.ticket.resolved_at or f.ticket.created_at
                fb_trend_raw.append((_make_utc(res_time), f.satisfaction_score))
            
            fb_trend_raw.sort(key=lambda x: x[0])
            
            # Group daily
            daily_scores = {}
            for dt, score in fb_trend_raw:
                day_str = dt.strftime("%Y-%m-%d")
                if day_str not in daily_scores:
                    daily_scores[day_str] = []
                daily_scores[day_str].append(score)
                
            sorted_days = sorted(daily_scores.keys())
            daily_avgs = [sum(daily_scores[d]) / len(daily_scores[d]) for d in sorted_days]

            fig_satisfaction = go.Figure(
                go.Scatter(
                    x=sorted_days,
                    y=daily_avgs,
                    mode="lines+markers",
                    marker=dict(size=8, color="#16A34A"),
                    line=dict(width=3, color="#16A34A"),
                )
            )
            fig_satisfaction.update_layout(
                title="Student Satisfaction Trend",
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font_color="#1A1A1A",
                xaxis=dict(gridcolor="rgba(0,0,0,0.05)"),
                yaxis=dict(title="Satisfaction Score", range=[0.8, 5.2], gridcolor="rgba(0,0,0,0.05)"),
                height=320,
                margin=dict(t=40, b=20, l=20, r=20),
            )
            st.plotly_chart(fig_satisfaction, use_container_width=True)

    # Row 3: Intent categories (Full Width)
    st.markdown("<h4>Top 5 Issue Categories</h4>", unsafe_allow_html=True)
    
    with st.spinner("Classifying ticket descriptions..."):
        try:
            from services.intent_classifier import predict_intent
            intent_counts = Counter()
            
            for t in tickets:
                if t.description:
                    raw_intent = predict_intent(t.description)
                    clean_intent = raw_intent.replace("_", " ").title()
                    intent_counts[clean_intent] += 1
            
            top_5 = intent_counts.most_common(5)
            
            if not top_5:
                st.info("No query descriptions available for classification.")
            else:
                top_5_sorted = sorted(top_5, key=lambda x: x[1])
                fig_intent = go.Figure(
                    go.Bar(
                        x=[item[1] for item in top_5_sorted],
                        y=[item[0] for item in top_5_sorted],
                        orientation="h",
                        marker_color="#7C3AED",
                        text=[item[1] for item in top_5_sorted],
                        textposition="outside",
                    )
                )
                fig_intent.update_layout(
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    font_color="#1A1A1A",
                    xaxis=dict(title="Number of Queries", gridcolor="rgba(0,0,0,0.05)"),
                    yaxis=dict(gridcolor="rgba(0,0,0,0.05)"),
                    height=300,
                    margin=dict(t=20, b=20, l=20, r=20),
                )
                st.plotly_chart(fig_intent, use_container_width=True)
        except Exception as e:
            st.error(f"Failed to load or execute intent classifier: {e}")
