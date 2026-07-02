import os
import streamlit as st

def render():
    st.markdown("<h2 style='margin-top:0;'>Privacy Policy</h2>", unsafe_allow_html=True)
    
    # Resolve the path to UQMS_Privacy_Policy.md in the project root
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    policy_path = os.path.join(base_dir, "UQMS_Privacy_Policy.md")
    
    if os.path.exists(policy_path):
        with open(policy_path, "r", encoding="utf-8") as f:
            policy_content = f.read()
        st.markdown(policy_content, unsafe_allow_html=True)
    else:
        st.error("Privacy Policy document could not be found.")
