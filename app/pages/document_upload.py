# app/pages/document_upload.py
"""
Document Upload — Step 2 of university onboarding (and ongoing admin use).
Saves documents to SQLite and indexes them in ChromaDB.
"""

import streamlit as st
from sqlalchemy.orm import Session

from models.university import University
from models.user import User
from models.kb_document import KBDocument, DocType
from services.ingestion import ingest_to_vectorstore


def _extract_text(uploaded_file) -> str:
    """Return plain text from an uploaded Streamlit file object."""
    filename: str = uploaded_file.name.lower()

    if filename.endswith(".pdf"):
        try:
            import pypdf
            reader = pypdf.PdfReader(uploaded_file)
            pages = [page.extract_text() or "" for page in reader.pages]
            return "\n\n".join(pages).strip()
        except ImportError:
            st.error("pypdf is not installed. Run: pip install pypdf")
            return ""
        except Exception as exc:
            st.error(f"Failed to read PDF: {exc}")
            return ""

    # Plain text fallback
    raw = uploaded_file.read()
    return raw.decode("utf-8", errors="replace").strip()


def render(db: Session, university: University, user: User) -> None:
    st.markdown(f"<h2>📂 Document Upload &mdash; {university.name}</h2>", unsafe_allow_html=True)
    st.markdown(
        "<p style='color:#6B6B6B; font-size:14px; margin-bottom: 1.5rem;'>"
        "Upload FAQ, policy, or circular documents. They will be stored in SQLite and indexed into the RAG system."
        "</p>",
        unsafe_allow_html=True,
    )

    # ── Upload form ───────────────────────────────────────────────────────────
    st.markdown("<div class='uqms-card'>", unsafe_allow_html=True)
    with st.form("upload_form", clear_on_submit=True):
        uploaded_files = st.file_uploader(
            "Choose .txt or .pdf files",
            type=["txt", "pdf"],
            accept_multiple_files=True,
        )
        doc_type_str = st.selectbox(
            "Document type (applies to all files in this batch)",
            options=[d.value for d in DocType],
            format_func=lambda v: v.capitalize(),
        )
        submitted = st.form_submit_button("Upload & Ingest", use_container_width=True)
    st.markdown("</div>", unsafe_allow_html=True)

    if submitted:
        if not uploaded_files:
            st.warning("Please select at least one file.")
        else:
            doc_type = DocType(doc_type_str)
            success_count = 0

            for uf in uploaded_files:
                text = _extract_text(uf)
                if not text:
                    st.warning(f"⚠️ No text extracted from **{uf.name}** — skipped.")
                    continue

                # Persist to SQLite
                doc = KBDocument(
                    university_id=university.id,
                    filename=uf.name,
                    content_text=text,
                    doc_type=doc_type,
                )
                db.add(doc)
                db.commit()
                db.refresh(doc)

                # Hand off to vectorstore (ingestion service)
                ingest_to_vectorstore(university.id, doc.id, text)

                st.success(f"✅ **{uf.name}** saved and indexed successfully (doc_id={doc.id}).")
                success_count += 1

            if success_count:
                st.info(f"{success_count} document(s) uploaded. Refresh to see the list below.")

    st.markdown("<hr style='border:0; border-top:1px solid #E5E5E5; margin: 2rem 0;'>", unsafe_allow_html=True)

    # ── Existing documents ────────────────────────────────────────────────────
    st.markdown("<h3>Uploaded Documents</h3>", unsafe_allow_html=True)
    docs: list[KBDocument] = (
        db.query(KBDocument)
        .filter(KBDocument.university_id == university.id)
        .order_by(KBDocument.uploaded_at.desc())
        .all()
    )

    if not docs:
        st.markdown("<p style='color:#6B6B6B; font-style:italic;'>No documents uploaded yet under this university.</p>", unsafe_allow_html=True)
        return

    for doc in docs:
        with st.expander(f"📄 [{doc.doc_type.value.upper()}] {doc.filename}"):
            st.markdown(
                f"<div style='margin-bottom: 8px; font-size:13px; color:#6B6B6B;'>"
                f"<b>ID:</b> {doc.id} | <b>Uploaded:</b> {doc.uploaded_at.strftime('%Y-%m-%d %H:%M')} | "
                f"<b>Size:</b> {len(doc.content_text):,} characters"
                f"</div>",
                unsafe_allow_html=True
            )
            st.text_area(
                "Document Content Preview", 
                value=doc.content_text[:600] + ("..." if len(doc.content_text) > 600 else ""),
                height=150,
                disabled=True,
                key=f"doc_preview_{doc.id}"
            )
