# services/rag_chat.py
"""
RAG pipeline using Groq API (Llama-3.3-70B / GPT-OSS-120B / Qwen-27B).

answer_query(university_id, query, db=None, student_id=None, chat_history=None)
  1. Intent Router: Handles greetings and meta/capability questions directly (0 tickets).
  2. Standalone Query Reformulator: Uses conversation history & current date/day to turn follow-ups into standalone queries.
  3. Multi-Query Retrieval: Generates query variations, embeds all of them, and merges/deduplicates top ChromaDB chunks.
  4. Scoped LLM Answer: Builds system+user prompt and calls Groq.
  5. Smart Escalation Guardrail: Escalates only genuine unanswered operational queries.
"""

import os
import logging
from datetime import datetime

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
VALID_CATEGORIES = frozenset([
    "admission", "fees", "exams", "attendance", "hostel", "library",
    "placement", "scholarship", "complaint", "document_request", "general",
])

GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
FALLBACK_MODELS = ["openai/gpt-oss-120b", "groq/compound-mini", "qwen/qwen3.8-27b", "groq/compound", "openai/gpt-oss-20b"]
TOP_K = 5
MAX_MERGED_CHUNKS = 8

_client: Groq | None = None
_healed_universities: set[int] = set()


def _get_client() -> Groq:
    global _client
    if _client is None:
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise EnvironmentError("GROQ_API_KEY is not set.")
        _client = Groq(api_key=api_key)
    return _client


def _is_greeting_or_smalltalk(query: str) -> bool:
    """Check if query is a simple greeting or expression of gratitude."""
    q = query.strip().lower().rstrip("!.,?")
    greetings = {
        "hi", "hello", "hey", "hey there", "good morning", "good afternoon",
        "good evening", "thanks", "thank you", "thx", "cool", "ok", "okay",
        "who are you", "what is your name", "help"
    }
    return q in greetings


def _is_meta_capability_query(query: str) -> bool:
    """Check if student is asking what the bot can do or what info it has."""
    q = query.strip().lower()
    meta_keywords = [
        "what info you have", "what info do you have", "what information do you have",
        "how can you help me", "what can you do", "what can i ask", "how to use",
        "help me", "what do you know", "show options", "menu options"
    ]
    return any(kw in q for kw in meta_keywords)


def _handle_smalltalk_or_meta(query: str) -> str | None:
    """Return friendly direct answer for chit-chat / meta queries without RAG or ticket creation."""
    q = query.strip().lower()

    if _is_greeting_or_smalltalk(q):
        if any(kw in q for kw in ["thanks", "thank you", "thx"]):
            return "You're very welcome! Let me know if you need any other information."
        return (
            "Hello! I am your University Assistant. "
            "How can I help you today? You can ask about admissions, fees, hostel rules, "
            "mess menus, exam schedules, library timings, and official circulars."
        )

    if _is_meta_capability_query(q):
        return (
            "I can assist you with official university information including:\n\n"
            "• **Hostel & Mess**: Wardens, room allocation, mess menus, and hostel rules\n"
            "• **Admissions & Fees**: Fee structures, payment deadlines, course details, and scholarships\n"
            "• **Academics & Exams**: Exam schedules, attendance requirements, and revaluation fees\n"
            "• **Campus Facilities**: Library hours, placement statistics, and department contacts\n\n"
            "Feel free to ask a specific question!"
        )

    return None


def _reformulate_query(query: str, chat_history: list | None, client: Groq, current_date_str: str) -> str:
    """
    Rewrite short/follow-up queries into a standalone search query using chat history.
    Example: 'Give me contact' after 'Who is warden of RK hostel?' -> 'Contact phone number of Mr Sunil Parker warden of RK hostel'
    """
    if not chat_history or len(chat_history) < 2:
        return query

    recent = chat_history[-6:]
    conv_lines = []
    for msg in recent:
        role = "Student" if msg.get("role") == "user" else "Assistant"
        content = msg.get("content", "").replace("\n", " ")
        conv_lines.append(f"{role}: {content[:200]}")
    conv_context = "\n".join(conv_lines)

    prompt = (
        f"Today's Date: {current_date_str}\n"
        f"Conversation History:\n{conv_context}\n\n"
        f"Latest Student Message: \"{query}\"\n\n"
        "Task: Based on the conversation history, rewrite the Latest Student Message into a clear, "
        "standalone search query that captures all implied context (entities, topics, names). "
        "Do NOT answer the question. Return ONLY the rewritten query string."
    )

    candidate_models = [GROQ_MODEL] + [m for m in FALLBACK_MODELS if m != GROQ_MODEL]
    for model_name in candidate_models:
        try:
            resp = client.chat.completions.create(
                model=model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=64,
            )
            rewritten = resp.choices[0].message.content.strip().strip('"')
            if rewritten and len(rewritten) > 3:
                log.info("RAG query reformulated: %r -> %r", query, rewritten)
                return rewritten
        except RateLimitError:
            return query
        except Exception as e:
            log.warning("Reformulation failed with model %s: %s", model_name, e)

    return query


