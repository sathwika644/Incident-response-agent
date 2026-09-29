import html
import os
import re
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

try:
    from hindsight_client import Hindsight
except ImportError:
    Hindsight = None

BASE = Path(__file__).parent
DATA = next((p for p in (BASE / "data" / "incidents.csv", BASE / "incidents.csv") if p.exists()), None)
BANK_ID = os.getenv("HINDSIGHT_BANK_ID", "incident-response-demo")
HINDSIGHT_URL = os.getenv("HINDSIGHT_API_URL", "https://api.hindsight.vectorize.io")
HINDSIGHT_KEY = os.getenv("HINDSIGHT_API_KEY", "")

st.set_page_config(page_title="Incident Memory Agent", page_icon="⚡", layout="wide")

if DATA is None:
    st.error("incidents.csv not found. Put it in `data/incidents.csv` next to app.py.")
    st.stop()

st.markdown("""
<style>
[data-testid="stAppViewContainer"] { background: radial-gradient(circle at 0% 0%, #172033 0%, #070b12 42%, #04060a 100%); }
[data-testid="stHeader"] { background: transparent; }
.block-container { max-width: 1450px; padding-top: 1.2rem; }
.hero { padding: 28px 32px; border-radius: 24px; background: linear-gradient(135deg,rgba(30,41,59,.92),rgba(10,15,25,.82)); border:1px solid rgba(255,255,255,.10); box-shadow:0 18px 60px rgba(0,0,0,.30); }
.hero h1 { margin: 6px 0 4px; font-size:2.35rem; }
.hero p { color:#aab6c7; margin:0; font-size:1rem; }
.badge { display:inline-block; padding:5px 11px; border-radius:999px; background:#123b2a; color:#70e3a5; border:1px solid #205c42; font-size:.76rem; font-weight:800; letter-spacing:.05em; }
.flow { display:flex; gap:8px; flex-wrap:wrap; margin-top:18px; align-items:center; }
.flow span { padding:7px 10px; border-radius:10px; background:rgba(148,163,184,.06); border:1px solid rgba(148,163,184,.15); color:#7d8aa0; font-size:.82rem; transition:all .3s; }
.flow span.done { background:rgba(56,189,248,.10); border-color:rgba(56,189,248,.35); color:#b9e9ff; }
.flow span.win { background:rgba(16,185,129,.14); border-color:rgba(16,185,129,.5); color:#6ee7b7; box-shadow:0 0 18px rgba(16,185,129,.25); }
.flow i { color:#475569; font-style:normal; }
.card { padding:18px; border-radius:16px; background:rgba(15,23,42,.72); border:1px solid rgba(255,255,255,.09); min-height:105px; }
.metric { font-size:1.55rem; font-weight:800; margin-top:5px; }
.muted { color:#94a3b8; font-size:.84rem; }
.memory { padding:15px 17px; border-radius:14px; background:linear-gradient(135deg,rgba(76,29,149,.22),rgba(30,41,59,.66)); border:1px solid rgba(167,139,250,.28); margin:8px 0; line-height:1.55; }
.memory b { color:#c4b5fd; }
.memory .bad { color:#fca5a5; } .memory .good { color:#86efac; }
.trace { padding:10px 13px; border-left:3px solid #38bdf8; background:rgba(56,189,248,.05); margin:7px 0; border-radius:6px; }
.agent { padding:20px; border-radius:17px; background:rgba(2,6,23,.82); border:1px solid rgba(56,189,248,.20); box-shadow:0 10px 35px rgba(0,0,0,.16); line-height:1.6; }
.agent.warm { border-color:rgba(16,185,129,.45); box-shadow:0 0 30px rgba(16,185,129,.12); }
.lesson { padding:14px 16px; border-radius:13px; background:rgba(16,185,129,.07); border:1px solid rgba(16,185,129,.20); margin-bottom:12px; }
.pill { display:inline-block; padding:3px 10px; border-radius:999px; font-size:.72rem; font-weight:800; letter-spacing:.05em; }
</style>
""", unsafe_allow_html=True)


def esc(x):
    return html.escape(str(x))


@st.cache_data
def load_incidents(path):
    d = pd.read_csv(path)
    d["latency_s"] = d["latency"].str.replace("s", "", regex=False).astype(float)
    d["error_pct"] = d["error_rate"].str.replace("%", "", regex=False).astype(float)
    return d


df = load_incidents(DATA)

