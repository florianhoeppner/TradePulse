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

- `frontend/lib/AgentStreamContext.tsx` — Shared React Context for SSE state (persists across page navigation)
- `frontend/lib/useAgentStream.ts` — SSE streaming hook, connection status logic
- `frontend/lib/api.ts` — Backend API calls, BACKEND_URL config
- `frontend/components/Providers.tsx` — Root provider wrapper (AgentStreamContext)
- `frontend/components/Navbar.tsx` — Connection status indicator (green/red dot)
- `backend/main.py` — SSE endpoint (`/events`), agent control, admin endpoints, health check (`/health`)
- `backend/agent.py` — Agentic loop with 7 real tool implementations
- `backend/state.py` — Demo state machine
- `backend/tests/` — Backend test suite (test_api, test_endpoints, test_tools, test_state)
- `trading-service/main.py` — Order execution, Prometheus metrics, chaos mode
- `trading-service/pricing_client.py` — Intentionally fragile pricing client (what the agent finds and fixes)
- `trading-service/test_trading_service.py`, `test_market_endpoints.py` — Trading service tests

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

## Testing Requirements

Every code change **must** include automated tests. No exceptions.

- **Backend**: Add or update tests in `backend/tests/`. Run with `cd backend && python -m pytest tests/ -v`
- **Trading Service**: Add or update tests in `trading-service/`. Run with `cd trading-service && python -m pytest -v`
- **Frontend**: Run `cd frontend && npm run build` to verify type safety and compilation
- **Test patterns**: Use `pytest-asyncio` + `AsyncClient` for endpoint tests, `respx` for HTTP mocking (backend), `unittest.mock.patch` for mocking (trading service)
- **What to test**: Every new endpoint, every tool function, every state transition, and both success and failure paths
- **See**: `TESTING.md` for the full manual testing guide and test inventory

## Error Handling Guidelines

All code must handle errors gracefully with clear, user-visible messages. The agent loop must never crash silently.

### Backend
- **External API calls** (PagerDuty, GitHub, Jira, Prometheus): Wrap in try/except, return `{"error": "<description>"}` in tool results so the agent can continue
- **Tool dispatch**: Use `args.get("key", default)` instead of `args["key"]` to prevent KeyError when Claude omits parameters
- **State transitions**: Catch `ValueError` from invalid transitions — never let a state machine error crash the agent loop
- **Proxy endpoints**: Return HTTP 502 with `{"error": "..."}` when downstream services are unreachable
- **Timeouts**: All `httpx.AsyncClient` calls must use `timeout=HTTP_TIMEOUT` (10s)

### Frontend
- **API calls**: All functions in `api.ts` return `{ ok, data?, error? }` — always check `ok` before using `data`
- **Error banners**: Show errors in a dismissible banner (auto-dismiss after 6s) — never fail silently
- **SSE reconnection**: Auto-reconnect after 2s on connection loss
- **State persistence**: Use `useAgentStreamContext()` from the shared context — never create per-page `useAgentStream()` instances
- **Loading states**: Show "Loading...", "Toggling...", "Starting..." during async operations to confirm the action was received
