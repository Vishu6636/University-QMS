# app/main.py
"""
app/main.py — Entry point for the University Query Management System Streamlit app.
Redesigned with SaaS-grade aesthetics (Notion/Linear style) and modern st.navigation.
"""

import sys
import os
import base64

# Force pure-python protobuf implementation to prevent opentelemetry/chromadb TypeError conflicts on deployment
os.environ["PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION"] = "python"

# ── Sentry error monitoring (free tier) ────────────────────────────────────────
# Initialise BEFORE any other imports so the SDK can hook into exception handling.
try:
    import sentry_sdk
    _sentry_dsn = os.getenv("SENTRY_DSN")
    if _sentry_dsn:
        sentry_sdk.init(
            dsn=_sentry_dsn,
            traces_sample_rate=0.1,
            environment=os.getenv("SENTRY_ENV", "production"),
        )
except ImportError:
    pass  # sentry-sdk not installed — monitoring disabled

# Add project root to sys.path so all imports resolve from any working directory.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import streamlit as st
from models.base import Base, engine, SessionLocal
from models.university import University
from models.user import User, UserRole
from models.ticket import Ticket
from models.kb_document import KBDocument
from models.feedback import Feedback
from models.lead import Lead
from models.audit_log import AuditLog
from services.auth_service import AuthService, validate_password
from services.rate_limiter import login_limiter, registration_limiter

# Ensure data directory exists
db_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data"))
os.makedirs(db_dir, exist_ok=True)
ASSETS_DIR = os.path.join(os.path.dirname(__file__), "assets")
LOGO_PATH = os.path.join(ASSETS_DIR, "uqms_logo.svg")
WORDMARK_PATH = os.path.join(ASSETS_DIR, "uqms_wordmark.svg")

INLINE_ICONS = {
    "building": "<svg viewBox='0 0 24 24' aria-hidden='true'><path d='M4 21h16M6 21V7l6-4 6 4v14M9 21v-6h6v6M9 10h.01M15 10h.01' /></svg>",
    "portal": "<svg viewBox='0 0 24 24' aria-hidden='true'><path d='M4 20h16M6 20V8l6-4 6 4v12M9 12h6M9 16h6' /></svg>",
}


def icon_svg(name: str) -> str:
    """Return an inline icon span for HTML-rendered chrome."""
    svg = INLINE_ICONS.get(name, "")
    return f"<span class='uqms-inline-icon'>{svg}</span>" if svg else ""

# Create all tables in SQLite if they don't exist
Base.metadata.create_all(bind=engine)

# Auto-seed database if empty
db_inst = SessionLocal()
try:
    if db_inst.query(University).count() == 0:
        from scripts.db_init import seed_demo_data
        seed_demo_data()
    # Check and add resolution_text column if it doesn't exist
    from sqlalchemy import inspect, text
    inspector = inspect(engine)
    if "tickets" in inspector.get_table_names():
        columns = [col["name"] for col in inspector.get_columns("tickets")]
        if "resolution_text" not in columns:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE tickets ADD COLUMN resolution_text TEXT"))
finally:
    db_inst.close()

