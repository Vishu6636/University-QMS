# app/pages/rag_chat_page.py
"""
Student-facing RAG chat interface.
Scoped automatically to the logged-in university_id and isolated per student.
"""

import streamlit as st
from services.rag_chat import answer_query


def render(uni, user) -> None:
    st.markdown("<h2>Ask the Knowledge Base</h2>", unsafe_allow_html=True)
    st.markdown(
        f"<p style='color:#6B6B6B; font-size:14px; margin-bottom: 1.5rem;'>"
        f"Answers are generated from <b>{uni.name}</b>'s uploaded documents. "
        f"Queries outside the knowledge base are automatically escalated to a support ticket."
        f"</p>",
        unsafe_allow_html=True,
    )

    # Init chat history in session state - scoped to university AND user to prevent leaks
    history_key = f"chat_history_{uni.id}_{user.id}"
    if history_key not in st.session_state:
        st.session_state[history_key] = []

    history = st.session_state[history_key]

    # Render previous messages
    for msg in history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg["role"] == "assistant" and msg.get("escalate"):
                st.warning("This query has been flagged for escalation to a support ticket.")

    # Input box
    query = st.chat_input("Type your question here…", key=f"chat_input_{uni.id}_{user.id}")

    if query:
        # Show user message
        with st.chat_message("user"):
            st.markdown(query)
        history.append({"role": "user", "content": query})

        # Get answer
        with st.chat_message("assistant"):
            with st.spinner("Searching knowledge base…"):
                result = answer_query(uni.id, query, db=st.session_state.db, student_id=user.id)

            answer_text = result["answer"]

            st.markdown(answer_text)

            col1, col2 = st.columns([3, 1])
            with col2:
                st.markdown(
                    f"<p style='font-size:12px; color:#6B6B6B; text-align:right; margin:0;'>"
                    f"{result['chunks_used']} chunk(s) used"
                    f"</p>",
                    unsafe_allow_html=True
                )

            if result["escalate"]:
                st.warning("Flagged for escalation to a support ticket.")

        history.append({
            "role": "assistant",
            "content": answer_text,
            "escalate": result["escalate"],
        })

    # Clear chat button
    if history:
        st.markdown("<div style='margin-top:1.5rem;'>", unsafe_allow_html=True)
        if st.button("Clear chat", key=f"clear_chat_{uni.id}_{user.id}", use_container_width=True):
            st.session_state[history_key] = []
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
