"""Sarkari Sahayak — Streamlit UI. Talks to the REST API only (never imports server code)."""

import os

import httpx
import streamlit as st

API_URL = os.environ.get("SAHAYAK_API_URL", "http://localhost:8000")
TIMEOUT = httpx.Timeout(90.0, connect=10.0)  # free-tier cold starts take ~1 minute

st.set_page_config(page_title="Sarkari Sahayak", page_icon="📜")
st.title("सरकारी सहायक · Sarkari Sahayak")
st.caption("RBI Master Directions से उत्तर — हर उत्तर स्रोत के साथ, या साफ़ इनकार।")

question = st.text_input("अपना प्रश्न लिखें / Ask a question", key="question", max_chars=1000)

if st.button("पूछें / Ask", type="primary", disabled=not question):
    with st.spinner("खोज रहे हैं… (free server may take ~1 min to wake up)"):
        try:
            resp = httpx.post(f"{API_URL}/v1/ask", json={"question": question}, timeout=TIMEOUT)
        except httpx.TimeoutException:
            st.warning("Server is waking up (free tier). Please try again in a few seconds.")
            st.stop()
    if resp.status_code == 429:
        st.warning(f"Too many requests. Retry after {resp.headers.get('retry-after', '60')} s.")
    elif resp.status_code == 503:
        st.warning(resp.json().get("detail", "Service temporarily unavailable."))
    elif resp.status_code != 200:
        st.error(f"Error {resp.status_code}")
    else:
        data = resp.json()
        st.session_state["last_run_id"] = data["run_id"]
        if data["refused"]:
            st.info(data["answer"])
        else:
            st.markdown(data["answer"])
        if data.get("degraded"):
            st.caption("⚠️ LLM unavailable — showing the most relevant passages instead.")
        for cite in data["citations"]:
            with st.expander(f"📄 {cite['chunk_id']}"):
                st.write(cite["text"])
                if cite.get("source_url"):
                    st.link_button("Source (rbi.org.in)", cite["source_url"])
