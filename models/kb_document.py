# models/kb_document.py
# KBDocument — a knowledge-base file uploaded by a university admin.

import enum
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Enum
from sqlalchemy.orm import relationship
from models.base import Base


class DocType(str, enum.Enum):
    faq = "faq"
    policy = "policy"
    circular = "circular"


class KBDocument(Base):
    __tablename__ = "kb_documents"

    id = Column(Integer, primary_key=True, index=True)
    university_id = Column(
        Integer,
        ForeignKey("universities.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    filename = Column(String(512), nullable=False)
    # Full extracted text — used for embedding into ChromaDB.
    content_text = Column(Text, nullable=False)
    doc_type = Column(
        Enum(DocType, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=DocType.faq,
    )
    uploaded_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    university = relationship("University", back_populates="kb_documents")

    def __repr__(self) -> str:
        return f"<KBDocument id={self.id} filename={self.filename!r} type={self.doc_type}>"
