import streamlit as st
import pandas as pd
import numpy as np
import json
import os
import re
import urllib
from datetime import datetime
from groq import Groq

from sqlalchemy import create_engine


# ─────────────────────────────────────────────────────────────
# PAGE CONFIG
# ─────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="DownBot — Factory Intelligence",
    page_icon="⚙️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────────────────────
# CUSTOM CSS
# ─────────────────────────────────────────────────────────────

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;700&family=Syne:wght@400;700;800&display=swap');

:root {
    --bg: #0d0f14;
    --surface: #161920;
    --border: #252a35;
    --accent: #00e5a0;
    --accent2: #ff6b35;
    --text: #e8eaf0;
    --muted: #7a8099;
}

html, body, [class*="css"] {
    font-family: 'Syne', sans-serif;
    background: var(--bg) !important;
    color: var(--text);
}

.stApp {
    background: var(--bg) !important;
}

.main-header {
    display: flex;
    align-items: center;
    gap: 14px;
    padding: 18px 0 10px;
    border-bottom: 1px solid var(--border);
    margin-bottom: 20px;
}

.main-header .logo {
    font-size: 2.2rem;
}

.main-header h1 {
    margin: 0;
    font-size: 1.7rem;
    font-weight: 800;
    background: linear-gradient(90deg, var(--accent), #00b8ff);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
}

.main-header p {
    margin: 0;
    font-size: 0.8rem;
    color: var(--muted);
    font-family: 'JetBrains Mono', monospace;
}

.msg-user {
    background: linear-gradient(135deg, #1a2a3a, #1e2d42);
    border: 1px solid #2a3f5a;
    border-radius: 18px 18px 4px 18px;
    padding: 14px 18px;
    margin: 8px 0 8px 60px;
    color: var(--text);
}

.msg-bot {
    background: var(--surface);
    border: 1px solid var(--border);
    border-left: 3px solid var(--accent);
    border-radius: 4px 18px 18px 18px;
    padding: 14px 18px;
    margin: 8px 60px 8px 0;
    color: var(--text);
}

.msg-meta {
    font-size: 0.72rem;
    color: var(--muted);
    font-family: 'JetBrains Mono', monospace;
    margin-bottom: 4px;
}

.kpi-grid {
    display: grid;
    grid-template-columns: repeat(2,1fr);
    gap: 10px;
    margin-bottom: 16px;
}

.kpi-card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 12px 14px;
    border-top: 2px solid var(--accent);
}

.kpi-label {
    font-size: 0.7rem;
    color: var(--muted);
    font-family: 'JetBrains Mono', monospace;
    text-transform: uppercase;
}

.kpi-value {
    font-size: 1.2rem;
    font-weight: 800;
    color: var(--accent);
}

section[data-testid="stSidebar"] {
    background: var(--surface) !important;
    border-right: 1px solid var(--border);
}

.stButton > button {
    background: transparent !important;
    border: 1px solid var(--accent) !important;
    color: var(--accent) !important;
    border-radius: 6px !important;
}

.stButton > button:hover {
    background: var(--accent) !important;
    color: black !important;
}

.stTextInput > div > div > input,
.stChatInput textarea {
    background: var(--surface) !important;
    border: 1px solid var(--border) !important;
    color: var(--text) !important;
    border-radius: 10px !important;
}

.personality-active {
    display: inline-block;
    padding: 3px 10px;
    background: rgba(0,229,160,0.12);
    border: 1px solid var(--accent);
    border-radius: 20px;
    font-size: 0.72rem;
    color: var(--accent);
    font-family: 'JetBrains Mono', monospace;
}
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────
# MSSQL CONFIG
# ─────────────────────────────────────────────────────────────

DB_SERVER   = "YOUR_SERVER_IP"
DB_DATABASE = "Grafana"
DB_USERNAME = "10.111.0.16\SQLEXPRESS"
DB_PASSWORD = "Rbs@54321"

connection_string = (
    f"DRIVER={{ODBC Driver 17 for SQL Server}};"
    f"SERVER={DB_SERVER};"
    f"DATABASE={DB_DATABASE};"
    f"UID={DB_USERNAME};"
    f"PWD={DB_PASSWORD};"
    "TrustServerCertificate=yes;"
)


engine = create_engine(
    f"mssql+pymssql://{DB_USERNAME}:{DB_PASSWORD}@{DB_SERVER}/{DB_DATABASE}"
)




# ─────────────────────────────────────────────────────────────
# LOAD DATA
# ─────────────────────────────────────────────────────────────

@st.cache_data(ttl=30)
def load_data():

    query = """
    SELECT
        Plant_ID,
        Line_ID,
        Machine_ID,
        Machine_Name,
        Shift,
        Hour,
        type,
        Start_time,
        Stop_time,
        down_time,
        Breakdown_Reason,
        Global_reason
    FROM downtime
    WHERE Start_time >= DATEADD(day, -30, GETDATE())
    """

    df = pd.read_sql(query, engine)

    df["Start_time"] = pd.to_datetime(
        df["Start_time"],
        errors="coerce"
    )

    df["Stop_time"] = pd.to_datetime(
        df["Stop_time"],
        errors="coerce"
    )

    df["down_time"] = pd.to_numeric(
        df["down_time"],
        errors="coerce"
    )

    return df


# ─────────────────────────────────────────────────────────────
# DATA CONTEXT
# ─────────────────────────────────────────────────────────────

def build_data_context(df):

    total_dt = df["down_time"].sum()
    avg_dt = df["down_time"].mean()

    top_reason = (
        df.groupby("Breakdown_Reason")["down_time"]
        .sum()
        .idxmax()
    )

    top_global = (
        df.groupby("Global_reason")["down_time"]
        .sum()
        .idxmax()
    )

    by_shift = (
        df.groupby("Shift")["down_time"]
        .sum()
        .to_dict()
    )

    by_reason = (
        df.groupby("Breakdown_Reason")["down_time"]
        .sum()
        .nlargest(5)
        .to_dict()
    )

    by_global = (
        df.groupby("Global_reason")["down_time"]
        .sum()
        .to_dict()
    )

    type_map = {
        3: "Unplanned",
        4: "Planned"
    }

    by_type = (
        df["type"]
        .map(type_map)
        .value_counts()
        .to_dict()
    )

    machine_map = (
        df[
            [
                "Plant_ID",
                "Line_ID",
                "Machine_ID",
                "Machine_Name"
            ]
        ]
        .drop_duplicates()
        .sort_values(
            ["Plant_ID", "Line_ID", "Machine_ID"]
        )
    )

    machine_text = machine_map.to_string(index=False)

    sample_rows = df.head(5).to_string(index=False)

    ctx = f"""
=== FACTORY DOWNTIME DATABASE CONTEXT ===

Total records: {len(df)}

Date range:
{df['Start_time'].min()}
to
{df['Start_time'].max()}

Machine Hierarchy:
{machine_text}

Total downtime seconds:
{total_dt:,.0f}

Average downtime:
{avg_dt:.1f}

Top breakdown reason:
{top_reason}

Top global category:
{top_global}

Downtime by shift:
{json.dumps(by_shift, indent=2)}

Top 5 breakdown reasons:
{json.dumps(by_reason, indent=2)}

Downtime by global reason:
{json.dumps(by_global, indent=2)}

Planned vs Unplanned:
{json.dumps(by_type, indent=2)}

Sample records:
{sample_rows}

=== END CONTEXT ===
"""

    return ctx


# ─────────────────────────────────────────────────────────────
# KPI
# ─────────────────────────────────────────────────────────────

def compute_kpis(df):

    total_sec = df["down_time"].sum()

    events = len(df)

    unplanned = len(
        df[df["type"] == 3]
    )

    top_reason = (
        df.groupby("Breakdown_Reason")["down_time"]
        .sum()
        .idxmax()
    )

    return {
        "total_hours": f"{total_sec/3600:.1f}h",
        "events": str(events),
        "unplanned": f"{unplanned}/{events}",
        "top_cause": top_reason[:18]
    }


# ─────────────────────────────────────────────────────────────
# PERSONALITIES
# ─────────────────────────────────────────────────────────────

PERSONALITIES = {

    "🔬 Analyst": (
        "analyst",
        "You are a precise manufacturing analyst."
    ),

    "🤖 Engineer": (
        "engineer",
        "You are a practical factory engineer."
    ),

    "📊 Executive": (
        "executive",
        "You are an operations advisor."
    )
}


SYSTEM_TEMPLATE = """
You are DownBot,
an industrial AI assistant.

PERSONALITY:
{personality_desc}

LIVE DATA:
{data_context}

RULES:
1. Use actual data only
2. Use exact numbers
3. Be concise
4. Give actionable insights
5. Never hallucinate
"""


# ─────────────────────────────────────────────────────────────
# GROQ
# ─────────────────────────────────────────────────────────────

@st.cache_resource
def get_client():

    api_key = (
        os.environ.get("GROQ_API_KEY")
        or st.secrets.get("GROQ_API_KEY", "")
    )

    if not api_key:
        return None

    return Groq(api_key=api_key)


def chat(client, messages, system_prompt):

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {
                "role": "system",
                "content": system_prompt
            }
        ] + messages,
        max_tokens=1500,
    )

    return response.choices[0].message.content


