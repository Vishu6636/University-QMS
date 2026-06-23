# app/main.py
"""
app/main.py — Entry point for the University Query Management System Streamlit app.
Redesigned with SaaS-grade aesthetics (Notion/Linear style) and modern st.navigation.
"""

import sys
import os

# Force pure-python protobuf implementation to prevent opentelemetry/chromadb TypeError conflicts on deployment
os.environ["PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION"] = "python"

# Add project root to sys.path so all imports resolve from any working directory.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import streamlit as st
from models.base import Base, engine, SessionLocal
from models.university import University
from models.user import User, UserRole
from models.ticket import Ticket
from models.kb_document import KBDocument
from models.feedback import Feedback
from services.auth_service import AuthService

# Ensure data directory exists
db_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data"))
os.makedirs(db_dir, exist_ok=True)

# Create all tables in SQLite if they don't exist
Base.metadata.create_all(bind=engine)

# Auto-seed database if empty
db_inst = SessionLocal()
try:
    if db_inst.query(University).count() == 0:
        from scripts.db_init import seed_demo_data
        seed_demo_data()
finally:
    db_inst.close()

# ── Custom CSS for light, premium theme ────────────────────────────────────────
CUSTOM_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif !important;
}

/* ── Main App Background ── */
.stApp {
    background-color: #FFFFFF !important;
    color: #1A1A1A !important;
}

/* ── Streamlit Top Header Strip ── */
header[data-testid="stHeader"] {
    background-color: #FFFFFF !important;
    border-bottom: 1px solid #E5E5E5 !important;
}

/* ── Sidebar ── */
[data-testid="stSidebar"] {
    background-color: #FAFAFA !important;
    border-right: 1px solid #E5E5E5 !important;
}

/* ── Streamlit Sidebar Navigation Links ── */
[data-testid="stSidebar"] [data-testid="stSidebarNav"] {
    background-color: transparent !important;
}

/* Custom Styling for Streamlit Page Links in Sidebar */
[data-testid="stSidebar"] a {
    border-radius: 6px !important;
    padding: 8px 12px !important;
    margin: 2px 0 !important;
    color: #3F3F3F !important;
    font-weight: 500 !important;
    text-decoration: none !important;
    transition: background-color 0.15s ease, color 0.15s ease !important;
}
[data-testid="stSidebar"] a:hover {
    background-color: #F0F0F2 !important;
    color: #1A1A1A !important;
}
[data-testid="stSidebar"] a[aria-current="page"] {
    background-color: #EEF2FF !important;
    color: #4F46E5 !important;
    border-left: 3px solid #4F46E5 !important;
    font-weight: 600 !important;
}

/* ── Headings ── */
h1, h2, h3, h4, h5, h6 { 
    color: #1A1A1A !important; 
    font-family: 'Inter', sans-serif !important;
    font-weight: 600 !important;
}
h1 {
    font-size: 26px !important;
    margin-top: 1rem !important;
    margin-bottom: 6px !important;
}
h2 {
    font-size: 22px !important;
    margin-top: 0 !important;
    margin-bottom: 8px !important;
}
h3 {
    font-size: 18px !important;
    margin-top: 1.5rem !important;
    margin-bottom: 10px !important;
}

/* ── Cards ── */
.uqms-card {
    background-color: #FFFFFF !important;
    border: 1px solid #E5E5E5 !important;
    border-radius: 8px !important;
    padding: 1.25rem !important;
    margin-bottom: 1rem !important;
    box-shadow: none !important;
    transition: border-color 0.15s ease, background-color 0.15s ease !important;
}
.uqms-card:hover {
    border-color: #4F46E5 !important;
}