SEV = {"CRITICAL": ("🔴", "#ef4444"), "HIGH": ("🟠", "#f97316"), "MEDIUM": ("🟡", "#eab308")}


def get_hindsight():
    if Hindsight is None or not HINDSIGHT_KEY:
        return None
    return Hindsight(base_url=HINDSIGHT_URL, api_key=HINDSIGHT_KEY)


def ensure_bank(client):
    if not client or st.session_state.get("bank_ready"):
        return
    try:
        client.create_bank(bank_id=BANK_ID, name="Incident Response Demo Memory")
    except Exception:
        pass  # bank probably exists already
    st.session_state.bank_ready = True


def memory_text(mem):
    if isinstance(mem, dict):
        return mem.get("text", "")
    return getattr(mem, "text", str(mem))


def field(text, name):
    m = re.search(rf"^{name}:\s*(.+)$", text, re.M | re.I)
    return m.group(1).strip() if m else None


def render_memory(mem):
    t = memory_text(mem)
    inc, svc = field(t, "Incident"), field(t, "Service")
    if not inc:  # live Hindsight observations may be free text
        return f'<div class="memory"><b>RELEVANT EXPERIENCE</b><br>{esc(t[:600])}</div>'
    return (
        f'<div class="memory"><b>RELEVANT EXPERIENCE · {esc(inc)} · {esc(svc)}</b><br>'
        f'<b>Root cause:</b> {esc(field(t, "Root cause"))}<br>'
        f'<span class="bad">✗ Failed:</span> {esc(field(t, "Failed action"))} &nbsp; '
        f'<span class="good">✓ Worked:</span> {esc(field(t, "Successful action"))}<br>'
        f'<span class="muted">Lesson: {esc(field(t, "Lesson"))}</span></div>'
    )


def recall_memory(client, query, current_service):
    if client:
        try:
            result = client.recall(bank_id=BANK_ID, query=query, types=["experience", "observation", "world"])
            return getattr(result, "results", []) or []
        except Exception as e:
            st.session_state["memory_error"] = str(e)
            return []
    # Local rehearsal mode: recall retained experiences for the same service.
    return [m for m in st.session_state.local_memory if m["service"] == current_service.lower()]


def retain_incident(client, row):
    content = f"""Production incident experience
Incident: {row['incident_id']}
Service: {row['service']}
Severity: {row['severity']}
Symptoms: {row['symptoms']}
Recent deployment: {row['deployment']}
Observed logs: {row['logs']}
Root cause: {row['root_cause']}
Failed action: {row['failed_action']}
Successful action: {row['successful_action']}
Outcome: {row['outcome']}
Lesson: {row['lesson']}
"""
    if client:
        try:
            client.retain(
                bank_id=BANK_ID,
                content=content,
                context="production incident investigation and remediation",
                metadata={"incident_id": str(row["incident_id"]), "service": str(row["service"])},
            )
            return True
        except Exception as e:
            st.session_state["memory_error"] = str(e)
            return False
    if str(row["incident_id"]) not in {m["incident_id"] for m in st.session_state.local_memory}:
        st.session_state.local_memory.append({
            "incident_id": str(row["incident_id"]),
            "service": str(row["service"]).lower(),
            "text": content,
        })
    return True


def reset_incident_state():
    st.session_state.investigated = False
    st.session_state.memories = []
    st.session_state.trace = []
    st.session_state.current_incident = None


for k, v in {"selected_incident": 0, "investigated": False, "memories": [], "retained": set(),
             "local_memory": [], "trace": [], "current_incident": None}.items():
    st.session_state.setdefault(k, v)

client = get_hindsight()
ensure_bank(client)

row = df.iloc[st.session_state.selected_incident]
rid = str(row.incident_id)
this_investigated = st.session_state.investigated and st.session_state.current_incident == rid
used_memory = this_investigated and bool(st.session_state.memories)

# Animated learning-loop stepper
stages = ["🚨 INCIDENT", "🧠 HINDSIGHT RECALL", "🔎 INVESTIGATE", "🛠️ REMEDIATE", "💾 HINDSIGHT RETAIN", "📈 IMPROVE"]
done = {0}
if this_investigated:
    done |= {1, 2, 3}
if rid in st.session_state.retained:
    done.add(4)
if used_memory:
    done.add(5)
