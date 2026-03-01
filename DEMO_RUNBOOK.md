# TradePulse Demo Runbook

Step-by-step guide for running the TradePulse demo in a live setting.

## Pre-Demo Checklist

- [ ] All services are running (frontend, backend, trading-service, Prometheus)
- [ ] Environment variables are configured (check Admin Panel > Config)
- [ ] Demo has been reset (Admin Panel > Reset Demo)
- [ ] PagerDuty dashboard is open in a browser tab
- [ ] Jira board is open in a browser tab
- [ ] Two browser windows ready: Dashboard + Admin Panel

## Demo Flow (5-7 minutes)

### Act 1: Normal Operations (30 seconds)

1. **Open the Live Dashboard** (`/`)
2. Point out the metrics chart showing p99 latency at ~200ms (green)
3. Show the "Monitored Symbols" card: AAPL, MSFT, GOOGL, JPM, GS
4. Note: "This trading platform is executing real orders against live market data"

### Act 2: Introduce Chaos (15 seconds)

5. **Open Admin Panel** (`/admin`) in a second tab/window
6. Click **"Enable Chaos Mode"**
7. Say: "We've just simulated a degradation in the upstream pricing service"

### Act 3: AI Agent Detects and Responds (2-3 minutes)

8. **Return to the Dashboard**
9. Click **"Start Demo"** (or the agent auto-detects if configured)
10. Watch the timeline populate in real time:

    - **Monitoring** — Agent checks Prometheus metrics
    - **Anomaly Detected** — p99 has breached 2000ms threshold
    - **PagerDuty** — Real incident created (show PD dashboard tab!)
    - **GitHub Investigation** — Agent retrieves pricing_client.py from repo
    - **Code Analysis** — 3 missing patterns identified:
      - Retry with Exponential Backoff
      - Circuit Breaker
      - Timeout Handling
    - **Fix Generated** — Optimized code ready
    - **Jira Ticket** — Real ticket created (show Jira tab!)

11. Point out: "Every step you see hit a real API — PagerDuty, GitHub, Jira"

### Act 4: Human-in-the-Loop (1 minute)

12. The timeline shows **"Human Approval — Waiting for approval"** with a glowing card
13. Click **"View Code Diff"** to show the before/after comparison
14. Walk through the changes:
    - "The agent identified three missing resiliency patterns"
    - "It generated a CircuitBreaker class, retry with backoff, and timeout handling"
15. Click **"Approve"**

### Act 5: Resolution (15 seconds)

16. Watch the final step: **"Resolved"** — incident closed on PagerDuty
17. Switch to PagerDuty tab — show the incident is resolved
18. Summarize: "From detection to resolution — the AI agent orchestrated the entire workflow"

### Act 6: Agent Console (optional, 30 seconds)

19. Switch to the **Console** tab (`/console`)
20. Show the full log of agent reasoning, tool calls, and results
21. Click on individual entries to expand the JSON payloads

## Reset for Next Demo

1. Go to **Admin Panel** (`/admin`)
2. Click **"Reset Demo"** (click twice to confirm)
3. This will:
   - Resolve any open PagerDuty incidents
   - Disable chaos mode on the trading service
   - Clear agent state
4. Ready for the next run in <30 seconds

## Troubleshooting

| Issue | Fix |
|-------|-----|
| SSE disconnected (red dot) | Refresh the page — auto-reconnects |
| Agent stuck | Reset via Admin Panel, try again |
| PagerDuty error | Check PAGERDUTY_ROUTING_KEY in Admin Config |
| Jira error | Check JIRA_EMAIL and JIRA_API_TOKEN in Admin Config |
| GitHub error | Check MYGITHUB_TOKEN in Admin Config |
| No metrics data | Ensure trading-service and Prometheus are running |

## Key Talking Points

- **Nothing is mocked**: Every API call hits a real external system
- **Human-in-the-loop**: The agent pauses for human approval before resolution
- **Fault-tolerant**: Every step has a 10-second timeout and graceful error handling
- **Real market data**: Live stock prices from Yahoo Finance
- **Production patterns**: State machine, SSE streaming, structured tool calling
