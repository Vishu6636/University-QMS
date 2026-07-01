# University Query Management System (UQMS)

An AI-driven, multi-tenant academic support portal designed to streamline student query routing, auto-classify ticket priorities, and provide an instant AI-powered Chat (RAG) assistant based on ingested university guidelines, manuals, and FAQs.

Designed with a premium, clean **Notion/Linear-style light aesthetic** and dynamic role-based page views.

---
## live 
https://university-qms-ep9ufqrnvi7g3qo6yeztr3.streamlit.app/

## Key Features

*   **Multi-Tenant Onboarding**: Register new universities dynamically with custom slugs and institutional departments (e.g., Admissions, Finance & Accounts, IT Support).
*   **Student Self-Registration**: Secure signup flow with matching confirmations, email format validations, and student department selection.
*   **Dynamic Role Isolation**: Role-based sidebar navigation (`st.navigation`) dynamically hides admin pages (such as Onboarding and Document Ingestion) from students, and vice versa.
*   **RAG Knowledge Assistant**: Ingests PDF/TXT documents, processes text chunks, and indexes them into a localized **ChromaDB** vector store to answer student queries using university guidelines.
*   **Automated Ticket Routing & Priority Prediction**: Auto-routes student support requests to relevant departments, scores sentiment, and predicts urgency using ML models.
*   **Interactive Admin Analytics**: Admin-only dashboards featuring ticket resolution timelines, department-wise backlogs, and student satisfaction ratings rendered via **Plotly**.

---

## Technology Stack

*   **Frontend**: [Streamlit](https://streamlit.io/) (Dynamic routing, custom CSS injection, interactive layout)
*   **Database & ORM**: [SQLite](https://www.sqlite.org/) & [SQLAlchemy](https://www.sqlalchemy.org/)
*   **Vector Engine**: [ChromaDB](https://www.trychroma.com/) (Local vector database)
*   **Machine Learning**: Scikit-Learn (TF-IDF + Logistic Regression for intent & priority classification)
*   **Document Parsing**: PyPDF
*   **Analytics**: Plotly & Pandas
*   **Security**: Bcrypt (Password hashing)

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

# Install required packages (includes CPU-only PyTorch optimization)
pip install -r requirements.txt
```

### 3. Initialize and Seed the Database
Reset and seed the SQLite database with mock universities, users, tickets, and KB documents:
```bash
python scripts/db_init.py --drop --seed
```
*When prompted, type `yes` to confirm dropping the database tables.*

### 4. Run the Streamlit Application
```bash
streamlit run app/main.py
```
Open `http://localhost:8501` in your browser to view the application.

---

## Production Deployment & Infrastructure Hardening

This system is configured for seamless deployment on free-tier cloud infrastructure (e.g., Render, Railway, or Streamlit Community Cloud) paired with a managed database.

### 1. Database Migration (Postgres)
For production, the database engine can be swapped from the default local SQLite file to PostgreSQL by setting the `DATABASE_URL` environment variable:
*   **Engine resilience**: The engine initializes with `pool_pre_ping=True` to automatically handle database idle timeouts and reconnection limits common on free-tier DB instances.
*   **Compatible Hosts**: Neon (serverless Postgres) or Supabase free tier are recommended. Neon supports branching and instant point-in-time recovery.
*   **Database backups**: Since Postgres is hosted externally, rely on the host's automatic, daily zero-config snapshots (available natively in Supabase and Neon) instead of custom database scripts.

### 2. Error Monitoring (Sentry)
Integrate real-time error tracking and alerting via Sentry:
1. Create a free Sentry project.
2. Add the `SENTRY_DSN` environment variable to your deployment configurations.
3. Errors arising from AI/RAG APIs, database connections, or ML classification logic will automatically log to Sentry with detailed call stacks.

### 3. Hosting Configurations (Render/Streamlit Cloud)
*   **Procfile**: A generic `Procfile` is included for services like Render or Railway.
*   **Resource limits**: On free-tier platforms, containers spin down (sleep) after ~15 minutes of inactivity. When a new request arrives, a cold start (~30-60 seconds) will occur.
*   **ChromaDB state**: Since the vector database is local (`./data/chroma`), it will be ephemeral on non-persistent container platforms (like Render's free tier). For persistent knowledge, attach a small persistent volume mount to `/data`, or use a persistent host.

---

## Configuration & Environment Variables

Create a `.env` file in the root directory (already included in `.gitignore`) or specify variables in your cloud hosting provider's panel:

| Environment Variable | Default | Purpose |
|----------------------|---------|---------|
| `GROQ_API_KEY` | *(Required)* | Groq API access token for generating RAG chat answers |
| `DATABASE_URL` | `sqlite:///./data/university_qms.db` | SQLAlchemy connection string (sqlite or postgresql) |
| `SESSION_TIMEOUT_MINUTES` | `30` | Minutes of inactivity before student session state is cleared |
| `SENTRY_DSN` | *(Optional)* | Sentry DSN endpoint for real-time error monitoring |
| `SENTRY_ENV` | `production` | Environment name reported to Sentry |
| `CHROMA_PATH` | `./data/chroma` | Persistent storage directory for ChromaDB collections |

---

## Project Architecture

```text
university-query-system/
├── app/                         # Frontend presentation layer
│   ├── main.py                  # Entry Point & Dynamic Navigation
│   └── pages/                   # User Role & Process Sub-Pages
│       ├── onboarding.py        # University & Admin Registration
│       ├── admin_dashboard.py   # Admin Analytics & Ticket Tracker
│       ├── student_dashboard.py # Student Tickets & Feedback Submission
│       ├── document_upload.py   # Ingestion dashboard
│       └── rag_chat.py          # AI Chatbot Interface (RAG)
├── models/                      # SQLAlchemy Database Schema Layer
├── services/                    # Core Business Logic & Process Services
│   ├── auth_service.py          # Hashing, authentication, registration
│   ├── ticket_service.py        # Ticket lifecycle & routing logic
│   ├── kb_service.py            # Text parsing & DB persistence
│   ├── vectorstore_service.py   # ChromaDB vector embedding & search
│   └── ingestion.py             # RAG text extraction from PDF & TXT
├── scripts/                     # Seed & training utility scripts
└── data/                        # Local data directory
```