chips = "<i>→</i>".join(
    f'<span class="{"win" if (i == 5 and i in done) else "done" if i in done else ""}">{s}</span>'
    for i, s in enumerate(stages)
)
st.markdown(f"""
<div class="hero">
  <span class="badge">● INCIDENT RESPONSE AGENT</span>
  <h1>⚡ Incident Memory Agent</h1>
  <p>Investigate production incidents, learn from remediation history, and reuse that experience on the next incident.</p>
  <div class="flow">{chips}</div>
</div>
""", unsafe_allow_html=True)

with st.sidebar:
    st.markdown("### 🎬 Demo Control")
    st.caption("Recommended: investigate INC-001, retain its experience, then investigate INC-002.")
    options = [f"{r.incident_id} · {r.service}" for r in df.itertuples()]
    choice = st.selectbox("Active incident", options, index=st.session_state.selected_incident)
    new_index = options.index(choice)
    if new_index != st.session_state.selected_incident:
        st.session_state.selected_incident = new_index
        reset_incident_state()
        st.rerun()

    st.divider()
    st.markdown("### 🧠 Hindsight Memory")
    if client:
        st.success("LIVE · Hindsight connected")
        st.caption(f"Memory bank: `{BANK_ID}`")
    else:
        st.warning("LOCAL REHEARSAL MODE")
        st.caption("The UI is interactive locally. Set HINDSIGHT_API_KEY in `.env` for real persistent memory.")

    if st.button("🔄 Reset demo", width="stretch"):
        st.session_state.retained = set()
        st.session_state.local_memory = []
        reset_incident_state()
        st.session_state.pop("memory_error", None)
        st.rerun()

retained_count = len(st.session_state.retained)
mem_state = "WARM" if retained_count else "COLD"
mem_color = "#f59e0b" if retained_count else "#60a5fa"
icon, sev_color = SEV.get(str(row.severity).upper(), ("⚪", "#94a3b8"))

c1, c2, c3, c4, c5 = st.columns(5)
c1.markdown(f'<div class="card"><div class="muted">SEVERITY</div><div class="metric" style="color:{sev_color}">{icon} {esc(row.severity)}</div></div>', unsafe_allow_html=True)
c2.markdown(f'<div class="card"><div class="muted">SERVICE</div><div class="metric">{esc(row.service)}</div></div>', unsafe_allow_html=True)
c3.markdown(f'<div class="card"><div class="muted">P95 LATENCY</div><div class="metric">{esc(row.latency)}</div></div>', unsafe_allow_html=True)
c4.markdown(f'<div class="card"><div class="muted">ERROR RATE</div><div class="metric" style="color:#f87171">{esc(row.error_rate)}</div></div>', unsafe_allow_html=True)
c5.markdown(f'<div class="card"><div class="muted">MEMORY · {retained_count} SAVED</div><div class="metric" style="color:{mem_color}">🧠 {mem_state}</div></div>', unsafe_allow_html=True)

st.write("")
left, right = st.columns([1.0, 1.35])