/* ── KPI metric ── */
.kpi { text-align: center !important; }
.kpi .value { font-size: 2.2rem !important; font-weight: 700 !important; margin-bottom: 4px !important; }
.kpi .label { font-size: 0.75rem !important; color: #6B6B6B !important; text-transform: uppercase !important; letter-spacing: 0.05em !important; font-weight: 500 !important; }

/* ── Status badges ── */
.badge {
    display: inline-block !important;
    padding: 4px 10px !important;
    border-radius: 6px !important;
    font-size: 12px !important;
    font-weight: 500 !important;
    text-transform: capitalize !important;
}
.badge-open {
    background-color: #EEF2FF !important;
    color: #4F46E5 !important;
    border: 1px solid #C7D2FE !important;
}
.badge-in_progress {
    background-color: #FEF3C7 !important;
    color: #D97706 !important;
    border: 1px solid #FDE68A !important;
}
.badge-resolved {
    background-color: #DCFCE7 !important;
    color: #16A34A !important;
    border: 1px solid #BBF7D0 !important;
}
.badge-closed {
    background-color: #F3F4F6 !important;
    color: #4B5563 !important;
    border: 1px solid #E5E5E5 !important;
}
.badge-escalated {
    background-color: #FEE2E2 !important;
    color: #DC2626 !important;
    border: 1px solid #FCA5A5 !important;
}
.badge-reopened {
    background-color: #F3E8FF !important;
    color: #7C3AED !important;
    border: 1px solid #E9D5FF !important;
}

/* ── Priority badges ── */
.prio-badge {
    display: inline-block !important;
    padding: 4px 10px !important;
    border-radius: 6px !important;
    font-size: 12px !important;
    font-weight: 500 !important;
    text-transform: capitalize !important;
    margin-left: 6px !important;
}
.prio-low { background-color: #F3F4F6 !important; color: #4B5563 !important; border: 1px solid #E5E5E5 !important; }
.prio-medium { background-color: #FEF3C7 !important; color: #D97706 !important; border: 1px solid #FDE68A !important; }
.prio-high { background-color: #FEE2E2 !important; color: #DC2626 !important; border: 1px solid #FCA5A5 !important; }
.prio-critical { background-color: #FEE2E2 !important; color: #DC2626 !important; border: 1px solid #EF4444 !important; font-weight: 600 !important; animation: pulse 2s infinite !important; }

@keyframes pulse {
    0% { opacity: 0.8; }
    50% { opacity: 1; }
    100% { opacity: 0.8; }
}

/* Custom Form & Input Styles */
div[data-baseweb="input"] {
    background-color: #F7F7F8 !important;
    border: 1px solid #E5E5E5 !important;
    border-radius: 6px !important;
    transition: border-color 0.15s ease, background-color 0.15s ease !important;
}
div[data-baseweb="input"]:focus-within {
    background-color: #FFFFFF !important;
    border-color: #4F46E5 !important;
}

/* Top Header Bar */
.uqms-topbar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 10px 0;
    border-bottom: 1px solid #E5E5E5;
    margin-bottom: 1.5rem;
}
.uqms-topbar-title {
    font-size: 14px;
    font-weight: 600;
    color: #1A1A1A;
}
.uqms-topbar-user {
    font-size: 13px;
    color: #6B6B6B;
}
</style>
"""

# ── Session init ───────────────────────────────────────────────────────────────
if "db" not in st.session_state:
    st.session_state.db = SessionLocal()
if "university" not in st.session_state:
    st.session_state.university = None
if "user" not in st.session_state:
    st.session_state.user = None

db = st.session_state.db

# ── Page config (must be first Streamlit call) ─────────────────────────────────
# We configure this globally in main.py. Config.toml themes do the styling.
st.logo("data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCIgZmlsbD0iIzRGNDZFNSIgd2lkdGg9IjQ4IiBoZWlnaHQ9IjQ4Ij48cGF0aCBkPSJNMTIgM0wxIDlsMTEgNiA5LTQuOTFWMTdoMlY5TDEyIDN6Ii8+PHBhdGggZD0iTTUgMTMuMTh2NGMwIDEuMS45IDIgMiAyaDEwYzEuMSAwIDItLjkgMi0ydi00bC03IDMuODItNy0zLjgyeiIvPjwvc3ZnPg==")

# ── Routing Helpers ────────────────────────────────────────────────────────────

def run_page(render_func):
    """Wrapper that injects global CSS style, renders the topbar, and runs page content."""
    # Apply CSS
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

    # Render top bar
    uni = st.session_state.university
    user = st.session_state.user
    if user is not None and uni is not None:
        role_label = user.role.value.title()
        st.markdown(
            f"<div class='uqms-topbar'>"
            f"<div class='uqms-topbar-title'>🏫 {uni.name}</div>"
            f"<div class='uqms-topbar-user'>Logged in as <b>{user.name}</b> ({role_label})</div>"
            f"</div>",
            unsafe_allow_html=True
        )
    else:
        st.markdown(
            f"<div class='uqms-topbar'>"
            f"<div class='uqms-topbar-title'>🎓 University Support Portal</div>"
            f"<div class='uqms-topbar-user'>Not Logged In</div>"
            f"</div>",
            unsafe_allow_html=True
        )

    # Render actual page function
    render_func()


def require_auth(role_required=None) -> bool:
    """Utility to guard pages that require authentication."""
    if st.session_state.user is None:
        return False
    if role_required and st.session_state.user.role != role_required:
        return False
    return True


def _show_login_page() -> None:
    """Render the central login card and Demo Quick Login dropdowns."""
    if st.session_state.user is not None:
        st.markdown("<div class='uqms-card' style='text-align: center;'>", unsafe_allow_html=True)
        st.markdown(
            f"<h3>Active Session Detected</h3>"
            f"<p style='color:#6B6B6B;'>You are currently signed in as <b>{st.session_state.user.name}</b> under <b>{st.session_state.university.name}</b>.</p>"
            f"<p style='color:#6B6B6B;'>Select any dashboard page in the sidebar navigation to continue.</p>",
            unsafe_allow_html=True
        )
        if st.button("🚪 Sign Out", key="btn_login_logout", use_container_width=True):
            for key in list(st.session_state.keys()):
                if key != "db":
                    del st.session_state[key]
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
        return

    st.markdown(
        "<h1 style='text-align:center;'>🎓 University QMS Portal</h1>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<p style='text-align:center;color:#6B6B6B;font-size:1.05rem;margin-bottom:1.5rem;'>"
        "Secure access to student support services and university administration."
        "</p>",
        unsafe_allow_html=True,
    )

    universities = AuthService.list_universities(db)
    if not universities:
        st.info("No universities found. Please seed the database.")
        return

    # Container Card
    st.markdown("<div class='uqms-card'>", unsafe_allow_html=True)
    
    # Dropdown to select university
    uni_names = [u.name for u in universities]
    selected_uni_name = st.selectbox("Select Your Institution", uni_names)
    uni = next(u for u in universities if u.name == selected_uni_name)
    
    # Tabs for login method
    login_tab1, login_tab2 = st.tabs(["🔐 Sign In", "📝 Register Student"])
    
    with login_tab1:
        email = st.text_input("University Email Address", placeholder="e.g. student@university.edu", key="login_email")
        password = st.text_input("Password", type="password", placeholder="••••••••", key="login_password")
        if st.button("Sign In", key="btn_manual_login", use_container_width=True):
            auth = AuthService(db)
            user = auth.authenticate(university_id=uni.id, email=email, password=password)
            if user:
                st.session_state.university = uni
                st.session_state.user = user
                st.success("Successfully logged in!")
                st.rerun()
            else:
                st.error("Invalid email or password for the selected institution.")
                
    with login_tab2:
        st.markdown("<h4 style='margin-top:0;'>Create Student Account</h4>", unsafe_allow_html=True)
        reg_name = st.text_input("Full Name", placeholder="e.g. Jane Student", key="reg_name")
        reg_email = st.text_input("University Email Address", placeholder="e.g. jane@greenfield.edu", key="reg_email")
        
        # Select student's department/academic program
        depts = uni.departments or ["General"]
        reg_dept = st.selectbox("Department / Academic Program", options=depts, key="reg_dept")
        
        reg_password = st.text_input("Password", type="password", placeholder="Minimum 6 characters", key="reg_password")
        reg_password_confirm = st.text_input("Confirm Password", type="password", placeholder="••••••••", key="reg_password_confirm")
        
        if st.button("Register & Log In", key="btn_student_register", use_container_width=True):
            errors = []
            if not reg_name.strip():
                errors.append("Full Name is required.")
            if not reg_email.strip():
                errors.append("Email Address is required.")
            elif "@" not in reg_email or "." not in reg_email.split("@")[-1]:
                errors.append("Invalid email address format.")
            if len(reg_password) < 6:
                errors.append("Password must be at least 6 characters.")
            if reg_password != reg_password_confirm:
                errors.append("Passwords do not match.")
            
            if errors:
                for e in errors:
                    st.error(f"⚠️ {e}")
            else:
                try:
                    auth = AuthService(db)
                    new_user = auth.register_user(
                        university_id=uni.id,
                        name=reg_name.strip(),
                        email=reg_email.strip(),
                        password=reg_password,
                        role=UserRole.student,
                        department=reg_dept,
                    )
                    st.session_state.university = uni
                    st.session_state.user = new_user
                    st.success("🎉 Account created successfully! Logging you in...")
                    st.rerun()
                except ValueError as ve:
                    st.error(f"⚠️ {ve}")
                except Exception as ex:
                    st.error(f"⚠️ Error creating account: {ex}")
    
    st.markdown("</div>", unsafe_allow_html=True)

# ── Page Definitions ─────────────────────────────────────────────────────────

def page_portal_login():
    run_page(_show_login_page)

def page_admin_dashboard():
    def _run():
        import importlib
        if require_auth(UserRole.admin):
            from app.pages import admin_dashboard
            importlib.reload(admin_dashboard)
            admin_dashboard.render(db, st.session_state.university, st.session_state.user)
        else:
            st.markdown("<div class='uqms-card'>", unsafe_allow_html=True)
            st.markdown(
                "<h3>🔒 Admin Dashboard Access Restricted</h3>"
                "<p style='color:#6B6B6B;'>Please log in as an administrator on the <b>Portal Login</b> page to access this dashboard.</p>",
                unsafe_allow_html=True
            )
            st.markdown("</div>", unsafe_allow_html=True)
            _show_login_page()
    run_page(_run)

def page_student_dashboard():
    def _run():
        import importlib
        if require_auth(UserRole.student):
            from app.pages import student_dashboard
            importlib.reload(student_dashboard)
            student_dashboard.render(db, st.session_state.university, st.session_state.user)
        else:
            st.markdown("<div class='uqms-card'>", unsafe_allow_html=True)
            st.markdown(
                "<h3>🔒 Student Dashboard Access Restricted</h3>"
                "<p style='color:#6B6B6B;'>Please log in as a student on the <b>Portal Login</b> page to access this dashboard.</p>",
                unsafe_allow_html=True
            )
            st.markdown("</div>", unsafe_allow_html=True)
            _show_login_page()
    run_page(_run)

def page_rag_chat():
    def _run():
        import importlib
        if require_auth():
            from app.pages import rag_chat_page
            importlib.reload(rag_chat_page)
            rag_chat_page.render(st.session_state.university, st.session_state.user)
        else:
            st.markdown("<div class='uqms-card'>", unsafe_allow_html=True)
            st.markdown(
                "<h3>🔒 Chat Access Restricted</h3>"
                "<p style='color:#6B6B6B;'>Please log in on the <b>Portal Login</b> page to access the RAG AI chatbot.</p>",
                unsafe_allow_html=True
            )
            st.markdown("</div>", unsafe_allow_html=True)
            _show_login_page()
    run_page(_run)

def page_document_upload():
    def _run():
        import importlib
        if require_auth(UserRole.admin):
            from app.pages import document_upload
            importlib.reload(document_upload)
            document_upload.render(db, st.session_state.university, st.session_state.user)
        else:
            st.markdown("<div class='uqms-card'>", unsafe_allow_html=True)
            st.markdown(
                "<h3>🔒 Document Upload Restricted</h3>"
                "<p style='color:#6B6B6B;'>Please log in as an administrator on the <b>Portal Login</b> page to upload knowledge base documents.</p>",
                unsafe_allow_html=True
            )
            st.markdown("</div>", unsafe_allow_html=True)
            _show_login_page()
    run_page(_run)

def page_onboarding():
    def _run():
        import importlib
        from app.pages import onboarding
        importlib.reload(onboarding)
        onboarding.render(db)
    run_page(_run)

# ── Navigation Definition ─────────────────────────────────────────────────────

# Define pages for st.navigation
login_pg = st.Page(page_portal_login, title="Portal Login", icon="🔒")
admin_pg = st.Page(page_admin_dashboard, title="Admin Dashboard", icon="📊")
student_pg = st.Page(page_student_dashboard, title="Student Dashboard", icon="📋")
rag_pg = st.Page(page_rag_chat, title="RAG Chat", icon="💬")
upload_pg = st.Page(page_document_upload, title="Document Upload", icon="📤")
onboarding_pg = st.Page(page_onboarding, title="Onboarding", icon="🌱")

# Build navigation dynamically based on user authentication state and role
pages_to_show = [login_pg]

current_user = st.session_state.user
if current_user is None:
    # Not logged in: show login and onboarding
    pages_to_show.append(onboarding_pg)
elif current_user.role == UserRole.student:
    # Logged in as student: show student dashboard and RAG chat
    pages_to_show.extend([student_pg, rag_pg])
elif current_user.role == UserRole.admin:
    # Logged in as admin: show admin dashboard, RAG chat, and document upload
    pages_to_show.extend([admin_pg, rag_pg, upload_pg])

pg = st.navigation(pages_to_show)

# Render branding above navigation menu
st.sidebar.markdown(
    "<div style='padding: 0.5rem 0 1rem 0; border-bottom: 1px solid #E5E5E5; margin-bottom: 1rem;'>"
    "<h2 style='margin: 0; color: #1A1A1A; font-size: 1.3rem; font-weight: 700; display: flex; align-items: center; gap: 8px;'>"
    "🎓 University Portal"
    "</h2>"
    "</div>",
    unsafe_allow_html=True
)

# Run navigation
pg.run()

# Render User profile at bottom of sidebar
if st.session_state.user is not None:
    uni = st.session_state.university
    user = st.session_state.user
    role_color = "#4F46E5" if user.role == UserRole.admin else "#D97706"
    
    st.sidebar.markdown("<hr style='border:0; border-top:1px solid #E5E5E5; margin: 1rem 0;'>", unsafe_allow_html=True)
    dept_info = f" &bull; {user.department}" if getattr(user, 'department', None) else ""
    st.sidebar.markdown(
        f"<div class='uqms-card' style='padding: 12px; margin-bottom: 12px; border-radius: 8px; background-color: #FFFFFF; border: 1px solid #E5E5E5;'>"
        f"<p style='margin: 0; font-size: 0.75rem; color: #6B6B6B; text-transform: uppercase; font-weight:600;'>{uni.name}</p>"
        f"<h4 style='margin: 4px 0 2px 0; color: #1A1A1A; font-size: 0.95rem; font-weight:600;'>{user.name}</h4>"
        f"<p style='margin: 0; font-size: 0.8rem; color: {role_color}; font-weight:500;'>{user.role.value.upper()}{dept_info}</p>"
        f"</div>",
        unsafe_allow_html=True,
    )
    if st.sidebar.button("🚪 Sign Out", key="sidebar_sign_out", use_container_width=True):
        # Clear session state keys except db
        for key in list(st.session_state.keys()):
            if key != "db":
                del st.session_state[key]
        st.rerun()
