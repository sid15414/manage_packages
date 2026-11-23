import os
import uuid
from pathlib import Path
from urllib.parse import quote
import base64
import streamlit.components.v1 as components
import markdown

import streamlit as st
from dotenv import load_dotenv
from langchain_core.messages import AIMessage, HumanMessage

load_dotenv()

from myagent import build_graph  # noqa: E402  (after load_dotenv)

st.set_page_config(page_title="ManageOrders", page_icon="📦", layout="centered")


# ---------------------------------------------------------------- setup
def get_db_url() -> str:
    url = os.getenv("SUPABASE_DB_URL")
    if not url:
        try:
            url = st.secrets["SUPABASE_DB_URL"]
        except Exception:
            url = None
    if not url:
        st.error(
            "SUPABASE_DB_URL is not set. Add it to your .env file "
            "(or to .streamlit/secrets.toml) and restart."
        )
        st.stop()
    return url


@st.cache_resource(show_spinner="Connecting to the database…")
def get_graph():
    return build_graph(get_db_url())


graph = get_graph()


# ---------------------------------------------------------------- helpers
def text_of(content) -> str:
    """Message content can be a string or a list of content blocks."""
    if isinstance(content, str):
        return content
    parts = []
    for block in content or []:
        if isinstance(block, str):
            parts.append(block)
        elif isinstance(block, dict) and block.get("type") == "text":
            parts.append(block.get("text", ""))
    return "".join(parts)


def as_dict(order) -> dict:
    return order.model_dump(mode="json") if hasattr(order, "model_dump") else dict(order)


def make_config() -> dict:
    return {
        "configurable": {
            "thread_id": st.session_state.thread_id,
            "user_name": st.session_state.user_name,
        }
    }


def reset_conversation():
    st.session_state.thread_id = str(uuid.uuid4())
    st.session_state.history = []
    st.session_state.pending = None


def run_turn(user_text: str):
    """Send one message through the graph. Returns (reply_text, pending_orders | None)."""
    config = make_config()
    final = None

    for state in graph.stream(
        {"messages": [HumanMessage(content=user_text)]},
        config,
        stream_mode="values",
    ):
        message = state["messages"][-1]
        # Skip internal tool calls; keep only plain assistant replies
        if isinstance(message, AIMessage) and not message.tool_calls:
            final = message

    snapshot = graph.get_state(config)

    # Graph paused before human_feedback -> extracted orders need approval
    if snapshot.next:
        orders = [as_dict(item["order"]) for item in snapshot.values.get("order_details", [])]
        return "I found these order details. Do you want me to save them?", orders

    return (text_of(final.content) if final else ""), None


def resolve_approval(approved: bool) -> str:
    config = make_config()
    graph.update_state(config, {"approval_status": approved}, as_node="human_feedback")
    for _ in graph.stream(None, config, stream_mode="values"):
        pass
    return (
        "Order details approved and saved."
        if approved
        else "Okay, I won't save these order details."
    )


def render_order(order: dict):
    name = order.get("name") or "Unnamed item"
    st.markdown(f"**{name}**")
    rows = [
        ("Store", order.get("source")),
        ("Order ID", order.get("order_id")),
        ("Purchased", order.get("purchased_date")),
        ("Expected delivery", order.get("expected_delivery_date")),
        ("Delivery partner", order.get("delivery_partner")),
        ("Tracking URL", order.get("url")),
    ]
    for label, value in rows:
        st.markdown(f"{label}: {value or '_not available_'}")


# ---------------------------------------------------------------- state
if "thread_id" not in st.session_state:
    reset_conversation()
st.session_state.setdefault("user_name", "")
st.session_state.setdefault("pending", None)