# ─────────────────────────────────────────────────────────────
# SESSION
# ─────────────────────────────────────────────────────────────

if "messages" not in st.session_state:
    st.session_state.messages = []

if "personality" not in st.session_state:
    st.session_state.personality = "🔬 Analyst"


# ─────────────────────────────────────────────────────────────
# LOAD DATA
# ─────────────────────────────────────────────────────────────

df = load_data()


# ─────────────────────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────────────────────

with st.sidebar:

    st.markdown("# ⚙️ DownBot")

    st.markdown(
        f"Loaded Records: {len(df)}"
    )

    st.divider()

    st.markdown("## Personality")

    for label in PERSONALITIES:

        if st.button(label, use_container_width=True):
            st.session_state.personality = label
            st.rerun()

    st.markdown(
        f"""
        <div class="personality-active">
        {st.session_state.personality}
        </div>
        """,
        unsafe_allow_html=True
    )

    st.divider()

    st.markdown("## 🏭 Factory Filters")

    # PLANT FILTER

    plant_options = sorted(
        df["Plant_ID"]
        .dropna()
        .unique()
    )

    selected_plant = st.selectbox(
        "Plant",
        ["All"] + list(plant_options)
    )

    filtered_df = df.copy()

    if selected_plant != "All":

        filtered_df = filtered_df[
            filtered_df["Plant_ID"] == selected_plant
        ]

    # LINE FILTER

    line_options = sorted(
        filtered_df["Line_ID"]
        .dropna()
        .unique()
    )

    selected_line = st.selectbox(
        "Line",
        ["All"] + list(line_options)
    )

    if selected_line != "All":

        filtered_df = filtered_df[
            filtered_df["Line_ID"] == selected_line
        ]

    # MACHINE FILTER

    machine_options = sorted(
        filtered_df["Machine_Name"]
        .dropna()
        .unique()
    )

    selected_machine = st.selectbox(
        "Machine",
        ["All"] + list(machine_options)
    )

    if selected_machine != "All":

        filtered_df = filtered_df[
            filtered_df["Machine_Name"]
            == selected_machine
        ]

    st.divider()

    # KPI

    kpis = compute_kpis(filtered_df)

    st.markdown(f"""
    <div class="kpi-grid">

        <div class="kpi-card">
            <div class="kpi-label">
            Total Downtime
            </div>
            <div class="kpi-value">
            {kpis['total_hours']}
            </div>
        </div>

        <div class="kpi-card">
            <div class="kpi-label">
            Events
            </div>
            <div class="kpi-value">
            {kpis['events']}
            </div>
        </div>

        <div class="kpi-card">
            <div class="kpi-label">
            Unplanned
            </div>
            <div class="kpi-value">
            {kpis['unplanned']}
            </div>
        </div>

        <div class="kpi-card">
            <div class="kpi-label">
            Top Cause
            </div>
            <div class="kpi-value">
            {kpis['top_cause']}
            </div>
        </div>

    </div>
    """, unsafe_allow_html=True)

    st.divider()

    if st.button("🗑️ Clear Chat"):

        st.session_state.messages = []
        st.rerun()


