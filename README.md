# 🎓 University Query Management System (UQMS)

An AI-driven, multi-tenant academic support portal designed to streamline student query routing, auto-classify ticket priorities, and provide an instant AI-powered Chat (RAG) assistant based on ingested university guidelines, manuals, and FAQs.

Designed with a premium, clean **Notion/Linear-style light aesthetic** and dynamic role-based page views.

---

## ✨ Key Features

*   **🏢 Multi-Tenant Onboarding**: Register new universities dynamically with custom slugs and institutional departments (e.g., Admissions, Finance & Accounts, IT Support).
*   **📝 Student Self-Registration**: Secure signup flow with matching confirmations, email format validations, and student department selection.
*   **🛡️ Dynamic Role Isolation**: Role-based sidebar navigation (`st.navigation`) dynamically hides admin pages (such as Onboarding and Document Ingestion) from students, and vice versa.
*   **💬 RAG Knowledge Assistant**: Ingests PDF/TXT documents, processes text chunks, and indexes them into a localized **ChromaDB** vector store to answer student queries using university guidelines.
*   **🤖 Automated Ticket Routing & Priority Prediction**: Auto-routes student support requests to relevant departments, scores sentiment, and predicts urgency using ML models.
*   **📊 Interactive Admin Analytics**: Admin-only dashboards featuring ticket resolution timelines, department-wise backlogs, and student satisfaction ratings rendered via **Plotly**.

---

## 🛠️ Technology Stack

*   **Frontend**: [Streamlit](https://streamlit.io/) (Dynamic routing, custom CSS injection, interactive layout)
*   **Database & ORM**: [SQLite](https://www.sqlite.org/) & [SQLAlchemy](https://www.sqlalchemy.org/)
*   **Vector Engine**: [ChromaDB](https://www.trychroma.com/) (Local vector database)
*   **Machine Learning**: Scikit-Learn (TF-IDF + Logistic Regression for intent & priority classification)
*   **Document Parsing**: PyPDF
*   **Analytics**: Plotly & Pandas
*   **Security**: Bcrypt (Password hashing)

---

## 🚀 Running Locally

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

## 🌩️ Deployment on Streamlit Cloud

1. Commit and push all changes to your GitHub repository.
2. Sign in to **[Streamlit Community Cloud](https://share.streamlit.io/)** with your GitHub account.
3. Click **New App** and select your repository (`University-QMS`).
4. Set the **Main file path** to `app/main.py`.
5. *(Optional)* Add your environment variables (like API keys) in **Advanced settings > Secrets** in TOML format:
   ```toml
   GROQ_API_KEY = "your-api-key"
   ```
6. Click **Deploy!**

---

## 📂 Project Architecture

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