# Hourglass SVG from Uiverse.io by nima-mollazadeh
hourglass_svg = """<svg aria-label="loader being flipped clockwise and circled by three white curves fading in and out" role="img" height="56px" width="56px" viewBox="0 0 56 56" class="loader" xmlns="http://www.w3.org/2000/svg">
  <style>
    svg {
      --dur: 2s;
      --hue: 244;
    }
    .loader__glare-top,
    .loader__glare-bottom,
    .loader__model,
    .loader__motion-thick,
    .loader__motion-medium,
    .loader__motion-thin,
    .loader__sand-drop,
    .loader__sand-fill,
    .loader__sand-grain-left,
    .loader__sand-grain-right,
    .loader__sand-line-left,
    .loader__sand-line-right,
    .loader__sand-mound-top,
    .loader__sand-mound-bottom {
      animation-duration: var(--dur);
      animation-timing-function: cubic-bezier(0.83, 0, 0.17, 1);
      animation-iteration-count: infinite;
    }
    .loader__glare-top { animation-name: glare-top; }
    .loader__glare-bottom { animation-name: glare-bottom; }
    .loader__model {
      animation-name: loader-flip;
      transform-origin: 12.25px 16.75px;
    }
    .loader__motion-thick,
    .loader__motion-medium,
    .loader__motion-thin { transform-origin: 26px 26px; }
    .loader__motion-thick { animation-name: motion-thick; }
    .loader__motion-medium { animation-name: motion-medium; }
    .loader__motion-thin { animation-name: motion-thin; }
    .loader__sand-drop { animation-name: sand-drop; }
    .loader__sand-fill { animation-name: sand-fill; }
    .loader__sand-grain-left { animation-name: sand-grain-left; }
    .loader__sand-grain-right { animation-name: sand-grain-right; }
    .loader__sand-line-left { animation-name: sand-line-left; }
    .loader__sand-line-right { animation-name: sand-line-right; }
    .loader__sand-mound-top { animation-name: sand-mound-top; }
    .loader__sand-mound-bottom {
      animation-name: sand-mound-bottom;
      transform-origin: 12.25px 31.5px;
    }

    @keyframes loader-flip {
      from { transform: translate(13.75px, 9.25px) rotate(-180deg); }
      24%, to { transform: translate(13.75px, 9.25px) rotate(0); }
    }
    @keyframes glare-top {
      from { stroke: rgba(255, 255, 255, 0); }
      24%, to { stroke: white; }
    }
    @keyframes glare-bottom {
      from { stroke: white; }
      24%, to { stroke: rgba(255, 255, 255, 0); }
    }
    @keyframes motion-thick {
      from {
        animation-timing-function: cubic-bezier(0.33, 0, 0.67, 0);
        stroke: rgba(255, 255, 255, 0);
        stroke-dashoffset: 153.94;
        transform: rotate(0.67turn);
      }
      20% {
        animation-timing-function: cubic-bezier(0.33, 1, 0.67, 1);
        stroke: rgb(32, 32, 32);
        stroke-dashoffset: 141.11;
        transform: rotate(1turn);
      }
      40%, to {
        stroke: rgba(255, 255, 255, 0);
        stroke-dashoffset: 153.94;
        transform: rotate(1.33turn);
      }
    }
    @keyframes motion-medium {
      from, 8% {
        animation-timing-function: cubic-bezier(0.33, 0, 0.67, 0);
        stroke: rgba(255, 255, 255, 0);
        stroke-dashoffset: 153.94;
        transform: rotate(0.5turn);
      }
      20% {
        animation-timing-function: cubic-bezier(0.33, 1, 0.67, 1);
        stroke: white;
        stroke-dashoffset: 147.53;
        transform: rotate(0.83turn);
      }
      32%, to {
        stroke: rgba(255, 255, 255, 0);
        stroke-dashoffset: 153.94;
        transform: rotate(1.17turn);
      }
    }
    @keyframes motion-thin {
      from, 4% {
        animation-timing-function: cubic-bezier(0.33, 0, 0.67, 0);
        stroke: rgba(255, 255, 255, 0);
        stroke-dashoffset: 153.94;
        transform: rotate(0.33turn);
      }
      24% {
        animation-timing-function: cubic-bezier(0.33, 1, 0.67, 1);
        stroke: rgb(53, 53, 53);
        stroke-dashoffset: 134.7;
        transform: rotate(0.67turn);
      }
      44%, to {
        stroke: rgba(255, 255, 255, 0);
        stroke-dashoffset: 153.94;
        transform: rotate(1turn);
      }
    }
    @keyframes sand-drop {
      from, 10% {
        animation-timing-function: cubic-bezier(0.12, 0, 0.39, 0);
        stroke-dashoffset: 1;
      }
      70%, to { stroke-dashoffset: -107; }
    }
    @keyframes sand-fill {
      from, 10% {
        animation-timing-function: cubic-bezier(0.12, 0, 0.39, 0);
        stroke-dashoffset: 55;
      }
      70%, to { stroke-dashoffset: -54; }
    }
    @keyframes sand-grain-left {
      from, 10% {
        animation-timing-function: cubic-bezier(0.12, 0, 0.39, 0);
        stroke-dashoffset: 29;
      }
      70%, to { stroke-dashoffset: -22; }
    }
    @keyframes sand-grain-right {
      from, 10% {
        animation-timing-function: cubic-bezier(0.12, 0, 0.39, 0);
        stroke-dashoffset: 27;
      }
      70%, to { stroke-dashoffset: -24; }
    }
    @keyframes sand-line-left {
      from, 10% {
        animation-timing-function: cubic-bezier(0.12, 0, 0.39, 0);
        stroke-dashoffset: 53;
      }
      70%, to { stroke-dashoffset: -55; }
    }
    @keyframes sand-line-right {
      from, 10% {
        animation-timing-function: cubic-bezier(0.12, 0, 0.39, 0);
        stroke-dashoffset: 14;
      }
      70%, to { stroke-dashoffset: -24.5; }
    }
    @keyframes sand-mound-top {
      from, 10% {
        animation-timing-function: linear;
        transform: translate(0, 0);
      }
      15% {
        animation-timing-function: cubic-bezier(0.12, 0, 0.39, 0);
        transform: translate(0, 1.5px);
      }
      51%, to { transform: translate(0, 13px); }
    }
    @keyframes sand-mound-bottom {
      from, 31% {
        animation-timing-function: cubic-bezier(0.61, 1, 0.88, 1);
        transform: scale(1, 0);
      }
      56%, to { transform: scale(1, 1); }
    }
  </style>
  <clipPath id="sand-mound-top">
    <path d="M 14.613 13.087 C 15.814 12.059 19.3 8.039 20.3 6.539 C 21.5 4.789 21.5 2.039 21.5 2.039 L 3 2.039 C 3 2.039 3 4.789 4.2 6.539 C 5.2 8.039 8.686 12.059 9.887 13.087 C 11 14.039 12.25 14.039 12.25 14.039 C 12.25 14.039 13.5 14.039 14.613 13.087 Z" class="loader__sand-mound-top"></path>
  </clipPath>
  <clipPath id="sand-mound-bottom">
    <path d="M 14.613 20.452 C 15.814 21.48 19.3 25.5 20.3 27 C 21.5 28.75 21.5 31.5 21.5 31.5 L 3 31.5 C 3 31.5 3 28.75 4.2 27 C 5.2 25.5 8.686 21.48 9.887 20.452 C 11 19.5 12.25 19.5 12.25 19.5 C 12.25 19.5 13.5 19.5 14.613 20.452 Z" class="loader__sand-mound-bottom"></path>
  </clipPath>
  <g transform="translate(2,2)">
    <g transform="rotate(-90,26,26)" stroke-linecap="round" stroke-dashoffset="153.94" stroke-dasharray="153.94 153.94" stroke="hsl(0,0%,100%)" fill="none">
      <circle transform="rotate(0,26,26)" r="24.5" cy="26" cx="26" stroke-width="2.5" class="loader__motion-thick"></circle>
      <circle transform="rotate(90,26,26)" r="24.5" cy="26" cx="26" stroke-width="1.75" class="loader__motion-medium"></circle>
      <circle transform="rotate(180,26,26)" r="24.5" cy="26" cx="26" stroke-width="1" class="loader__motion-thin"></circle>
    </g>
    <g transform="translate(13.75,9.25)" class="loader__model">
      <path d="M 1.5 2 L 23 2 C 23 2 22.5 8.5 19 12 C 16 15.5 13.5 13.5 13.5 16.75 C 13.5 20 16 18 19 21.5 C 22.5 25 23 31.5 23 31.5 L 1.5 31.5 C 1.5 31.5 2 25 5.5 21.5 C 8.5 18 11 20 11 16.75 C 11 13.5 8.5 15.5 5.5 12 C 2 8.5 1.5 2 1.5 2 Z" fill="hsl(var(--hue),90%,85%)"></path>

      <g stroke-linecap="round" stroke="hsl(35,90%,90%)">
        <line y2="20.75" x2="12" y1="15.75" x1="12" stroke-dasharray="0.25 33.75" stroke-width="1" class="loader__sand-grain-left"></line>
        <line y2="21.75" x2="12.5" y1="16.75" x1="12.5" stroke-dasharray="0.25 33.75" stroke-width="1" class="loader__sand-grain-right"></line>
        <line y2="31.5" x2="12.25" y1="18" x1="12.25" stroke-dasharray="0.5 107.5" stroke-width="1" class="loader__sand-drop"></line>
        <line y2="31.5" x2="12.25" y1="14.75" x1="12.25" stroke-dasharray="54 54" stroke-width="1.5" class="loader__sand-fill"></line>
        <line y2="31.5" x2="12" y1="16" x1="12" stroke-dasharray="1 107" stroke-width="1" stroke="hsl(35,90%,83%)" class="loader__sand-line-left"></line>
        <line y2="31.5" x2="12.5" y1="16" x1="12.5" stroke-dasharray="12 96" stroke-width="1" stroke="hsl(35,90%,83%)" class="loader__sand-line-right"></line>

        <g stroke-width="0" fill="hsl(35,90%,90%)">
          <path d="M 12.25 15 L 15.392 13.486 C 21.737 11.168 22.5 2 22.5 2 L 2 2.013 C 2 2.013 2.753 11.046 9.009 13.438 L 12.25 15 Z" clip-path="url(#sand-mound-top)"></path>
          <path d="M 12.25 18.5 L 15.392 20.014 C 21.737 22.332 22.5 31.5 22.5 31.5 L 2 31.487 C 2 31.487 2.753 22.454 9.009 20.062 Z" clip-path="url(#sand-mound-bottom)"></path>
        </g>
      </g>

      <g stroke-width="2" stroke-linecap="round" opacity="0.7" fill="none">
        <path d="M 19.437 3.421 C 19.437 3.421 19.671 6.454 17.914 8.846 C 16.157 11.238 14.5 11.5 14.5 11.5" stroke="hsl(0,0%,100%)" class="loader__glare-top"></path>
        <path transform="rotate(180,12.25,16.75)" d="M 19.437 3.421 C 19.437 3.421 19.671 6.454 17.914 8.846 C 16.157 11.238 14.5 11.5 14.5 11.5" stroke="hsla(0,0%,100%,0)" class="loader__glare-bottom"></path>
      </g>

      <rect height="2" width="24.5" fill="hsl(var(--hue),90%,50%)"></rect>
      <rect height="1" width="19.5" y="0.5" x="2.5" ry="0.5" rx="0.5" fill="hsl(var(--hue),90%,57.5%)"></rect>
      <rect height="2" width="24.5" y="31.5" fill="hsl(var(--hue),90%,50%)"></rect>
      <rect height="1" width="19.5" y="32" x="2.5" ry="0.5" rx="0.5" fill="hsl(var(--hue),90%,57.5%)"></rect>
    </g>
  </g>
</svg>"""
hourglass_b64 = base64.b64encode(hourglass_svg.encode()).decode()