# ─────────────────────────────────────────────────────────────
# MAIN HEADER
# ─────────────────────────────────────────────────────────────

st.markdown("""
<div class="main-header">

<div class="logo">
⚙️
</div>

<div>

<h1>
DownBot — Factory Intelligence
</h1>

<p>
RAG-powered downtime analysis
</p>

</div>

</div>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────
# API CHECK
# ─────────────────────────────────────────────────────────────

client = get_client()

if not client:

    st.error(
        "GROQ_API_KEY not found"
    )

    st.stop()


# ─────────────────────────────────────────────────────────────
# CONTEXT
# ─────────────────────────────────────────────────────────────

data_ctx = build_data_context(filtered_df)


# ─────────────────────────────────────────────────────────────
# CHAT HISTORY
# ─────────────────────────────────────────────────────────────

if not st.session_state.messages:

    st.markdown("""
    <div class="msg-bot">

    👋 <strong>Welcome to DownBot</strong>

    Ask anything about:
    <br><br>

    • Downtime trends
    <br>
    • Machine failures
    <br>
    • Shift comparison
    <br>
    • Planned vs unplanned
    <br>
    • Root-cause insights

    </div>
    """, unsafe_allow_html=True)

else:

    for msg in st.session_state.messages:

        if msg["role"] == "user":

            st.markdown(
                f"""
                <div class="msg-meta">
                You · {msg['ts']}
                </div>

                <div class="msg-user">
                {msg['content']}
                </div>
                """,
                unsafe_allow_html=True
            )

        else:

            st.markdown(
                f"""
                <div class="msg-meta">
                ⚙️ DownBot · {msg['ts']}
                </div>

                <div class="msg-bot">
                {msg['content']}
                </div>
                """,
                unsafe_allow_html=True
            )


# ─────────────────────────────────────────────────────────────
# CHAT INPUT
# ─────────────────────────────────────────────────────────────

user_input = st.chat_input(
    "Ask about downtime..."
)

if user_input:

    ts = datetime.now().strftime("%H:%M")

    st.session_state.messages.append({
        "role": "user",
        "content": user_input,
        "ts": ts
    })

    _, personality_desc = PERSONALITIES[
        st.session_state.personality
    ]

    system_prompt = SYSTEM_TEMPLATE.format(
        personality_desc=personality_desc,
        data_context=data_ctx
    )

    history = [
        {
            "role": m["role"],
            "content": m["content"]
        }
        for m in st.session_state.messages
    ]

    with st.spinner("Analysing..."):

        try:

            answer = chat(
                client,
                history,
                system_prompt
            )

        except Exception as e:

            answer = f"⚠️ Error: {e}"

    st.session_state.messages.append({

        "role": "assistant",
        "content": answer,
        "ts": ts

    })

    st.rerun()
