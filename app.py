"""
Streamlit web UI for the Applied AI Documentation Assistant.

Run with:
    streamlit run app.py
"""

import streamlit as st
from dotenv import load_dotenv
load_dotenv()

from docubot import DocuBot
from confidence import compute_confidence, confidence_label, extract_meaningful_terms
from guardrails import validate_input, validate_output, log_interaction

# -----------------------------------------------------------------------
# Page config
# -----------------------------------------------------------------------

st.set_page_config(
    page_title="Applied AI Documentation Assistant",
    page_icon="📚",
    layout="centered",
)

# -----------------------------------------------------------------------
# Session state — initialise bot and LLM client once
# -----------------------------------------------------------------------

@st.cache_resource
def load_bot(has_llm):
    llm_client = None
    if has_llm:
        try:
            from llm_client import GeminiClient
            llm_client = GeminiClient()
        except Exception:
            pass
    return DocuBot(docs_folder="docs", extra_docs_folders=["custom_docs"], llm_client=llm_client)

@st.cache_resource
def try_llm():
    try:
        from llm_client import GeminiClient
        client = GeminiClient()
        return client, True
    except Exception:
        return None, False

llm_client, has_llm = try_llm()
bot = load_bot(has_llm)

# -----------------------------------------------------------------------
# Header
# -----------------------------------------------------------------------

st.title("📚 Applied AI Documentation Assistant")
st.caption(
    f"Loaded **{len(bot.documents)} documents** from `docs/` + `custom_docs/` · "
    f"LLM: {'✅ Gemini enabled' if has_llm else '⚠️ No API key — Retrieval mode only'}"
)
st.divider()

# -----------------------------------------------------------------------
# Mode selector + query input
# -----------------------------------------------------------------------

mode_options = ["2 — Retrieval Only", "3 — RAG", "4 — Agentic RAG", "1 — Naive LLM"]
mode_labels  = {"2 — Retrieval Only": "2", "3 — RAG": "3",
                "4 — Agentic RAG": "4", "1 — Naive LLM": "1"}

col1, col2 = st.columns([1, 3])
with col1:
    selected = st.selectbox("Mode", mode_options, index=0)
    mode = mode_labels[selected]

with col2:
    query = st.text_input("Developer question", placeholder="e.g. Where is the auth token generated?")

run = st.button("Ask", type="primary", use_container_width=True)

# -----------------------------------------------------------------------
# Run on button click
# -----------------------------------------------------------------------

if run and query.strip():
    st.divider()

    # --- Guardrail: input validation ---
    valid, reason = validate_input(query)
    if not valid:
        st.error(f"🚧 **Guardrail blocked:** {reason}")
        st.stop()

    # --- Retrieval & confidence ---
    with st.spinner("Retrieving..."):
        snippets = bot.retrieve(query, top_k=5)

    terms = extract_meaningful_terms(query)
    all_scores = [bot.score_document(query, t) for _, t in snippets]
    top_score = all_scores[0] if all_scores else 0.0
    top_snippet = snippets[0][1] if snippets else ""
    conf = compute_confidence(top_score, all_scores, terms, top_snippet)
    label = confidence_label(conf)

    color = {"HIGH": "green", "MEDIUM": "orange", "LOW": "red"}.get(label, "gray")
    st.markdown(
        f"**Retrieval Confidence:** "
        f"<span style='color:{color}; font-weight:bold'>{conf:.2f} [{label}]</span>",
        unsafe_allow_html=True,
    )

    # --- Mode 2: Retrieval Only ---
    if mode == "2":
        st.subheader("Retrieved Snippets")
        if not snippets:
            st.info("No matching documentation found.")
        else:
            for fname, text in snippets:
                with st.expander(f"📄 {fname}"):
                    st.markdown(text)
        log_interaction(query, "retrieval", str([f for f, _ in snippets]), conf)

    # --- Mode 1: Naive LLM ---
    elif mode == "1":
        if not has_llm:
            st.warning("Naive LLM mode requires a GEMINI_API_KEY.")
        else:
            with st.spinner("Asking Gemini (no docs)..."):
                answer = bot.llm_client.naive_answer_over_full_docs(query, "")
            st.subheader("Naive LLM Answer")
            st.markdown(answer)
            st.caption("⚠️ This answer is not grounded in any documentation.")
            log_interaction(query, "naive", answer)

    # --- Mode 3: RAG ---
    elif mode == "3":
        if not has_llm:
            st.warning("RAG mode requires a GEMINI_API_KEY.")
        else:
            with st.spinner("Generating grounded answer..."):
                answer = bot.answer_rag(query)

            grounded, note = validate_output(answer, snippets)
            if not grounded:
                st.warning(f"🚧 **Output guardrail:** {note}")

            st.subheader("RAG Answer")
            st.markdown(answer)

            st.subheader("Source Snippets Used")
            for fname, text in snippets[:3]:
                with st.expander(f"📄 {fname}"):
                    st.markdown(text)
            log_interaction(query, "rag", answer, conf)

    # --- Mode 4: Agentic RAG ---
    elif mode == "4":
        if not has_llm:
            st.warning("Agentic RAG mode requires a GEMINI_API_KEY.")
        else:
            from agent import agentic_rag_answer

            log_placeholder = st.empty()
            agent_log = []

            # Monkey-patch print to capture agent steps
            import builtins
            original_print = builtins.print
            def capture_print(*args, **kwargs):
                msg = " ".join(str(a) for a in args)
                if "[Agent]" in msg:
                    agent_log.append(msg.strip())
                    log_placeholder.info("\n\n".join(agent_log))
                original_print(*args, **kwargs)
            builtins.print = capture_print

            with st.spinner("Running agentic self-critique loop..."):
                result = agentic_rag_answer(bot, query, verbose=True)

            builtins.print = original_print

            st.subheader("Agentic RAG Answer")
            st.markdown(result["answer"])

            meta_col1, meta_col2, meta_col3 = st.columns(3)
            meta_col1.metric("Attempts", result["attempts"])
            meta_col2.metric("Grounded", "✅ Yes" if result["grounded"] else "❌ No")
            meta_col3.metric("Final top_k", result["final_top_k"])

            if result.get("critique"):
                st.caption(f"**Self-critique:** {result['critique']}")

            st.subheader("Agent Steps")
            for step in agent_log:
                st.markdown(f"`{step}`")

            log_interaction(query, "agentic", result["answer"], conf)

elif run and not query.strip():
    st.warning("Please enter a question.")

# -----------------------------------------------------------------------
# Sidebar — sample queries
# -----------------------------------------------------------------------

with st.sidebar:
    st.header("Sample Queries")
    st.caption("Click to fill the input above, then press Ask.")

    samples = [
        "Where is the auth token generated?",
        "Which endpoint lists all users?",
        "How do I connect to the database?",
        "How does a client refresh an access token?",
        "Which fields are stored in the users table?",
        "What steps are needed to deploy the application?",
        "How do I open a pull request?",
        "Is there any mention of payment processing?",
        "Tell me a joke",
    ]

    for s in samples:
        st.code(s, language=None)

    st.divider()
    st.header("Documents Loaded")
    for fname, _ in bot.documents:
        folder = "custom_docs" if fname in ["DEPLOYMENT.md", "CONTRIBUTING.md", "ERRORS.md"] else "docs"
        st.markdown(f"- `{folder}/{fname}`")