# ── Custom CSS for light, premium theme ────────────────────────────────────────
CUSTOM_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif !important;
}

/* ── Main App Background ── */
.stApp {
    background-color: transparent !important;
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
    transition: background-color 160ms ease-out, transform 160ms ease-out, color 160ms ease-out !important;
    transform: translateX(0);
}
[data-testid="stSidebar"] a:hover {
    background-color: #FFFFFF !important;
    color: #1A1A1A !important;
    transform: translateX(2px) !important;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05) !important;
    border: 1px solid #E5E5E5 !important;
}
[data-testid="stSidebar"] a[aria-current="page"] {
    background-color: #EEF2FF !important;
    color: #4F46E5 !important;
    border-left: 3px solid #4F46E5 !important;
    font-weight: 600 !important;
    box-shadow: 0 2px 4px rgba(79, 70, 229, 0.08) !important;
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
.uqms-inline-icon {
    display: inline-flex;
    width: 1em;
    height: 1em;
    margin-right: 0.45rem;
    vertical-align: -0.14em;
    color: currentColor;
}
.uqms-inline-icon svg {
    width: 1em;
    height: 1em;
    fill: none;
    stroke: currentColor;
    stroke-width: 2;
    stroke-linecap: round;
    stroke-linejoin: round;
}

/* ── Custom Loading Indicators ── */

/* 1. Hourglass Loader (Landing page ONLY) */
.stApp:has(.bg-landing) .stSpinner {
    position: relative !important;
    padding-top: 80px !important;
    text-align: center !important;
}
.stApp:has(.bg-landing) .stSpinner > div:first-child {
    display: none !important;
}
.stApp:has(.bg-landing) .stSpinner svg {
    display: none !important;
}
.stApp:has(.bg-landing) .stSpinner::before {
    content: "" !important;
    position: absolute !important;
    top: 10px !important;
    left: calc(50% - 28px) !important;
    width: 56px !important;
    height: 56px !important;
    background-image: url('data:image/svg+xml;base64,{hourglass_b64}') !important;
    background-size: contain !important;
    background-repeat: no-repeat !important;
}

/* 2. Bouncing-Dots/Steps Loader (everywhere AFTER login) */
.stApp:not(:has(.bg-landing)) .stSpinner {
    position: relative !important;
    height: 150px !important;
    padding-top: 130px !important;
    text-align: center !important;
}
.stApp:not(:has(.bg-landing)) .stSpinner > div:first-child {
    display: none !important;
}
.stApp:not(:has(.bg-landing)) .stSpinner svg {
    display: none !important;
}
.stApp:not(:has(.bg-landing)) .stSpinner::before {
    content: "" !important;
    position: absolute !important;
    bottom: 30px !important;
    left: calc(50% - 15px) !important;
    height: 30px !important;
    width: 30px !important;
    border-radius: 50% !important;
    background: #4F46E5 !important;
    animation: loading-bounce 0.5s ease-in-out infinite alternate !important;
}
.stApp:not(:has(.bg-landing)) .stSpinner::after {
    content: "" !important;
    position: absolute !important;
    top: 50px !important;
    left: calc(50% + 5px) !important;
    height: 7px !important;
    width: 45px !important;
    border-radius: 4px !important;
    box-shadow: 0 5px 0 #e5e5e5, -35px 50px 0 #e5e5e5, -70px 95px 0 #e5e5e5 !important;
    animation: loading-step 1s ease-in-out infinite !important;
}

@keyframes loading-bounce {
  0% { transform: scale(1, 0.7); }
  40% { transform: scale(0.8, 1.2); }
  60% { transform: scale(1, 1); }
  100% { bottom: 140px; }
}
@keyframes loading-step {
  0% {
    box-shadow: 0 10px 0 rgba(0, 0, 0, 0),
      0 10px 0 #e5e5e5,
      -35px 50px 0 #e5e5e5,
      -70px 90px 0 #e5e5e5;
  }
  100% {
    box-shadow: 0 10px 0 #e5e5e5,
      -35px 50px 0 #e5e5e5,
      -70px 90px 0 #e5e5e5,
      -70px 90px 0 rgba(0, 0, 0, 0);
  }
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

# ── Session timeout ────────────────────────────────────────────────────────────
from datetime import datetime, timezone, timedelta

SESSION_TIMEOUT_MINUTES = int(os.getenv("SESSION_TIMEOUT_MINUTES", "30"))

if "last_activity" not in st.session_state:
    st.session_state.last_activity = datetime.now(timezone.utc)

if st.session_state.user is not None and st.session_state.user.role == UserRole.student:
    elapsed = datetime.now(timezone.utc) - st.session_state.last_activity
    if elapsed > timedelta(minutes=SESSION_TIMEOUT_MINUTES):
        # Clear session (except db handle)
        for key in list(st.session_state.keys()):
            if key != "db":
                del st.session_state[key]
        st.toast("Session expired due to inactivity. Please sign in again.")

# Update last activity timestamp on every page load
st.session_state.last_activity = datetime.now(timezone.utc)

db = st.session_state.db

# ── Page config (must be first Streamlit call) ─────────────────────────────────
# We configure this globally in main.py. Config.toml themes do the styling.
st.logo(LOGO_PATH)

# ── Routing Helpers ────────────────────────────────────────────────────────────

def get_image_path(filename: str) -> str:
    path = os.path.join(os.path.dirname(__file__), "assets", "backgrounds", filename)
    if not os.path.exists(path):
        path = os.path.join(os.path.dirname(__file__), "assets", filename)
    return path

@st.cache_data
def get_base64_image(filename: str, mtime: float) -> str:
    path = get_image_path(filename)
    try:
        with open(path, "rb") as f:
            encoded = base64.b64encode(f.read()).decode()
            return f"data:image/webp;base64,{encoded}"
    except Exception as e:
        return ""

def get_background_css() -> str:
    def load_bg(filename: str) -> str:
        path = get_image_path(filename)
        mtime = os.path.getmtime(path) if os.path.exists(path) else 0.0
        return get_base64_image(filename, mtime)

    bg_landing = load_bg("bg_landing.webp")
    bg_onboarding = load_bg("bg_onboarding.webp")
    bg_public_inquiry = load_bg("bg_public_inquiry.webp")
    bg_super_admin = load_bg("bg_super_admin.webp")
    bg_admin = load_bg("bg_admin.webp")
    bg_student = load_bg("bg_student.webp")

    css = f"""
<style>
/* ── Page Backgrounds using :has() selector ── */
.stApp:has(.bg-landing) {{
    background-image: linear-gradient(rgba(255,255,255,0.90), rgba(255,255,255,0.93)), url('{bg_landing}') !important;
    background-size: cover !important;
    background-attachment: fixed !important;
    background-position: center !important;
}}
.stApp:has(.bg-onboarding) {{
    background-image: linear-gradient(rgba(255,255,255,0.90), rgba(255,255,255,0.93)), url('{bg_onboarding}') !important;
    background-size: cover !important;
    background-attachment: fixed !important;
    background-position: center !important;
}}
.stApp:has(.bg-public-inquiry) {{
    background-image: linear-gradient(rgba(255,255,255,0.90), rgba(255,255,255,0.93)), url('{bg_public_inquiry}') !important;
    background-size: cover !important;
    background-attachment: fixed !important;
    background-position: center !important;
}}
.stApp:has(.bg-super-admin) {{
    background-image: linear-gradient(rgba(255,255,255,0.90), rgba(255,255,255,0.93)), url('{bg_super_admin}') !important;
    background-size: cover !important;
    background-attachment: fixed !important;
    background-position: center !important;
}}
.stApp:has(.bg-admin) {{
    background-image: linear-gradient(rgba(255,255,255,0.90), rgba(255,255,255,0.93)), url('{bg_admin}') !important;
    background-size: cover !important;
    background-attachment: fixed !important;
    background-position: center !important;
}}
.stApp:has(.bg-student) {{
    background-image: linear-gradient(rgba(255,255,255,0.90), rgba(255,255,255,0.93)), url('{bg_student}') !important;
    background-size: cover !important;
    background-attachment: fixed !important;
    background-position: center !important;
}}

/* Ensure all cards, forms, and tables sit as opaque solid white surfaces */
.uqms-card, div[data-testid="stForm"], div[data-testid="stTable"] {{
    background-color: #FFFFFF !important;
    border: 1px solid #E5E5E5 !important;
    opacity: 1.0 !important;
}}
</style>
"""
    return css


def run_page(render_func, bg_class: str = "bg-landing"):
    """Wrapper that injects global CSS style, renders the topbar, and runs page content."""
    # Render background marker
    st.markdown(f"<div class='bg-marker {bg_class}'></div>", unsafe_allow_html=True)

    # Apply CSS
    st.markdown(CUSTOM_CSS.replace("{hourglass_b64}", hourglass_b64), unsafe_allow_html=True)
    st.markdown(get_background_css(), unsafe_allow_html=True)

    # Render top bar
    uni = st.session_state.university
    user = st.session_state.user
    if user is not None and uni is not None:
        role_label = user.role.value.title()
        st.markdown(
            f"<div class='uqms-topbar'>"
            f"<div class='uqms-topbar-title'>{icon_svg('building')}{uni.name}</div>"
            f"<div class='uqms-topbar-user'>Logged in as <b>{user.name}</b> ({role_label})</div>"
            f"</div>",
            unsafe_allow_html=True
        )
    else:
        st.markdown(
            f"<div class='uqms-topbar'>"
            f"<div class='uqms-topbar-title'>{icon_svg('portal')}University Support Portal</div>"
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
        uni_str = f"under <b>{st.session_state.university.name}</b>" if st.session_state.university else "under <b>System Console</b>"
        st.markdown("<div class='uqms-card' style='text-align: center;'>", unsafe_allow_html=True)
        st.markdown(
            f"<h3>Active Session Detected</h3>"
            f"<p style='color:#6B6B6B;'>You are currently signed in as <b>{st.session_state.user.name}</b> {uni_str}.</p>"
            f"<p style='color:#6B6B6B;'>Select any dashboard page in the sidebar navigation to continue.</p>",
            unsafe_allow_html=True
        )
        if st.button("Sign Out", key="btn_login_logout", use_container_width=True):
            for key in list(st.session_state.keys()):
                if key != "db":
                    del st.session_state[key]
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
        return

    st.markdown(
        "<h1 style='text-align:center;'>University QMS Portal</h1>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<p style='text-align:center;color:#6B6B6B;font-size:1.05rem;margin-bottom:1.5rem;'>"
        "Secure access to student support services and university administration."
        "</p>",
        unsafe_allow_html=True,
    )

    universities = [u for u in AuthService.list_universities(db) if u.status != "rejected"]
    if not universities:
        st.info("No universities found. Please seed the database.")
        return

    # Public inquiry entry point — prominent link before the login card
    st.markdown(
        "<div class='uqms-card' style='text-align:center; background: linear-gradient(135deg, #EEF2FF 0%, #E0E7FF 100%); border: 1px solid #C7D2FE;'>"
        "<p style='margin:0 0 4px 0; font-size:15px; font-weight:600; color:#4F46E5;'>Public Inquiry</p>"
        "<p style='margin:0; font-size:13px; color:#6B6B6B;'>"
        "No account needed — explore any university's knowledge base via the "
        "<b>Public Inquiry</b> page in the sidebar."
        "</p>"
        "</div>",
        unsafe_allow_html=True,
    )

    # Container Card
    st.markdown("<div class='uqms-card'>", unsafe_allow_html=True)
    
    # Dropdown to select university
    uni_names = [u.name for u in universities]
    selected_uni_name = st.selectbox("Select Your Institution", uni_names)
    uni = next(u for u in universities if u.name == selected_uni_name)
    
    # Tabs for login method
    login_tab1, login_tab2 = st.tabs(["Sign In", "Register Student"])
    
    with login_tab1:
        email = st.text_input("University Email Address", placeholder="e.g. student@university.edu", key="login_email")
        password = st.text_input("Password", type="password", placeholder="••••••••", key="login_password")
        if st.button("Sign In", key="btn_manual_login", use_container_width=True):
            # ── Rate limit check ──
            allowed, retry_after = login_limiter.record_attempt(email)
            if not allowed:
                minutes_left = max(1, retry_after // 60)
                st.error(
                    f"Too many login attempts. "
                    f"Please try again in {minutes_left} minute{'s' if minutes_left != 1 else ''}."
                )
            else:
                auth = AuthService(db)
                user = auth.authenticate(university_id=uni.id, email=email, password=password)
                if user:
                    login_limiter.reset(email)  # Clear limit on success
                    if user.role == UserRole.super_admin:
                        st.session_state.university = None
                        st.session_state.user = user
                        st.success("Successfully logged in as Super Admin!")
                        st.rerun()
                    else:
                        user_uni = user.university
                        if not user_uni:
                            st.error("Associated university not found.")
                        elif user_uni.status == "pending":
                            st.warning("Your university registration is under review. You'll receive access once approved.")
                        elif user_uni.status == "rejected":
                            st.error("Your university registration request has been rejected.")
                        elif user_uni.status == "approved":
                            st.session_state.university = user_uni
                            st.session_state.user = user
                            st.success("Successfully logged in!")
                            st.rerun()
                        else:
                            st.error(f"Access restricted. Institution status: {user_uni.status}")
                else:
                    st.error("Invalid email or password for the selected institution.")
                
    with login_tab2:
        st.markdown("<h4 style='margin-top:0;'>Create Student Account</h4>", unsafe_allow_html=True)
        reg_name = st.text_input("Full Name", placeholder="e.g. Jane Student", key="reg_name")
        reg_email = st.text_input("University Email Address", placeholder="e.g. jane@greenfield.edu", key="reg_email")
        
        # Select student's department/academic program
        depts = uni.departments or ["General"]
        reg_dept = st.selectbox("Department / Academic Program", options=depts, key="reg_dept")
        
        reg_password = st.text_input("Password", type="password", placeholder="Min 8 chars, at least 1 number", key="reg_password")
        reg_password_confirm = st.text_input("Confirm Password", type="password", placeholder="••••••••", key="reg_password_confirm")
        
        if st.button("Register & Log In", key="btn_student_register", use_container_width=True):
            errors = []
            if not reg_name.strip():
                errors.append("Full Name is required.")
            if not reg_email.strip():
                errors.append("Email Address is required.")
            elif "@" not in reg_email or "." not in reg_email.split("@")[-1]:
                errors.append("Invalid email address format.")
            try:
                validate_password(reg_password)
            except ValueError as pw_err:
                errors.append(str(pw_err))
            if reg_password != reg_password_confirm:
                errors.append("Passwords do not match.")
            
            if errors:
                for e in errors:
                    st.error(str(e))
            else:
                # ── Rate limit check ──
                allowed, retry_after = registration_limiter.record_attempt(reg_email)
                if not allowed:
                    minutes_left = max(1, retry_after // 60)
                    st.error(
                        f"Too many registration attempts. "
                        f"Please try again in {minutes_left} minute{'s' if minutes_left != 1 else ''}."
                    )
                else:
                    try:
                        auth = AuthService(db)
                        # Pre-check: email already taken in this university?
                        if auth.check_email_exists(uni.id, reg_email.strip()):
                            st.error(
                                "This email is already registered. "
                                "Please sign in instead, or use a different email."
                            )
                        else:
                            new_user = auth.register_user(
                                university_id=uni.id,
                                name=reg_name.strip(),
                                email=reg_email.strip(),
                                password=reg_password,
                                role=UserRole.student,
                                department=reg_dept,
                            )
                            registration_limiter.reset(reg_email)  # Clear limit on success
                            st.session_state.university = uni
                            st.session_state.user = new_user
                            st.success("Account created successfully. Logging you in...")
                            st.rerun()
                    except Exception:
                        st.error("Something went wrong creating your account. Please try again.")
    
    st.markdown("</div>", unsafe_allow_html=True)

# ── Page Definitions ─────────────────────────────────────────────────────────

def page_portal_login():
    run_page(_show_login_page, bg_class="bg-landing")

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
                "<h3>Admin Dashboard Access Restricted</h3>"
                "<p style='color:#6B6B6B;'>Please log in as an administrator on the <b>Portal Login</b> page to access this dashboard.</p>",
                unsafe_allow_html=True
            )
            st.markdown("</div>", unsafe_allow_html=True)
            _show_login_page()
    run_page(_run, bg_class="bg-admin")

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
                "<h3>Student Dashboard Access Restricted</h3>"
                "<p style='color:#6B6B6B;'>Please log in as a student on the <b>Portal Login</b> page to access this dashboard.</p>",
                unsafe_allow_html=True
            )
            st.markdown("</div>", unsafe_allow_html=True)
            _show_login_page()
    run_page(_run, bg_class="bg-student")

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
                "<h3>Chat Access Restricted</h3>"
                "<p style='color:#6B6B6B;'>Please log in on the <b>Portal Login</b> page to access the RAG AI chatbot.</p>",
                unsafe_allow_html=True
            )
            st.markdown("</div>", unsafe_allow_html=True)
            _show_login_page()
    bg_class = "bg-admin" if st.session_state.user and st.session_state.user.role == UserRole.admin else "bg-student"
    run_page(_run, bg_class=bg_class)

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
                "<h3>Document Upload Restricted</h3>"
                "<p style='color:#6B6B6B;'>Please log in as an administrator on the <b>Portal Login</b> page to upload knowledge base documents.</p>",
                unsafe_allow_html=True
            )
            st.markdown("</div>", unsafe_allow_html=True)
            _show_login_page()
    run_page(_run, bg_class="bg-admin")

def page_admin_assistant():
    def _run():
        import importlib
        if require_auth(UserRole.admin):
            from app.pages import admin_assistant_page
            importlib.reload(admin_assistant_page)
            admin_assistant_page.render(st.session_state.university, st.session_state.user)
        else:
            st.markdown("<div class='uqms-card'>", unsafe_allow_html=True)
            st.markdown(
                "<h3>Assistant Restricted</h3>"
                "<p style='color:#6B6B6B;'>Please log in as an administrator on the <b>Portal Login</b> page to access the assistant.</p>",
                unsafe_allow_html=True
            )
            st.markdown("</div>", unsafe_allow_html=True)
            _show_login_page()
    run_page(_run, bg_class="bg-admin")

def page_onboarding():
    def _run():
        import importlib
        from app.pages import onboarding
        importlib.reload(onboarding)
        onboarding.render(db)
    run_page(_run, bg_class="bg-onboarding")

def page_public_inquiry():
    def _run():
        import importlib
        from app.pages import public_inquiry
        importlib.reload(public_inquiry)
        public_inquiry.render()
    run_page(_run, bg_class="bg-public-inquiry")

def page_super_admin_dashboard():
    def _run():
        import importlib
        if require_auth(UserRole.super_admin):
            from app.pages import super_admin_dashboard
            importlib.reload(super_admin_dashboard)
            super_admin_dashboard.render(db, st.session_state.user)
        else:
            st.markdown("<div class='uqms-card'>", unsafe_allow_html=True)
            st.markdown(
                "<h3>Super Admin Console Access Restricted</h3>"
                "<p style='color:#6B6B6B;'>Please log in as a super administrator on the <b>Portal Login</b> page to access this console.</p>",
                unsafe_allow_html=True
            )
            st.markdown("</div>", unsafe_allow_html=True)
            _show_login_page()
    run_page(_run, bg_class="bg-super-admin")

# ── Navigation Definition ─────────────────────────────────────────────────────

# Define pages for st.navigation
login_pg = st.Page(page_portal_login, title="Portal Login", icon=":material/lock:")
admin_pg = st.Page(page_admin_dashboard, title="Admin Dashboard", icon=":material/monitoring:")
admin_assistant_pg = st.Page(page_admin_assistant, title="Admin Assistant", icon=":material/support_agent:")
student_pg = st.Page(page_student_dashboard, title="Student Dashboard", icon=":material/assignment:")
rag_pg = st.Page(page_rag_chat, title="RAG Chat", icon=":material/chat:")
upload_pg = st.Page(page_document_upload, title="Document Upload", icon=":material/upload_file:")
onboarding_pg = st.Page(page_onboarding, title="Onboarding", icon=":material/add_business:")
public_inquiry_pg = st.Page(page_public_inquiry, title="Public Inquiry", icon=":material/public:")
super_admin_pg = st.Page(page_super_admin_dashboard, title="Super Admin Console", icon=":material/admin_panel_settings:")

# Build navigation dynamically based on user authentication state and role
pages_to_show = [login_pg]

current_user = st.session_state.user
if current_user is None:
    # Not logged in: show login and onboarding
    pages_to_show.extend([onboarding_pg, public_inquiry_pg])
elif current_user.role == UserRole.super_admin:
    # Logged in as super admin: show super admin console
    pages_to_show.append(super_admin_pg)
elif current_user.role == UserRole.student:
    # Logged in as student: show student dashboard and RAG chat
    pages_to_show.extend([student_pg, rag_pg])
elif current_user.role == UserRole.admin:
    # Logged in as admin: show admin dashboard, RAG chat, admin assistant and document upload
    pages_to_show.extend([admin_pg, rag_pg, admin_assistant_pg, upload_pg])

pg = st.navigation(pages_to_show)

# Render branding above navigation menu
st.sidebar.image(WORDMARK_PATH, use_container_width=True)
st.sidebar.markdown(
    "<div style='border-bottom: 1px solid #E5E5E5; margin: 0.25rem 0 1rem 0;'></div>",
    unsafe_allow_html=True,
)

# Run navigation
pg.run()

# Render User profile at bottom of sidebar
if st.session_state.user is not None:
    uni = st.session_state.university
    user = st.session_state.user
    
    st.sidebar.markdown("<hr style='border:0; border-top:1px solid #E5E5E5; margin: 1rem 0;'>", unsafe_allow_html=True)
    if user.role == UserRole.super_admin:
        st.sidebar.markdown(
            f"<div class='uqms-card' style='padding: 12px; margin-bottom: 12px; border-radius: 8px; background-color: #FFFFFF; border: 1px solid #E5E5E5;'>"
            f"<p style='margin: 0; font-size: 0.75rem; color: #6B6B6B; text-transform: uppercase; font-weight:600;'>System Console</p>"
            f"<h4 style='margin: 4px 0 2px 0; color: #1A1A1A; font-size: 0.95rem; font-weight:600;'>{user.name}</h4>"
            f"<p style='margin: 0; font-size: 0.8rem; color: #4F46E5; font-weight:500;'>SUPER ADMIN</p>"
            f"</div>",
            unsafe_allow_html=True,
        )
    else:
        role_color = "#4F46E5" if user.role == UserRole.admin else "#D97706"
        uni_name = uni.name if uni else ""
        dept_info = f" &bull; {user.department}" if getattr(user, 'department', None) else ""
        st.sidebar.markdown(
            f"<div class='uqms-card' style='padding: 12px; margin-bottom: 12px; border-radius: 8px; background-color: #FFFFFF; border: 1px solid #E5E5E5;'>"
            f"<p style='margin: 0; font-size: 0.75rem; color: #6B6B6B; text-transform: uppercase; font-weight:600;'>{uni_name}</p>"
            f"<h4 style='margin: 4px 0 2px 0; color: #1A1A1A; font-size: 0.95rem; font-weight:600;'>{user.name}</h4>"
            f"<p style='margin: 0; font-size: 0.8rem; color: {role_color}; font-weight:500;'>{user.role.value.upper()}{dept_info}</p>"
            f"</div>",
            unsafe_allow_html=True,
        )
    if st.sidebar.button("Sign Out", key="sidebar_sign_out", use_container_width=True):
        # Clear session state keys except db
        for key in list(st.session_state.keys()):
            if key != "db":
                del st.session_state[key]
        st.rerun()
