# Incident Memory Agent — HackWithHyderabad 3.0 Demo

A polished, interactive Incident Response Agent demo built around Hindsight persistent memory.

## What this demo proves

The demo is intentionally designed around one visible learning loop:

**Incident → Hindsight Recall → Investigation → Remediation → Hindsight Retain → Future Incident**

Run **INC-001** first, investigate it, and retain the experience. Then switch to **INC-002** and investigate again. The second investigation can use the retained experience and explicitly avoid the previously ineffective Redis restart.

## Windows setup

1. Extract the ZIP.
2. Open Command Prompt in the `incident_memory_agent` folder (`app.py` and the `data/` folder must sit together).
3. Create a virtual environment:

```bat
python -m venv .venv
.venv\Scripts\activate
```

4. Install dependencies:

```bat
pip install -r requirements.txt
```

5. Launch:

```bat
streamlit run app.py
```

6. Open the local Streamlit URL shown in the terminal, normally `http://localhost:8501`.

## Demo sequence

### Step 1 — Cold start
Select `INC-001 · payment-api` and click **Investigate with Memory**.

The dashboard shows the current telemetry, a cold-start memory state, investigation trace, root cause, and recommended remediation.

### Step 2 — Retain experience
Click **Resolve Incident + Retain Experience**.

The Experience Ledger changes to `✓ RETAINED`, the memory state becomes `WARM`, and the retained experience remains available when you change incidents.

### Step 3 — Demonstrate learning
Select `INC-002 · payment-api` and click **Investigate with Memory**.

The dashboard recalls the previous payment-api experience and the recommendation explicitly says not to repeat the previously ineffective Redis restart.

## Hindsight configuration

The application can run in **Local Rehearsal Mode** without an API key so the UI and interaction flow can be demonstrated safely. For the final hackathon demo, copy `.env.example` to `.env` and fill in your values (loaded automatically):

```text
HINDSIGHT_API_KEY=your_hindsight_api_key
HINDSIGHT_API_URL=https://api.hindsight.vectorize.io
HINDSIGHT_BANK_ID=incident-response-demo
```

Do not commit real API keys to GitHub.

## Architecture

- **CSV:** controlled incident and telemetry scenarios for a reproducible hackathon demo.
- **Incident Response Agent:** correlates current incident evidence with previous experience.
- **Hindsight:** persistent memory for incident experience, including failed and successful remediation.
- **Streamlit:** interactive engineering dashboard.

## Recording tip

For a strong 2-minute demonstration:

1. Show INC-001 as a cold-start incident.
2. Investigate.
3. Show the root cause and remediation.
4. Retain the experience.
5. Switch to INC-002.
6. Investigate again.
7. Pause on the Hindsight Recall panel and the recommendation that avoids the known failed action.
8. End on the Learning Loop: **Experience → Recall → Improvement**.