# ---------------------------------------------------------------- sidebar
with st.sidebar:
    st.header("ManageOrders")

    # ------------------------------------------------------------
    # Recruiter README
    # Render readme.md as HTML and open it in a new tab
    # ------------------------------------------------------------
    readme_path = Path(__file__).parent / "readme.md"

    if readme_path.exists():
        readme_content = readme_path.read_text(encoding="utf-8")

        # Convert Markdown -> HTML
        readme_html = markdown.markdown(
            readme_content,
            extensions=[
                "fenced_code",
                "tables",
                "toc",
            ],
        )

        # Create a complete standalone HTML page
        html_page = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">

            <title>ManageOrders — For Recruiters</title>

            <style>
                body {{
                    font-family:
                        -apple-system,
                        BlinkMacSystemFont,
                        "Segoe UI",
                        Roboto,
                        Helvetica,
                        Arial,
                        sans-serif;

                    max-width: 900px;
                    margin: 0 auto;
                    padding: 40px 24px;
                    line-height: 1.6;
                    color: #24292f;
                    background: #ffffff;
                }}

                h1 {{
                    font-size: 2.2rem;
                    margin-bottom: 20px;
                    border-bottom: 1px solid #d0d7de;
                    padding-bottom: 10px;
                }}

                h2 {{
                    margin-top: 35px;
                    border-bottom: 1px solid #d8dee4;
                    padding-bottom: 6px;
                }}

                h3 {{
                    margin-top: 25px;
                }}

                p {{
                    margin: 12px 0;
                }}

                code {{
                    background: #f6f8fa;
                    padding: 2px 5px;
                    border-radius: 4px;
                    font-size: 0.9em;
                }}

                pre {{
                    background: #f6f8fa;
                    padding: 16px;
                    border-radius: 8px;
                    overflow-x: auto;
                }}

                pre code {{
                    background: transparent;
                    padding: 0;
                }}

                blockquote {{
                    margin: 20px 0;
                    padding: 10px 20px;
                    border-left: 4px solid #0969da;
                    background: #f6f8fa;
                }}

                table {{
                    width: 100%;
                    border-collapse: collapse;
                    margin: 20px 0;
                }}

                th,
                td {{
                    border: 1px solid #d0d7de;
                    padding: 8px 12px;
                    text-align: left;
                }}

                th {{
                    background: #f6f8fa;
                }}

                a {{
                    color: #0969da;
                }}

                @media (max-width: 600px) {{
                    body {{
                        padding: 20px 15px;
                    }}
                }}
            </style>
        </head>

        <body>
            {readme_html}
        </body>
        </html>
        """

        html_b64 = base64.b64encode(
            html_page.encode("utf-8")
        ).decode("utf-8")

        components.html(
    f"""
    <script>
        function openReadme() {{
            const html = {readme_html!r};

            const fullPage = `
                <!DOCTYPE html>
                <html>
                <head>
                    <meta charset="UTF-8">
                    <meta name="viewport" content="width=device-width, initial-scale=1.0">
                    <title>ManageOrders — For Recruiters</title>
                    <style>
                        body {{
                            font-family: -apple-system, BlinkMacSystemFont,
                                "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
                            max-width: 900px;
                            margin: 0 auto;
                            padding: 40px 24px;
                            line-height: 1.6;
                            color: #24292f;
                            background: #ffffff;
                        }}

                        h1 {{
                            font-size: 2.2rem;
                            border-bottom: 1px solid #d0d7de;
                            padding-bottom: 10px;
                        }}

                        h2 {{
                            margin-top: 35px;
                            border-bottom: 1px solid #d8dee4;
                            padding-bottom: 6px;
                        }}

                        code {{
                            background: #f6f8fa;
                            padding: 2px 5px;
                            border-radius: 4px;
                        }}

                        pre {{
                            background: #f6f8fa;
                            padding: 16px;
                            border-radius: 8px;
                            overflow-x: auto;
                        }}

                        table {{
                            width: 100%;
                            border-collapse: collapse;
                            margin: 20px 0;
                        }}

                        th, td {{
                            border: 1px solid #d0d7de;
                            padding: 8px 12px;
                            text-align: left;
                        }}

                        th {{
                            background: #f6f8fa;
                        }}

                        a {{
                            color: #0969da;
                        }}
                    </style>
                </head>
                <body>
                    ${{html}}
                </body>
                </html>
            `;

            const blob = new Blob(
                [fullPage],
                {{ type: "text/html;charset=UTF-8" }}
            );

            const url = URL.createObjectURL(blob);
            window.open(url, "_blank");
        }}
    </script>

    <button
        onclick="openReadme()"
        style="
            width: 100%;
            padding: 10px 12px;
            border: 1px solid #d1d5db;
            border-radius: 8px;
            background: white;
            cursor: pointer;
            font-size: 14px;
            font-weight: 600;
            color: #1f2937;
        "
    >
        📖 Readme — For Recruiters
    </button>
    """,
    height=55,
)
    name = st.text_input(
        "Your name",
        value=st.session_state.user_name,
    ).strip()

    if name != st.session_state.user_name:
        st.session_state.user_name = name
        reset_conversation()  # orders are stored per user, so start a fresh thread

    if st.button("New conversation", use_container_width=True):
        reset_conversation()
        st.rerun()

    if st.session_state.user_name:
        with st.expander("Saved orders", expanded=False):
            saved = graph.store.search((st.session_state.user_name, "orders"))
            if not saved:
                st.caption("No saved orders yet.")
            for item in saved:
                render_order(item.value)
                st.divider()

# ---------------------------------------------------------------- main
st.title("📦 ManageOrders")

if not st.session_state.user_name:
    st.info("Enter your name in the sidebar to start. Your saved orders are kept under that name.")
    st.stop()

for msg in st.session_state.history:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# Approval card (shown while the graph is paused)
if st.session_state.pending:
    with st.chat_message("assistant"):
        with st.container(border=True):
            for order in st.session_state.pending:
                render_order(order)
        approve_col, reject_col, _ = st.columns([1, 1, 3])
        if approve_col.button("Save", type="primary", use_container_width=True):
            with st.spinner("Saving…"):
                reply = resolve_approval(True)
            st.session_state.history.append({"role": "assistant", "content": reply})
            st.session_state.pending = None
            st.rerun()
        if reject_col.button("Discard", use_container_width=True):
            with st.spinner("Discarding…"):
                reply = resolve_approval(False)
            st.session_state.history.append({"role": "assistant", "content": reply})
            st.session_state.pending = None
            st.rerun()

prompt = st.chat_input(
    "Tell me about an order, or ask about your orders",
    disabled=bool(st.session_state.pending),
)

if prompt:
    st.session_state.history.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Thinking…"):
            reply, pending = run_turn(prompt)
        st.markdown(reply)

    st.session_state.history.append({"role": "assistant", "content": reply})
    st.session_state.pending = pending
    if pending:
        st.rerun()  # redraw so the Save / Discard card appears
