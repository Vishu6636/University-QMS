# services/rag_chat.py
"""
RAG pipeline using Groq API (Llama-3.3-70B).

answer_query(university_id, query)
  1. Retrieves top-5 chunks from the university's ChromaDB collection.
  2. Builds a system+user prompt that scopes the model strictly to the
     retrieved context.
  3. Calls Groq, returns the answer string.
"""

import os
import logging

try:
    import sentry_sdk
except ImportError:
    sentry_sdk = None

import traceback
from groq import (
    Groq,
    APIError,
    APIConnectionError,
    RateLimitError,
    BadRequestError,
    AuthenticationError,
    NotFoundError,
)
from services.ingestion import retrieve
from utils.structured_logger import log_event

log = logging.getLogger(__name__)

# Fixed category list for student query classification
# (aligned with DATASET_NOTES.md intent taxonomy)
VALID_CATEGORIES = frozenset([
    "admission", "fees", "exams", "attendance", "hostel", "library",
    "placement", "scholarship", "complaint", "document_request", "general",
])

GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
FALLBACK_MODELS = ["openai/gpt-oss-120b", "groq/compound-mini", "openai/gpt-oss-20b", "groq/compound"]
TOP_K = 5

_client: Groq | None = None

# Cache: tracks which university_ids have been verified as synced this session.
# Cleared on process restart, which is the exact scenario that causes desync.
_healed_universities: set[int] = set()


def _get_client() -> Groq:
    global _client
    if _client is None:
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise EnvironmentError("GROQ_API_KEY is not set.")
        _client = Groq(api_key=api_key)
    return _client


def answer_query(
    university_id: int,
    query: str,
    db = None,
    student_id: int = None,
) -> dict:
    """
    Answer a student query using RAG against the university's knowledge base.

    Returns:
        {
            "answer": str,
            "chunks_used": int,
            "escalate": bool,   # True when model says it lacks information
        }
    """
    # Auto-healing check before retrieval (runs at most once per university per session)
    if db is not None and university_id not in _healed_universities:
        try:
            from services.ingestion import _get_chroma_client, _collection_name
            from models.kb_document import KBDocument
            client = _get_chroma_client()
            collection = client.get_or_create_collection(
                name=_collection_name(university_id),
                metadata={"hnsw:space": "cosine"},
            )
            db_docs_count = db.query(KBDocument).filter(
                KBDocument.university_id == university_id
            ).count()
            chroma_count = collection.count()

            needs_reindex = False
            if db_docs_count > 0 and chroma_count == 0:
                needs_reindex = True
            elif db_docs_count > 0 and chroma_count > 0:
                # Lightweight check: compare unique doc_id count vs DB doc count
                res = collection.get(include=["metadatas"])
                indexed_doc_ids = set(
                    m["doc_id"] for m in res.get("metadatas", []) if m and "doc_id" in m
                )
                if len(indexed_doc_ids) < db_docs_count:
                    needs_reindex = True

            if needs_reindex:
                log.info(
                    "Auto-healing: Chroma collection out of sync with DB for university %d. Reindexing...",
                    university_id,
                )
                from models.university import University
                uni = db.query(University).filter(University.id == university_id).first()
                if uni:
                    from services.kb_service import KBService
                    kb_svc = KBService(db, uni)
                    kb_svc.reindex_all()

            _healed_universities.add(university_id)
        except Exception as e_reindex:
            log.warning("Auto-healing Chroma in answer_query failed: %s", e_reindex)

    # 1. Retrieve relevant chunks
    chunks = retrieve(university_id, query, k=TOP_K)

    if not chunks:
        answer = (
            "I don't have that information in the knowledge base. "
            "I'll escalate this to a ticket so the right department can assist you."
        )
        escalate = True
    else:
        # 2. Build context block
        context = "\n\n---\n\n".join(
            f"[Chunk {i+1}]\n{c['text']}" for i, c in enumerate(chunks)
        )

        system_prompt = (
            "You are a helpful university support assistant. "
            "Answer the student's question using ONLY the context provided below. "
            "Do not use any outside knowledge. "
            "If the context does not contain enough information to answer confidently, "
            "respond with exactly: "
            "\"I don't have that information, I'll escalate this to a ticket.\"\n\n"
            f"CONTEXT:\n{context}"
        )

        # 3. Call Groq with model fallbacks
        candidate_models = [GROQ_MODEL] + [m for m in FALLBACK_MODELS if m != GROQ_MODEL]
        client = _get_client()
        answer = None
        last_error = None

        for model_name in candidate_models:
            try:
                response = client.chat.completions.create(
                    model=model_name,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": query},
                    ],
                    temperature=0.2,
                    max_tokens=512,
                )
                answer = response.choices[0].message.content.strip()
                if answer:
                    break
            except RateLimitError as e:
                last_error = e
                log.warning("Groq rate limit hit for model %s: %s", model_name, e)
                log_event("groq_rate_limit", model=model_name, error=str(e), university_id=university_id)
            except BadRequestError as e:
                last_error = e
                log.warning("Groq bad request for model %s: %s", model_name, e)
                log_event("groq_bad_request", model=model_name, error=str(e), university_id=university_id)
            except APIConnectionError as e:
                last_error = e
                log.warning("Groq API connection error for model %s: %s", model_name, e)
                log_event("groq_connection_error", model=model_name, error=str(e), university_id=university_id)
            except AuthenticationError as e:
                last_error = e
                log.error("Groq API authentication error (invalid API key): %s", e)
                log_event("groq_auth_error", model=model_name, error=str(e), university_id=university_id)
            except NotFoundError as e:
                last_error = e
                log.warning("Groq model %s not found: %s", model_name, e)
                log_event("groq_model_not_found", model=model_name, error=str(e), university_id=university_id)
            except Exception as e:
                last_error = e
                log.warning("Groq model %s failed with unexpected error: %s", model_name, e, exc_info=True)
                log_event(
                    "groq_model_error",
                    model=model_name,
                    error=str(e),
                    error_type=type(e).__name__,
                    university_id=university_id
                )

        if answer is None:
            err_type = type(last_error).__name__ if last_error else "UnknownError"
            err_msg = str(last_error) if last_error else "No response returned from any candidate model."
            tb_str = traceback.format_exc() if last_error else ""

            log.error(
                "All Groq API models failed. Last error [%s]: %s\nTraceback:\n%s",
                err_type,
                err_msg,
                tb_str,
            )
            if sentry_sdk and last_error:
                sentry_sdk.capture_exception(last_error)

            log_event(
                "groq_api_failure",
                error=err_msg,
                error_type=err_type,
                traceback=tb_str,
                university_id=university_id,
                query=query,
            )
            log_event(
                "rag_query_error",
                error=err_msg,
                error_type=err_type,
                university_id=university_id,
                query=query,
            )

            if isinstance(last_error, RateLimitError):
                answer = "The AI service is currently receiving too many requests. Please try again in a moment."
            elif isinstance(last_error, AuthenticationError):
                answer = "AI service authentication failed. Please contact your system administrator."
            else:
                answer = "Sorry, there was an error reaching the AI service. Please try again."

        escalate = "escalate this to a ticket" in answer.lower()

    # 4. Auto-escalate if we have the database session and student_id
    if escalate and db is not None and student_id is not None:
        try:
            from services.ticket_service import TicketService
            svc = TicketService(db, university_id)
            ticket = svc.create_ticket(
                student_id=student_id,
                title=f"AI Escalation: {query[:50]}...",
                description=query
            )
            answer += (
                f"\n\n🎫 **Ticket #{ticket.id} automatically opened** in "
                f"**{ticket.department}** department with **{ticket.priority.value}** priority."
            )
        except Exception as e:
            log.exception("Failed to auto-create escalation ticket: %s", e)

    return {
        "answer": answer,
        "chunks_used": len(chunks),
        "escalate": escalate,
    }


