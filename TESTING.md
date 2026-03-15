# TradePulse Testing Guide

Step-by-step guide for testing TradePulse — both manual and automated.

## Prerequisites

### 1. Start All Services

```bash
# Terminal 1 — Trading Service (port 8001)
cd trading-service && pip install -r requirements.txt
uvicorn main:app --reload --port 8001

# Terminal 2 — Backend (port 8000)
cd backend && pip install -r requirements.txt
uvicorn main:app --reload --port 8000

# Terminal 3 — Frontend (port 3000)
cd frontend && npm install
npm run dev
```

### 2. Required Environment Variables

**Backend** (set before starting):
- `ANTHROPIC_API_KEY` — Claude API key
- `PAGERDUTY_ROUTING_KEY` — PagerDuty Events v2 routing key
- `JIRA_DOMAIN`, `JIRA_EMAIL`, `JIRA_API_TOKEN`, `JIRA_PROJECT_KEY` — Jira Cloud
- `MYGITHUB_TOKEN`, `MYGITHUB_REPO` — GitHub PAT and repo (e.g., `owner/repo`)
- `PROMETHEUS_URL` — Prometheus query endpoint (optional, agent falls back to trading service)
- `TRADING_SERVICE_URL` — Defaults to `http://trading-service:8001`; set to `http://localhost:8001` for local dev

**Frontend**: `NEXT_PUBLIC_BACKEND_URL` — Defaults to `http://localhost:8000`

### 3. Verify Services Are Healthy

```bash
curl http://localhost:8001/health   # Trading service → {"status":"ok","chaos_mode":false}
curl http://localhost:8000/health   # Backend → {"status":"ok","agent_state":"idle",...}
```

---

## Running Automated Tests

```bash
# Backend tests (from repo root)
cd backend && python -m pytest tests/ -v

# Trading service tests (from repo root)
cd trading-service && python -m pytest -v
```

---

## Manual Testing: Full Demo Workflow (Happy Path)

### Step 1 — Verify Idle State
```bash
curl http://localhost:8000/agent/status
```
Expected: `{"state": "idle", "history": [], "run_data": {}}`

### Step 2 — Check Market Data Is Flowing
```bash
curl http://localhost:8000/market/prices
curl http://localhost:8000/market/activity
curl http://localhost:8000/market/status
```
Expected: JSON responses with live stock quotes, recent trades, and NYSE open/closed status.

### Step 3 — Enable Chaos Mode
```bash
curl -X POST http://localhost:8000/admin/chaos/enable
```
Expected: `{"chaos_mode": true, "message": "Chaos mode enabled — latency will spike"}`

Wait 30–60 seconds for latency to build up in the trading service metrics.

### Step 4 — Start the Agent
```bash
curl -X POST http://localhost:8000/agent/start
```
Expected: `{"status": "started", "message": "Agent run initiated"}`

### Step 5 — Connect to SSE Stream
```bash
curl -N http://localhost:8000/events
```
You should see a stream of events in this order:
1. `state_change` → `monitoring`
2. `tool_call` → `detect_latency_anomaly`
3. `state_change` → `anomaly_detected`
4. `tool_call` → `create_pagerduty_incident`
5. `state_change` → `incident_created`
6. `tool_call` → `investigate_github_source`
7. `state_change` → `investigating`
8. `tool_call` → `identify_missing_patterns`
9. `state_change` → `analyzing`
10. `tool_call` → `generate_optimized_code`
11. `state_change` → `fix_generated`
12. `tool_call` → `create_jira_ticket`
13. `state_change` → `ticket_created` → `awaiting_approval`

### Step 6 — Verify Awaiting Approval
```bash
curl http://localhost:8000/agent/status
```
Expected: `state` is `awaiting_approval`, `run_data` contains PagerDuty dedup key, Jira ticket URL, and generated code.

### Step 7 — Approve the Fix
```bash
curl -X POST http://localhost:8000/agent/approve
```
Expected: `{"status": "approved", "message": "Fix approved — agent will resolve incident"}`

### Step 8 — Wait for Resolution
The SSE stream should show:
- `tool_call` → `resolve_pagerduty_incident`
- `state_change` → `resolved`

### Step 9 — Check Run History
```bash
curl http://localhost:8000/admin/history
```
Expected: `{"runs": [{"outcome": "completed", "steps": ..., "duration_ms": ..., ...}]}`

---

## Manual Testing: Rejection Path

Follow Steps 1–6 above, then:

```bash
curl -X POST http://localhost:8000/agent/reject
```
Expected: `{"status": "rejected", "message": "Fix rejected — incident remains open"}`

The agent state should transition to `rejected` and the SSE stream completes.

---

## Manual Testing: Admin Reset

Start a demo (Steps 1–5), then mid-run:

```bash
curl -X POST http://localhost:8000/admin/reset
```

Expected:
- Response: `{"status": "reset", "errors": null, "message": "Demo reset complete"}`
- Agent state returns to `idle`
- Chaos mode disabled on trading service
- Any open PagerDuty incident resolved

Verify:
```bash
curl http://localhost:8000/agent/status       # state: idle
curl http://localhost:8001/chaos/status        # chaos_mode: false
```

---

## Manual Testing: Error Conditions

### Start Agent When Already Running
```bash
curl -X POST http://localhost:8000/agent/start   # First start
curl -X POST http://localhost:8000/agent/start   # Second start
```
Expected (second call): `{"error": "Agent is already running", "state": "monitoring"}`

### Approve/Reject When Not Awaiting
```bash
curl -X POST http://localhost:8000/agent/approve
```
Expected: `{"error": "Agent is not awaiting approval", "state": "idle"}`

### Invalid Chaos Mode
```bash
curl -X POST http://localhost:8000/admin/chaos/invalid
```
Expected: HTTP 422 with `{"error": "Mode must be 'enable' or 'disable'"}`

### Market Endpoints When Trading Service Is Down
Stop the trading service, then:
```bash
curl http://localhost:8000/market/prices
```
Expected: HTTP 502 with `{"error": "Failed to fetch market prices: ..."}`

---

## Manual Testing: AI Market Commentary

```bash
curl -X POST http://localhost:8000/market/commentary
```

Expected (with API key configured): JSON with `commentary` (2–3 sentence market analysis), `isIncident` (boolean), and `timestamp`.

Expected (without API key): `{"commentary": "AI commentary unavailable — API key not configured.", ...}`

---

## Manual Testing: Frontend

1. **Connection Indicator**: Open `http://localhost:3000` — the navbar should show a green dot when connected to SSE, red when disconnected.
2. **Market Data**: The dashboard should display live stock prices with sparkline charts, updating in real-time.
3. **Start Agent**: Click the "Start" button — the timeline should populate step-by-step.
4. **Approval Flow**: When the agent reaches "Awaiting Approval", the Approve/Reject buttons should appear. Click one and verify the timeline completes.
5. **Admin Panel**: Use the admin panel to reset the demo and toggle chaos mode. Verify the UI reflects the state changes.
6. **Market Commentary**: Commentary panel should show AI-generated market analysis, refreshing periodically.
