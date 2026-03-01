# TradePulse — AI Incident Response Demo

A production-grade AI Agent demo for enterprise financial services audiences.
An AI agent detects a latency anomaly in a trading platform, investigates the
root cause, generates a fix, and orchestrates incident response — all using
real external systems. Nothing is mocked.

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                         VERCEL                                   │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │  Next.js Frontend                                           │ │
│  │  ┌─────────────┐ ┌──────────────┐ ┌──────────────────────┐ │ │
│  │  │  Dashboard   │ │   Console    │ │    Admin Panel       │ │ │
│  │  │  (Timeline)  │ │  (Logs)      │ │  (Controls/Config)   │ │ │
│  │  └──────┬───────┘ └──────┬───────┘ └──────────┬───────────┘ │ │
│  │         └────────────────┼────────────────────┘             │ │
│  │                          │ SSE                              │ │
│  └──────────────────────────┼──────────────────────────────────┘ │
└─────────────────────────────┼────────────────────────────────────┘
                              │
┌─────────────────────────────┼────────────────────────────────────┐
│                        RAILWAY                                    │
│  ┌──────────────────────────┼──────────────────────────────────┐ │
│  │  Backend (FastAPI)       ▼                                  │ │
│  │  ┌──────────────────────────────┐                           │ │
│  │  │  AI Agent (Claude Sonnet)    │                           │ │
│  │  │  7 Real Tool Calls:          │                           │ │
│  │  │  1. Prometheus Query         │──── Prometheus ◄── Scrape │ │
│  │  │  2. PagerDuty Create ────────┼──── PagerDuty API        │ │
│  │  │  3. GitHub Investigate ──────┼──── GitHub API            │ │
│  │  │  4. Analyze Patterns         │                           │ │
│  │  │  5. Generate Fix             │                           │ │
│  │  │  6. Jira Ticket ────────────┼──── Jira API              │ │
│  │  │  7. PagerDuty Resolve ──────┼──── PagerDuty API        │ │
│  │  └──────────────────────────────┘                           │ │
│  └─────────────────────────────────────────────────────────────┘ │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │  Trading Service (FastAPI)                                  │ │
│  │  - Live stock prices via yfinance (AAPL, MSFT, GOOGL, etc)│ │
│  │  - Prometheus metrics (latency, orders, errors)             │ │
│  │  - Chaos mode toggle for demo                               │ │
│  │  - Intentionally fragile pricing_client.py                  │ │
│  └─────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────┘
```

## The Demo Story

1. A trading platform processes orders using live market data
2. An operator enables "chaos mode" — the pricing client becomes slow
3. The AI agent detects p99 latency breaching 2000ms via Prometheus
4. The agent creates a real PagerDuty incident
5. It investigates the source code on GitHub and finds missing resiliency patterns
6. It generates an optimized version with retry, circuit breaker, and timeout
7. It creates a Jira ticket with the full analysis and proposed fix
8. A human reviews and approves the fix
9. The agent resolves the PagerDuty incident and logs a change event

**Everything is real. Nothing is mocked.**

## Local Development

### Prerequisites

- Python 3.11+
- Node.js 18+
- npm

### Trading Service

```bash
cd trading-service
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8001
```

### Backend

```bash
cd backend
pip install -r requirements.txt

# Set environment variables
export ANTHROPIC_API_KEY=your_key
export PAGERDUTY_ROUTING_KEY=your_key
export JIRA_EMAIL=your_email
export JIRA_API_TOKEN=your_token
export MYGITHUB_TOKEN=your_token
export PROMETHEUS_URL=http://localhost:9090
export TRADING_SERVICE_URL=http://localhost:8001

uvicorn main:app --host 0.0.0.0 --port 8000
```

### Frontend

```bash
cd frontend
npm install
NEXT_PUBLIC_BACKEND_URL=http://localhost:8000 npm run dev
```

### Running Tests

```bash
# Trading service tests
cd trading-service && pytest -v

# Backend tests
cd backend && pytest -v

# Frontend build check
cd frontend && npm run build
```

## Environment Variables

### Railway (backend + trading-service)

| Variable | Description |
|----------|-------------|
| `ANTHROPIC_API_KEY` | Anthropic API key for Claude |
| `PAGERDUTY_ROUTING_KEY` | PagerDuty Events API v2 routing key |
| `JIRA_DOMAIN` | Jira Cloud domain (e.g., `yoursite.atlassian.net`) |
| `JIRA_EMAIL` | Jira account email |
| `JIRA_API_TOKEN` | Jira API token |
| `JIRA_PROJECT_KEY` | Jira project key (default: `SCRUM`) |
| `MYGITHUB_TOKEN` | GitHub personal access token |
| `MYGITHUB_REPO` | GitHub repo (default: `florianhoeppner/TradePulse`) |
| `PROMETHEUS_URL` | Prometheus URL (default: `http://prometheus:9090`) |
| `TRADING_SERVICE_URL` | Trading service URL (default: `http://trading-service:8001`) |

### Vercel (frontend)

| Variable | Description |
|----------|-------------|
| `NEXT_PUBLIC_BACKEND_URL` | Backend API URL on Railway |

## Deployment

### Railway

1. Import repo from GitHub
2. Create three services: `backend`, `trading-service`, `prometheus`
3. Set root directory for each service
4. Add all environment variables
5. Deploy

### Vercel

1. Import repo from GitHub
2. Set root directory to `frontend`
3. Set `NEXT_PUBLIC_BACKEND_URL` to Railway backend URL
4. Deploy

## Project Structure

```
TradePulse/
├── frontend/               # Next.js → Vercel
│   ├── app/
│   │   ├── page.tsx        # Live Dashboard
│   │   ├── console/        # Agent Console
│   │   └── admin/          # Admin Panel
│   ├── components/         # React components
│   └── lib/                # Hooks, API, types
├── backend/                # FastAPI → Railway
│   ├── main.py             # SSE + API endpoints
│   ├── agent.py            # AI agent + 7 tools
│   ├── state.py            # Demo state machine
│   └── tests/              # Backend tests
├── trading-service/        # FastAPI → Railway
│   ├── main.py             # Order service + metrics
│   └── pricing_client.py   # Intentionally fragile
├── prometheus/
│   └── prometheus.yml      # Scrape config
└── railway.json            # Multi-service config
```

## Tech Stack

- **Frontend**: Next.js 14, Tailwind CSS, Framer Motion
- **Backend**: FastAPI, Anthropic SDK (Claude Sonnet), SSE
- **Trading Service**: FastAPI, yfinance, prometheus-client
- **AI Model**: Claude Sonnet 4.6 via Anthropic API
- **External Services**: PagerDuty, Jira, GitHub (all real APIs)
