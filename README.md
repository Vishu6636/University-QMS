# University Query Management System

University QMS is a multi-tenant academic support portal built for universities and colleges. It gives students a single place to submit questions, track support tickets, and search institutional knowledge, while giving administrators practical tools for routing, analytics, and issue management.

**Live application:** [Open University QMS](https://university-qms-ep9ufqrnvi7g3qo6yeztr3.streamlit.app/)

## Highlights

- **Role-based workspaces** for platform administrators, institution administrators, and students.
- **Tenant isolation** so each institution manages its own users, tickets, documents, and knowledge base.
- **Secure account flows** with password hashing, session controls, rate limiting, and email OTP verification.
- **Intelligent query handling** with intent classification, priority prediction, automatic department routing, and sentiment-aware triage.
- **RAG knowledge assistant** that answers questions from institution-specific PDFs and text documents.
- **Operational dashboards** for ticket lifecycle tracking, feedback, query trends, audits, leads, and platform complaints.

## Technology

| Area | Tools |
| --- | --- |
| Application | Streamlit, Python |
| Data | SQLAlchemy, SQLite or PostgreSQL |
| AI search | ChromaDB, Sentence Transformers, Groq |
| Machine learning | scikit-learn, XGBoost |
| Email | Brevo API |
| Analytics | Pandas, Plotly |
| Monitoring | Sentry (optional) |

## Project structure

```text
app/          Streamlit entry point, role-based pages, and visual assets
models/       SQLAlchemy database models and packaged ML models
services/     Authentication, tickets, email, AI, knowledge-base, and audit services
scripts/      Database setup, data ingestion, training, evaluation, and verification tools
data/         Local development data and the labelled training dataset
reports/      Reproducible model-evaluation summaries
utils/        Shared logging and timezone utilities
```

## Run locally

### 1. Create a virtual environment

```bash
git clone https://github.com/Vishu6636/University-QMS.git
cd University-QMS
python -m venv .venv
```

Activate it:

```powershell
# Windows PowerShell
.venv\Scripts\Activate.ps1
```

```bash
# macOS/Linux
source .venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure environment variables

Copy the template, then add your service credentials:

```powershell
Copy-Item .env.example .env
```

| Variable | Required | Description |
| --- | --- | --- |
| `GROQ_API_KEY` | For AI answers | Groq API key for the RAG assistant |
| `BREVO_API_KEY` | For email | Brevo API key for OTP and notification email |
| `BREVO_SENDER_EMAIL` | For email | Verified Brevo sender address |
| `PLATFORM_OWNER_EMAIL` | For complaints | Recipient for platform complaint alerts |
| `DATABASE_URL` | No | Defaults to local SQLite |
| `CHROMA_PATH` | No | Defaults to `./data/chroma` |
| `SENTRY_DSN` | No | Sentry error-monitoring endpoint |

### 4. Initialise local data and start the app

```bash
python scripts/db_init.py --drop --seed
streamlit run app/main.py
```

Then open `http://localhost:8501`.

## Deployment

The repository includes both a `Dockerfile` and a `Procfile`.

```bash
docker build -t university-qms .
docker run --env-file .env -p 8501:8501 university-qms
```

For a hosted environment, set the variables from `.env.example` in the platform's secret manager. Do not commit `.env`, databases, Chroma collections, or API keys.

## Development utilities

The `scripts/` directory contains small, focused tools for common maintenance tasks:

- `db_init.py` — initialise or seed the database.
- `ingest_faqs.py` — ingest knowledge-base content.
- `train_intent_classifier.py` and `train_priority_model.py` — rebuild packaged ML models.
- `run_evaluation.py` — regenerate evaluation reports.
- `test_*.py` — verify tenant isolation, ticket lifecycle, email/OTP handling, RAG chat, and platform complaints.

## Privacy and security

Passwords are stored using bcrypt hashes. Configuration secrets are supplied through environment variables and excluded from version control. See [the privacy policy](UQMS_Privacy_Policy.md) for the application’s privacy statement.
