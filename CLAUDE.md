# TradePulse — AI Incident Response Demo

Production-grade AI Agent demo for enterprise financial services audiences. An AI agent detects trading platform latency spikes, creates real PagerDuty incidents, investigates GitHub source code, generates fixes, creates Jira tickets, and awaits human approval. Nothing in the agent loop is mocked.

## Architecture

```
frontend/ (Next.js 14, Vercel)  ←SSE→  backend/ (FastAPI, Railway)  →  trading-service/ (FastAPI, Railway)
                                                                     →  Prometheus (metrics)
                                                                     →  PagerDuty, GitHub, Jira (real APIs)
                                                                     →  Anthropic Claude (AI reasoning)
```

## Tech Stack

- **Frontend**: Next.js 14 (App Router), Tailwind CSS, Framer Motion, TypeScript
- **Backend**: FastAPI, Anthropic SDK (claude-sonnet-4-6), SSE via sse-starlette
- **Trading Service**: FastAPI, yfinance, prometheus-client
- **Deployment**: Vercel (frontend), Railway (backend + trading-service + Prometheus)

## Key Files

- `frontend/lib/useAgentStream.ts` — SSE streaming hook, connection status logic
- `frontend/lib/api.ts` — Backend API calls, BACKEND_URL config
- `frontend/components/Navbar.tsx` — Connection status indicator (green/red dot)
- `backend/main.py` — SSE endpoint (`/events`), agent control, admin endpoints, health check (`/health`)
- `backend/agent.py` — Agentic loop with 7 real tool implementations
- `backend/state.py` — Demo state machine
- `trading-service/main.py` — Order execution, Prometheus metrics, chaos mode
- `trading-service/pricing_client.py` — Intentionally fragile pricing client (what the agent finds and fixes)

## Commands

### Frontend
```bash
cd frontend && npm install        # Install dependencies
cd frontend && npm run dev        # Dev server (port 3000)
cd frontend && npm run build      # Type-check + production build
cd frontend && npm run lint       # ESLint
```

### Backend
```bash
cd backend && pip install -r requirements.txt
cd backend && uvicorn main:app --reload --port 8000
cd backend && python -m pytest tests/ -v
```

### Trading Service
```bash
cd trading-service && pip install -r requirements.txt
cd trading-service && uvicorn main:app --reload --port 8001
cd trading-service && python -m pytest test_trading_service.py -v
```

## Environment Variables

### Railway (backend)
`ANTHROPIC_API_KEY`, `PAGERDUTY_ROUTING_KEY`, `JIRA_DOMAIN`, `JIRA_EMAIL`, `JIRA_API_TOKEN`, `JIRA_PROJECT_KEY`, `MYGITHUB_TOKEN`, `MYGITHUB_REPO`, `PROMETHEUS_URL`, `TRADING_SERVICE_URL`

### Vercel (frontend)
`NEXT_PUBLIC_BACKEND_URL` — defaults to `http://localhost:8000`

## Design Philosophy

- Dark theme, Anthropic-inspired palette (deep navy, white typography, blue/green accents)
- Fault-safe for live demos: every step succeeds or shows a clear, graceful error
- All external API calls have 10s timeouts and graceful error handling
- Demo fully resettable in under 30 seconds via Admin Panel