INTENT_MAP = {
    "admission_query": "admission",
    "fee_payment": "fees",
    "exam_schedule": "exams",
    "attendance_policy": "attendance",
    "hostel_booking": "hostel",
    "library_access": "library",
    "placement_info": "placement",
    "scholarship_inquiry": "scholarship",
    "grievance": "complaint",
    "document_request": "document_request",
    "revaluation_request": "exams",
    "course_registration": "admission",
}


def classify_query_category(query_text: str) -> str:
    """
    Classify a student query into one of the fixed categories using high-precision intent classification.

    Returns one of VALID_CATEGORIES.
    """
    try:
        from services.intent_classifier import predict_intent
        raw_intent = predict_intent(query_text)
        if raw_intent in INTENT_MAP:
            return INTENT_MAP[raw_intent]
    except Exception as e:
        log.warning("Intent classification failed: %s", e)

    # Fallback keyword matching
    q = query_text.lower()
    if any(k in q for k in ["admission", "apply", "b.tech", "m.tech", "course", "join"]):
        return "admission"
    elif any(k in q for k in ["fee", "payment", "cost", "charge", "dues"]):
        return "fees"
    elif any(k in q for k in ["exam", "schedule", "revaluation", "marks", "result"]):
        return "exams"
    elif any(k in q for k in ["attendance", "present", "absent"]):
        return "attendance"
    elif any(k in q for k in ["hostel", "mess", "room", "curfew", "accommodation"]):
        return "hostel"
    elif any(k in q for k in ["library", "book", "issue"]):
        return "library"
    elif any(k in q for k in ["placement", "job", "salary", "company", "package"]):
        return "placement"
    elif any(k in q for k in ["scholarship", "stipend", "grant", "financial aid"]):
        return "scholarship"
    elif any(k in q for k in ["complain", "grievance", "issue", "problem"]):
        return "complaint"
    elif any(k in q for k in ["document", "certificate", "transcript", "marksheet"]):
        return "document_request"

    return "general"
