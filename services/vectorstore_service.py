# services/vectorstore_service.py
"""
Vectorstore ingestion stub.

Replace the body of `ingest_to_vectorstore` with real ChromaDB / embedding
logic in the next iteration.
"""


def ingest_to_vectorstore(university_id: int, doc_id: int, text: str) -> bool:
    """
    Placeholder: index a KB document into the vector store.

    Args:
        university_id: Tenant identifier (used to pick the right collection).
        doc_id:        SQLite KBDocument.id (used as the vector record key).
        text:          Full extracted text to embed.

    Returns:
        True on success (always, for now).
    """
    print(
        f"[vectorstore stub] ingest_to_vectorstore("
        f"university_id={university_id}, doc_id={doc_id}, "
        f"text_len={len(text)} chars)"
    )
    return True
