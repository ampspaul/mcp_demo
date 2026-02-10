import asyncio
import uuid
import streamlit as st
from langgraph.checkpoint.memory import InMemorySaver

# ✅ Agent lives in agent.py (your existing file)
from agent_app.agent import build_graph

st.set_page_config(page_title="Leave Agent", page_icon="🧑‍💼", layout="centered")
st.title("🧑‍💼 Leave Agent")

# ---------------------------
# Session init
# ---------------------------
if "thread_id" not in st.session_state:
    st.session_state.thread_id = str(uuid.uuid4())

if "messages" not in st.session_state:
    st.session_state.messages = []  # {"role": "user"/"assistant", "content": str}

if "email_from" not in st.session_state:
    st.session_state.email_from = ""

if "app" not in st.session_state:
    checkpointer = InMemorySaver()
    st.session_state.app = build_graph(checkpointer)


# ---------------------------
# Sidebar
# ---------------------------
with st.sidebar:
    st.header("Session")
    st.caption("This thread_id is used for LangGraph checkpoint memory.")
    st.code(st.session_state.thread_id)

    st.session_state.email_from = st.text_input(
        "Your email (email_from)",
        value=st.session_state.email_from,
        placeholder="alice@company.com",
    )

    debug = st.toggle("Show debug state", value=False)

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Reset chat"):
            st.session_state.messages = []
            st.rerun()
    with col2:
        if st.button("New thread"):
            st.session_state.thread_id = str(uuid.uuid4())
            st.session_state.messages = []
            st.rerun()


# ---------------------------
# Render chat history
# ---------------------------
for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])


# ---------------------------
# Run agent (async -> sync wrapper)
# ---------------------------
async def _run_agent(user_text: str) -> dict:
    app = st.session_state.app
    thread_id = st.session_state.thread_id
    email_from = (st.session_state.email_from or "unknown@company.com").strip()

    return await app.ainvoke(
        {"email_from": email_from, "email_body": user_text},
        config={"configurable": {"thread_id": thread_id}},
    )


def run_agent(user_text: str) -> dict:
    # Streamlit runs sync; safest is asyncio.run per call
    return asyncio.run(_run_agent(user_text))


# ---------------------------
# Chat input
# ---------------------------
prompt = st.chat_input("Type: leave from 3rd March to 6th March 2026")

if prompt:
    # show user msg
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # call agent
    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            result = run_agent(prompt)

        # Prefer standard keys from your nodes
        assistant_text = (
            result.get("message")
            or result.get("final_message")
            or (result.get("email_body_out") if isinstance(result.get("email_body_out"), str) else None)
            or "Done."
        )

        st.markdown(assistant_text)
        st.session_state.messages.append({"role": "assistant", "content": assistant_text})

        if debug:
            st.divider()
            st.caption("Debug (selected fields)")
            st.json(
                {
                    "intent": result.get("intent"),
                    "validate_employee": result.get("validate_employee"),
                    "get_leave_balance": result.get("get_leave_balance"),
                    "loa_created": result.get("loa_created"),
                    "ok": result.get("ok"),
                    "error": result.get("error"),
                }
            )
