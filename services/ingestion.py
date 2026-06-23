# services/ingestion.py
"""
Vectorstore ingestion and retrieval for the University Query System.

Key design decisions
--------------------
* **Per-university collection**: each university gets its own ChromaDB
  collection named ``university_{university_id}``.  This provides hard
  tenant isolation — a retrieve() call for university 1 is physically
  incapable of returning university 2's chunks.

* **Overlapping word-based chunking**: text is split into ~300-word chunks
  with a 50-word stride overlap so that semantic context is preserved at
  chunk boundaries.

* **Local sentence-transformers embedding**: ``all-MiniLM-L6-v2`` runs
  entirely on-device (CPU-friendly), no external API calls required.
  ChromaDB receives pre-computed embeddings so we stay in full control
  of the embedding model.
"""

import logging
import os
from typing import Optional

import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer

log = logging.getLogger(__name__)

# ── Configuration ──────────────────────────────────────────────────────────────

CHROMA_PATH: str = os.getenv("CHROMA_PATH", "./data/chroma")
EMBED_MODEL_NAME: str = "all-MiniLM-L6-v2"

# Chunking parameters (word-based)
CHUNK_SIZE_WORDS: int = 300   # target chunk size in words
CHUNK_OVERLAP_WORDS: int = 50  # overlap between consecutive chunks

# ── Singletons (lazy-initialised) ─────────────────────────────────────────────

_embed_model: Optional[SentenceTransformer] = None
_chroma_client: Optional[chromadb.PersistentClient] = None


def _get_embed_model() -> SentenceTransformer:
    """Return (and cache) the sentence-transformer embedding model."""
    global _embed_model
    if _embed_model is None:
        log.info("Loading embedding model '%s' …", EMBED_MODEL_NAME)
        _embed_model = SentenceTransformer(EMBED_MODEL_NAME)
        log.info("Embedding model loaded.")
    return _embed_model


def _get_chroma_client() -> chromadb.PersistentClient:
    """Return (and cache) a persistent ChromaDB client."""
    global _chroma_client
    if _chroma_client is None:
        _chroma_client = chromadb.PersistentClient(
            path=CHROMA_PATH,
            settings=Settings(anonymized_telemetry=False),
        )
    return _chroma_client


# ── Helpers ────────────────────────────────────────────────────────────────────

def _collection_name(university_id: int) -> str:
    """Deterministic ChromaDB collection name for a given university."""
    return f"university_{university_id}"


def _get_or_create_collection(university_id: int):
    """Return the ChromaDB collection for *university_id*, creating it if absent."""
    client = _get_chroma_client()
    return client.get_or_create_collection(
        name=_collection_name(university_id),
        # Store raw embeddings; cosine distance for similarity ranking.
        metadata={"hnsw:space": "cosine"},
        # We supply our own embeddings, so tell ChromaDB not to embed.
        embedding_function=None,
    )


def _chunk_text(
    text: str,
    chunk_size: int = CHUNK_SIZE_WORDS,
    overlap: int = CHUNK_OVERLAP_WORDS,
) -> list[str]:
    """
    Split *text* into overlapping word-based chunks.

    Args:
        text:       Full document text.
        chunk_size: Target chunk size in words.
        overlap:    Number of words shared between consecutive chunks.

    Returns:
        List of chunk strings.  Guaranteed to be non-empty.
    """
    words = text.split()
    if not words:
        return [text]

    stride = max(1, chunk_size - overlap)
    chunks: list[str] = []

    start = 0
    while start < len(words):
        end = min(start + chunk_size, len(words))
        chunk = " ".join(words[start:end])
        chunks.append(chunk)
        if end == len(words):
            break
        start += stride

    return chunks


# ── Public API ─────────────────────────────────────────────────────────────────

def ingest_to_vectorstore(university_id: int, doc_id: int, text: str) -> bool:
    """
    Chunk *text* and upsert embeddings into the university's ChromaDB collection.

    Args:
        university_id: Tenant identifier; determines the ChromaDB collection.
        doc_id:        SQLite KBDocument.id — used as part of the vector record key.
        text:          Full extracted text to embed.

    Returns:
        ``True`` on success, ``False`` if an error was encountered.
    """
    if not text or not text.strip():
        log.warning(
            "ingest_to_vectorstore: empty text for university_id=%s doc_id=%s — skipping.",
            university_id, doc_id,
        )
        return False

    try:
        chunks = _chunk_text(text)
        log.info(
            "Ingesting doc_id=%s for university_id=%s — %d chunk(s).",
            doc_id, university_id, len(chunks),
        )

        # Embed all chunks in one batch (efficient).
        model = _get_embed_model()
        embeddings: list[list[float]] = model.encode(
            chunks, show_progress_bar=False, convert_to_numpy=True
        ).tolist()

        # Build ChromaDB record lists.
        ids = [f"u{university_id}_doc{doc_id}_chunk{i}" for i in range(len(chunks))]
        metadatas = [
            {
                "university_id": university_id,
                "doc_id": doc_id,
                "chunk_index": i,
                "chunk_total": len(chunks),
            }
            for i in range(len(chunks))
        ]

        collection = _get_or_create_collection(university_id)
        collection.upsert(
            ids=ids,
            embeddings=embeddings,
            documents=chunks,
            metadatas=metadatas,
        )
        log.info(
            "Upserted %d chunk(s) into collection '%s'.",
            len(chunks), _collection_name(university_id),
        )
        return True

    except Exception:
        log.exception(
            "ingest_to_vectorstore failed for university_id=%s doc_id=%s.",
            university_id, doc_id,
        )
        return False


def retrieve(
    university_id: int,
    query: str,
    k: int = 5,
) -> list[dict]:
    """
    Semantic search over *university_id*'s isolated ChromaDB collection.

    Only the target university's collection is queried — cross-tenant leakage
    is architecturally impossible because each university owns a separate
    ChromaDB collection.

    Args:
        university_id: Tenant whose knowledge base to search.
        query:         Natural-language query string.
        k:             Maximum number of results to return.

    Returns:
        List of result dicts (sorted by descending similarity score)::

            [
                {
                    "text":         str,   # chunk text
                    "score":        float, # cosine similarity in [0, 1]
                    "doc_id":       int,
                    "chunk_index":  int,
                    "university_id": int,
                },
                …
            ]

        Returns an empty list if the collection is empty or an error occurs.
    """
    if not query or not query.strip():
        log.warning("retrieve: empty query for university_id=%s.", university_id)
        return []

    try:
        collection = _get_or_create_collection(university_id)
        total = collection.count()
        if total == 0:
            log.info(
                "retrieve: collection '%s' is empty.",
                _collection_name(university_id),
            )
            return []

        # Embed the query with the same model used during ingestion.
        model = _get_embed_model()
        query_embedding: list[float] = model.encode(
            [query], show_progress_bar=False, convert_to_numpy=True
        ).tolist()[0]

        n = min(k, total)
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=n,
            include=["documents", "metadatas", "distances"],
        )

        output: list[dict] = []
        docs = results.get("documents", [[]])[0]
        metas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]

        for text, meta, dist in zip(docs, metas, distances):
            output.append(
                {
                    "text": text,
                    # ChromaDB returns cosine *distance* (0 = identical).
                    # Convert to similarity so higher is better.
                    "score": round(1.0 - dist, 6),
                    "doc_id": meta.get("doc_id"),
                    "chunk_index": meta.get("chunk_index"),
                    "university_id": meta.get("university_id"),
                }
            )

        return output

    except Exception:
        log.exception(
            "retrieve failed for university_id=%s query=%r.", university_id, query
        )
        return []
