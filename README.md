# University Query Management System (UQMS)

An AI-driven, multi-tenant academic support portal designed to streamline student query routing, auto-classify ticket priorities & intent taxonomy, verify user email via OTP, and provide an instant AI-powered RAG assistant based on ingested university guidelines, manuals, and FAQs.

Designed with a premium, clean **Notion/Linear-style light aesthetic** and dynamic role-based page views.

---

## Live Demo
[University Query Management System](https://university-qms-ep9ufqrnvi7g3qo6yeztr3.streamlit.app/)

---


**OR**

uqms66.up.railway.app

## Key Features

* **Multi-Tenant Onboarding**: Register new universities dynamically with custom slugs and institutional departments (e.g., Admissions, Finance & Accounts, IT Support).
* **OTP Email Verification**: Secure 2-step registration with Brevo REST API email verification for all student and admin signups.
* **Dynamic Role Isolation**: Role-based navigation (`st.navigation`) strictly isolating super admins, institution admins, and students.
* **RAG Knowledge Assistant**: Ingests PDF/TXT documents into localized **ChromaDB** vector stores scoped per tenant to answer student queries accurately.
* **Student Question Logging & Taxonomy**: Auto-categorizes student questions in real-time using ML intent classification into fixed academic categories (Admissions, Fees, Exams, Hostel, Library, etc.) with 24h auto-cleanup and interactive category drill-down views.
* **Automated Ticket Routing & Priority Prediction**: Auto-routes student support requests to relevant departments, scores sentiment, and predicts urgency using ML models.
* **Platform Support & Complaints**: Direct support complaint channel from admins to super admin with automated email alerts and resolution tracking.
* **Interactive Admin Analytics**: Admin-only dashboards featuring category breakdown charts, ticket resolution timelines, and student satisfaction ratings rendered via **Plotly**.

---

## Technology Stack

* **Frontend**: [Streamlit](https://streamlit.io/) (Dynamic routing, custom CSS injection, interactive layout)
* **Database & ORM**: [SQLite](https://www.sqlite.org/) / [PostgreSQL](https://www.postgresql.org/) & [SQLAlchemy](https://www.sqlalchemy.org/)
* **Vector Engine**: [ChromaDB](https://www.trychroma.com/) (Tenant-isolated vector database)
* **Transactional Email**: [Brevo REST API](https://www.brevo.com/) (OTP & Notification delivery)
* **Machine Learning**: Scikit-Learn (TF-IDF + Logistic Regression for intent & priority classification)
* **Document Parsing**: PyPDF
* **Analytics**: Plotly & Pandas
* **Security**: Bcrypt (Password hashing)

---

## Running Locally

### 1. Prerequisites
Ensure you have **Python 3.10+** installed.

### 2. Setup Virtual Environment & Install Dependencies
```bash
# Clone the repository
git clone https://github.com/Vishu6636/University-QMS.git
cd University-QMS

# Create and activate virtual environment
python -m venv .venv
# On Windows PowerShell:
.venv\Scripts\Activate.ps1
# On macOS/Linux:
source .venv/bin/activate

# Install required packages
pip install -r requirements.txt
```

### 3. Initialize and Seed the Database
Reset and seed the database with mock universities, users, tickets, and KB documents:
```bash
python scripts/db_init.py --drop --seed
```

### 4. Run the Streamlit Application
```bash
streamlit run app/main.py
```
Open `http://localhost:8501` in your browser.

---

## Configuration & Environment Variables

Create a `.env` file in the root directory:

| Environment Variable | Purpose |
|----------------------|---------|
| `GROQ_API_KEY` | Groq API access token for RAG chat responses |
| `BREVO_API_KEY` | Brevo API key for OTP and notification emails |
| `BREVO_SENDER_EMAIL` | Verified sender email address in Brevo |
| `PLATFORM_OWNER_EMAIL` | Platform owner recipient email for platform complaints |
| `DATABASE_URL` | SQLAlchemy connection string (`sqlite:///./data/university_qms.db` or PostgreSQL) |
| `CHROMA_PATH` | Persistent storage directory for ChromaDB collections (`./data/chroma`) |
| `SENTRY_DSN` | *(Optional)* Sentry DSN endpoint for real-time error monitoring |

---

## Project Architecture

```text
University-QMS/
├── app/                         # Presentation layer
│   ├── main.py                  # App Entry Point & Dynamic Navigation
│   └── pages/                   # Role-Based Page Views
│       ├── onboarding.py        # Institutional Onboarding & OTP
│       ├── admin_dashboard.py   # Admin Analytics, Leads & Question Logs
│       ├── super_admin_dashboard.py # Super Admin Console & Complaints
│       ├── student_dashboard.py # Student Tickets & Feedback Submission
│       ├── document_upload.py   # KB Document Ingestion Dashboard
│       ├── rag_chat_page.py     # RAG AI Chatbot Interface
│       ├── admin_assistant_page.py # Admin AI Assistant
│       ├── public_inquiry.py    # Public Lead Generator / Inquiry Form
│       └── 99_Privacy_Policy.py # Privacy Policy Page
├── models/                      # SQLAlchemy Database Models
│   ├── university.py
│   ├── user.py
│   ├── ticket.py
│   ├── student_query_log.py
│   ├── platform_complaint.py
│   └── audit_log.py
├── services/                    # Core Business & ML Services
│   ├── auth_service.py          # Authentication & user management
│   ├── otp_service.py           # OTP generation & validation
│   ├── email_service.py         # Brevo email REST API client
│   ├── intent_classifier.py     # TF-IDF intent prediction
│   ├── rag_chat.py              # RAG orchestration & query categorization
│   ├── kb_service.py            # Text parsing & DB persistence
│   └── vectorstore_service.py   # ChromaDB vector embedding & retrieval
├── scripts/                     # Seed, test, and evaluation scripts
│   ├── test_tenant_isolation.py # Multi-tenant isolation test suite
│   ├── test_otp_and_email.py    # OTP & Email test suite
│   └── test_platform_complaint.py # Platform complaints test suite
├── reports/                     # ML Evaluation outputs & reports
└── data/                        # Local SQLite & ChromaDB storage
```