def _generate_paraphrases(query: str, client: Groq, current_date_str: str) -> list[str]:
    """
    Generate 2 variations/paraphrases of the query for multi-query retrieval.
    This fixes the issue where asking the same question 3 different ways returned no context.
    """
    queries = [query]
    prompt = (
        f"Today's Date: {current_date_str}\n"
        f"Original Query: \"{query}\"\n\n"
        "Task: Generate 2 alternative ways to ask this question using different key phrases, synonyms, "
        "or specific date terms (e.g. if query mentions 'today', include the day of week). "
        "Return exactly 2 lines, one paraphrase per line. Do not number them."
    )

    candidate_models = [GROQ_MODEL] + [m for m in FALLBACK_MODELS if m != GROQ_MODEL]
    for model_name in candidate_models:
        try:
            resp = client.chat.completions.create(
                model=model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=96,
            )
            lines = [l.strip().strip("-*123. ") for l in resp.choices[0].message.content.strip().split("\n") if l.strip()]
            for line in lines:
                if line and line.lower() not in [q.lower() for q in queries]:
                    queries.append(line)
            if len(queries) >= 2:
                break
        except RateLimitError:
            return queries
        except Exception as e:
            log.warning("Paraphrase generation failed with model %s: %s", model_name, e)

    return queries[:3]


def retrieve_multi(university_id: int, queries: list[str], k: int = TOP_K) -> list[dict]:
    """
    Retrieve chunks for multiple query variations from ChromaDB and deduplicate.
    """
    merged_chunks: list[dict] = []
    seen_keys: set = set()

    for q in queries:
        chunks = retrieve(university_id, q, k=k)
        for chunk in chunks:
            # Deduplicate by doc_id and chunk_index (or text fallback)
            key = (chunk.get("doc_id"), chunk.get("chunk_index"), chunk.get("text", "")[:50])
            if key not in seen_keys:
                seen_keys.add(key)
                merged_chunks.append(chunk)

    # Sort merged chunks by cosine similarity score descending
    merged_chunks.sort(key=lambda c: c.get("score", 0.0), reverse=True)
    return merged_chunks[:MAX_MERGED_CHUNKS]


def answer_query(
    university_id: int,
    query: str,
    db = None,
    student_id: int = None,
    chat_history: list | None = None,
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
    # 0. Intent Router: Handle greetings and meta queries immediately (0 tickets)
    smalltalk_response = _handle_smalltalk_or_meta(query)
    if smalltalk_response:
        return {
            "answer": smalltalk_response,
            "chunks_used": 0,
            "escalate": False,
        }

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

    current_date_str = datetime.now().strftime("%A, %d %B %Y")
    client = _get_client()

    # 1. Contextual Query Reformulation (if history is present)
    standalone_query = _reformulate_query(query, chat_history, client, current_date_str)

    # 2. Multi-Query Paraphrasing (generate 2-3 query variations)
    query_variations = _generate_paraphrases(standalone_query, client, current_date_str)

    # 3. Retrieve & Deduplicate top chunks across all query variations
    chunks = retrieve_multi(university_id, query_variations, k=TOP_K)

    if not chunks:
        answer = (
            "I don't have that information in the university knowledge base. "
            "I'll escalate this to a support ticket so the relevant department can assist you."
        )
        escalate = True
    else:
        # 4. Build rich context block with Date awareness
        context = "\n\n---\n\n".join(
            f"[Chunk {i+1}]\n{c['text']}" for i, c in enumerate(chunks)
        )

        system_prompt = (
            f"You are a helpful university support assistant for University ID #{university_id}.\n"
            f"Today's Date: {current_date_str}.\n"
            "Answer the student's question accurately using ONLY the context provided below.\n"
            "Do not use any outside knowledge.\n"
            "If a question mentions 'today' or specific days, use Today's Date to match days of the week.\n"
            "If the context contains a partial answer (e.g. answers when a college was established but not by whom), "
            "provide the facts available in the context first.\n"
            "If the context does not contain enough information to answer the question, "
            "respond with exactly: "
            "\"I don't have that information, I'll escalate this to a ticket.\"\n\n"
            f"CONTEXT:\n{context}"
        )

        # 5. Call Groq with model fallbacks
        candidate_models = [GROQ_MODEL] + [m for m in FALLBACK_MODELS if m != GROQ_MODEL]
        answer = None
        last_error = None

        for model_name in candidate_models:
            try:
                messages = [{"role": "system", "content": system_prompt}]
                # If chat history exists, include recent context
                if chat_history:
                    recent = chat_history[-4:]
                    for msg in recent:
                        messages.append({"role": msg["role"], "content": msg["content"]})

                messages.append({"role": "user", "content": query})

                response = client.chat.completions.create(
                    model=model_name,
                    messages=messages,
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

    # 6. Auto-escalate if we have the database session and student_id
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
            if db is not None:
                try:
                    db.rollback()
                except Exception:
                    pass
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

