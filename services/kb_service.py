# services/kb_service.py
"""
KBService — Knowledge-Base document management.

Handles SQLite persistence (KBDocument) and ChromaDB vector indexing.
Each university gets its own isolated ChromaDB collection named
`kb_<university_slug>` so similarity searches are automatically scoped.
"""

import logging
import os
from typing import Optional

import chromadb
from chromadb.config import Settings
from sqlalchemy.orm import Session

from models.kb_document import KBDocument, DocType
from models.university import University

log = logging.getLogger(__name__)

# ChromaDB storage location — configurable via env var.
CHROMA_PATH = os.getenv("CHROMA_PATH", "./data/chroma")


def _get_chroma_client() -> chromadb.PersistentClient:
    """Return a persistent ChromaDB client backed by the local filesystem."""
    return chromadb.PersistentClient(
        path=CHROMA_PATH,
        settings=Settings(anonymized_telemetry=False),
    )


class KBService:
    """Manages knowledge-base documents and their vector embeddings."""

    def __init__(self, db: Session, university: University) -> None:
        self.db = db
        self.university = university
        self._chroma: Optional[chromadb.PersistentClient] = None

    # ── ChromaDB helpers ───────────────────────────────────────────────────────

    @property
    def chroma(self) -> chromadb.PersistentClient:
        if self._chroma is None:
            self._chroma = _get_chroma_client()
        return self._chroma

    @property
    def collection_name(self) -> str:
        return f"kb_{self.university.slug}"

    def _get_collection(self):
        """Get-or-create the ChromaDB collection for this university."""
        return self.chroma.get_or_create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    # ── Document ingestion ─────────────────────────────────────────────────────

    def add_document(
        self,
        *,
        filename: str,
        content_text: str,
        doc_type: DocType,
    ) -> KBDocument:
        """
        Persist a document to SQLite and index it in ChromaDB.

        The document text is chunked into ~500-character paragraphs and each
        chunk is stored as a separate ChromaDB entry.  The SQLite record holds
        the full text for display / re-indexing.
        """
        # 1. SQLite
        doc = KBDocument(
            university_id=self.university.id,
            filename=filename,
            content_text=content_text,
            doc_type=doc_type,
        )
        self.db.add(doc)
        self.db.commit()
        self.db.refresh(doc)
        log.info("Saved KBDocument id=%s filename=%s", doc.id, filename)

        # 2. ChromaDB — chunk by paragraph, fall back to single chunk
        self._index_document(doc)
        return doc

    def _index_document(self, doc: KBDocument) -> None:
        """Chunk the document and upsert chunks into ChromaDB using services.ingestion."""
        from services.ingestion import ingest_to_vectorstore
        ingest_to_vectorstore(self.university.id, doc.id, doc.content_text)


    @staticmethod
    def _chunk_text(text: str, max_chars: int = 500) -> list[str]:
        """Split text on double-newlines; merge short paragraphs to approach max_chars."""
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        chunks: list[str] = []
        current = ""
        for para in paragraphs:
            if len(current) + len(para) + 2 <= max_chars:
                current = (current + "\n\n" + para).strip()
            else:
                if current:
                    chunks.append(current)
                current = para
        if current:
            chunks.append(current)
        return chunks or [text[:max_chars]]

    # ── Retrieval ──────────────────────────────────────────────────────────────

    def search(self, query: str, n_results: int = 5) -> list[dict]:
        """
        Semantic search over this university's KB collection.

        Returns a list of dicts with keys: text, score, filename, doc_type.
        """
        collection = self._get_collection()
        try:
            results = collection.query(
                query_texts=[query],
                n_results=min(n_results, collection.count() or 1),
                include=["documents", "metadatas", "distances"],
            )
        except Exception as exc:
            log.warning("ChromaDB query failed: %s", exc)
            return []

        output = []
        docs = results.get("documents", [[]])[0]
        metas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]
        for text, meta, dist in zip(docs, metas, distances):
            output.append(
                {
                    "text": text,
                    "score": round(1 - dist, 4),   # cosine similarity
                    "filename": meta.get("filename"),
                    "doc_type": meta.get("doc_type"),
                }
            )
        return output

    # ── CRUD ───────────────────────────────────────────────────────────────────

    def list_documents(self, doc_type: Optional[DocType] = None) -> list[KBDocument]:
        q = self.db.query(KBDocument).filter(
            KBDocument.university_id == self.university.id
        )
        if doc_type:
            q = q.filter(KBDocument.doc_type == doc_type)
        return q.order_by(KBDocument.uploaded_at.desc()).all()

    def get_document(self, doc_id: int) -> Optional[KBDocument]:
        return (
            self.db.query(KBDocument)
            .filter(
                KBDocument.id == doc_id,
                KBDocument.university_id == self.university.id,
            )
            .first()
        )

    def delete_document(self, doc_id: int) -> bool:
        """Delete the SQLite record and remove chunks from ChromaDB."""
        doc = self.get_document(doc_id)
        if not doc:
            return False

        # Remove from ChromaDB
        try:
            from services.ingestion import _get_chroma_client
            client = _get_chroma_client()
            collection = client.get_or_create_collection(
                name=f"university_{self.university.id}",
                metadata={"hnsw:space": "cosine"},
                embedding_function=None,
            )
            existing = collection.get(where={"doc_id": doc_id})
            if existing["ids"]:
                collection.delete(ids=existing["ids"])
        except Exception as exc:
            log.warning("ChromaDB delete failed for doc_id=%s: %s", doc_id, exc)

        self.db.delete(doc)
        self.db.commit()
        log.info("Deleted KBDocument id=%s", doc_id)
        return True

    def reindex_all(self) -> int:
        """Re-embed all documents for this university — useful after model changes."""
        docs = self.list_documents()
        for doc in docs:
            self._index_document(doc)
        return len(docs)
