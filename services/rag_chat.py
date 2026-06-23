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
from groq import Groq
from services.ingestion import retrieve

log = logging.getLogger(__name__)

GROQ_MODEL = "llama-3.3-70b-versatile"
TOP_K = 5

_client: Groq | None = None


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

        # 3. Call Groq
        try:
            client = _get_client()
            response = client.chat.completions.create(
                model=GROQ_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": query},
                ],
                temperature=0.2,
                max_tokens=512,
            )
            answer = response.choices[0].message.content.strip()
        except Exception as e:
            log.exception("Groq API call failed: %s", e)
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