with left:
    st.markdown("### 🚨 Active Incident")
    st.markdown(f"""
    <div class="card">
      <h3>{esc(row.incident_id)} · {esc(row.title)}</h3>
      <p class="muted">{esc(row.symptoms)}</p>
      <hr style="border-color:rgba(255,255,255,.08)">
      <b>Recent deployment</b><br>{esc(row.deployment)}<br><br>
      <b>Observed telemetry</b>
      <pre style="white-space:pre-wrap">{esc(row.logs)}</pre>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("### 📊 Incident Comparison")
    chart_df = df.assign(selected=df["incident_id"] == rid)
    def bar(col, title, color):
        return (alt.Chart(chart_df).mark_bar(cornerRadiusTopLeft=5, cornerRadiusTopRight=5)
                .encode(x=alt.X("incident_id:N", title=None, axis=alt.Axis(labelAngle=0)),
                        y=alt.Y(f"{col}:Q", title=title),
                        color=alt.condition("datum.selected", alt.value(color), alt.value("#334155")),
                        tooltip=["incident_id", "service", col])
                .properties(height=170))
    b1, b2 = st.columns(2)
    b1.altair_chart(bar("latency_s", "Latency (s)", "#38bdf8"), width="stretch")
    b2.altair_chart(bar("error_pct", "Error rate (%)", "#f87171"), width="stretch")

    st.dataframe(df[["incident_id", "service", "severity", "deployment", "outcome"]], width="stretch", hide_index=True)

with right:
    st.markdown("### 🤖 Agent Investigation")
    st.caption("The agent uses the current incident + prior experience. Hindsight is the memory layer.")

    if st.button("🔎 Investigate with Memory", type="primary", width="stretch"):
        query = (
            f"Find previous production incidents similar to {row.service}. "
            f"Current symptoms: {row.symptoms}. Deployment: {row.deployment}. "
            f"Look specifically for prior root causes, failed remediation attempts, successful actions, and lessons."
        )
        with st.spinner("Recalling incident experience and correlating telemetry..."):
            memories = recall_memory(client, query, str(row.service))
        st.session_state.memories = memories
        st.session_state.investigated = True
        st.session_state.current_incident = rid
        trace = [
            "Ingested current incident symptoms, deployment and telemetry",
            "Queried Hindsight for similar production experience",
            f"Retrieved {len(memories)} relevant memory match(es)",
        ]
        if memories:
            trace.append("Used recalled experience to avoid repeating a known failed action")
        st.session_state.trace = trace
        st.rerun()

    if this_investigated:
        memories = st.session_state.memories

        st.markdown("#### 🧠 Hindsight Recall")
        if memories:
            for mem in memories[:3]:
                st.markdown(render_memory(mem), unsafe_allow_html=True)
        else:
            st.info("No matching experience was recalled. This is the agent's cold-start investigation.")

        st.markdown("#### 🔬 Investigation Trace")
        for step in st.session_state.trace:
            st.markdown(f'<div class="trace">✓ {esc(step)}</div>', unsafe_allow_html=True)

        if memories:
            top = memory_text(memories[0])
            prior = field(top, "Incident") or "a previous incident"
            failed = field(top, "Failed action") or row.failed_action
            worked = field(top, "Successful action") or row.successful_action
            recommendation = (f"Check <b>{esc(str(row.root_cause).lower())}</b> first. "
                              f"Do <b>NOT</b> repeat “{esc(failed)}” — it was ineffective in {esc(prior)}. "
                              + (f"Roll back the current release <b>{esc(row.deployment)}</b> — the same fix that resolved {esc(prior)}."
                                 if worked.lower().startswith("rollback")
                                 else f"Apply “{esc(worked)}”, which resolved {esc(prior)}."))
            confidence = '<span class="pill" style="background:#064e3b;color:#6ee7b7">HIGH</span> historical experience corroborates the current telemetry'
            cls = "agent warm"
        else:
            recommendation = f"Start with deployment correlation and resource saturation. Candidate remediation: “{esc(row.successful_action)}”."
            confidence = '<span class="pill" style="background:#78350f;color:#fcd34d">MEDIUM</span> current telemetry only'
            cls = "agent"

        st.markdown("#### 💡 Agent Recommendation")
        st.markdown(f"""
        <div class="{cls}">
          <b>Likely root cause</b><br>{esc(row.root_cause)}<br><br>
          <b>Recommended action</b><br>{recommendation}<br><br>
          <b>Confidence</b><br>{confidence}
        </div>
        """, unsafe_allow_html=True)

        st.write("")
        if rid in st.session_state.retained:
            st.success("✓ Experience already retained for this incident.")
        elif st.button("✅ Resolve Incident + Retain Experience", width="stretch"):
            if retain_incident(client, row):
                st.session_state.retained.add(rid)
                st.rerun()
            else:
                st.error("The experience could not be retained. Check the Hindsight connection details below.")
    else:
        st.info("Click **Investigate with Memory** to start the agent.")

st.divider()
st.markdown("### 🧠 Learning Loop")
p1, p2, p3 = st.columns(3)
p1.markdown("**1 · EXPERIENCE**\n\nIncident + failed action + successful action + lesson are retained.")
p2.markdown("**2 · RECALL**\n\nA later incident asks Hindsight for similar experience before choosing remediation.")
p3.markdown("**3 · IMPROVEMENT**\n\nThe agent avoids a previously ineffective action and reuses the successful path.")

st.markdown("### 📚 Experience Ledger")
ledger = df[["incident_id", "service", "root_cause", "failed_action", "successful_action", "lesson"]].copy()
ledger["memory_status"] = ledger["incident_id"].apply(lambda x: "✓ RETAINED" if str(x) in st.session_state.retained else "— pending")
st.dataframe(ledger, width="stretch", hide_index=True)

if st.session_state.retained:
    st.markdown('<div class="lesson"><b>Demo proof:</b> experience has been retained. Switch to INC-002 and investigate again to demonstrate memory-driven response.</div>', unsafe_allow_html=True)

if "memory_error" in st.session_state:
    with st.expander("Hindsight connection details"):
        st.code(st.session_state["memory_error"])
