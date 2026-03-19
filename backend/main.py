"""
TradePulse Backend API
FastAPI server with SSE streaming for real-time agent progress.
"""

import asyncio
import json
import logging
import os
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import AsyncGenerator

logger = logging.getLogger("tradepulse.backend")

import httpx
from fastapi import FastAPI, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sse_starlette.sse import EventSourceResponse

from state import AgentState, DemoState, RunHistory

# --- Configuration ---

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
PAGERDUTY_ROUTING_KEY = os.environ.get("PAGERDUTY_ROUTING_KEY", "")
TRADING_SERVICE_URL = os.environ.get("TRADING_SERVICE_URL", "http://trading-service:8001")
HTTP_TIMEOUT = 10.0

ENV_VAR_NAMES = [
    "ANTHROPIC_API_KEY",
    "PAGERDUTY_ROUTING_KEY",
    "JIRA_DOMAIN",
    "JIRA_EMAIL",
    "JIRA_API_TOKEN",
    "JIRA_PROJECT_KEY",
    "MYGITHUB_TOKEN",
    "MYGITHUB_REPO",
    "PROMETHEUS_URL",
    "TRADING_SERVICE_URL",
]

# --- Global State ---

demo_state = DemoState()
run_history = RunHistory()
event_queue: asyncio.Queue = asyncio.Queue()
approval_event = asyncio.Event()
agent_task: asyncio.Task | None = None
# Track SSE subscribers for fan-out
sse_subscribers: list[asyncio.Queue] = []
broadcast_task = None


# --- SSE Fan-out ---

async def broadcast_events():
    """Background task: reads from the main event queue and fans out to all SSE subscribers."""
    while True:
        event = await event_queue.get()
        dead_subscribers = []
        for sub_queue in sse_subscribers:
            try:
                sub_queue.put_nowait(event)
            except asyncio.QueueFull:
                dead_subscribers.append(sub_queue)
        for dead in dead_subscribers:
            sse_subscribers.remove(dead)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global broadcast_task
    port = os.environ.get("PORT", "8000")
    logger.info("TradePulse backend starting on port %s", port)

    # Diagnostic: check if anthropic SDK is available
    try:
        import anthropic
        logger.info("anthropic SDK version: %s", anthropic.__version__)
    except Exception as e:
        logger.warning("anthropic SDK not available: %s", e)

    # Diagnostic: check env var configuration
    configured = [v for v in ENV_VAR_NAMES if os.environ.get(v)]
    missing = [v for v in ENV_VAR_NAMES if not os.environ.get(v)]
    logger.info("Configured env vars: %s", configured)
    if missing:
        logger.warning("Missing env vars: %s", missing)

    broadcast_task = asyncio.create_task(broadcast_events())
    logger.info("TradePulse backend ready — health check at /health")
    yield
    broadcast_task.cancel()
    try:
        await broadcast_task
    except asyncio.CancelledError:
        pass


# --- FastAPI App ---

app = FastAPI(
    title="TradePulse Backend",
    description="AI Agent orchestration with real-time SSE streaming",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- SSE Endpoint ---

async def event_generator(subscriber_queue: asyncio.Queue) -> AsyncGenerator[dict, None]:
    """Generate SSE events for a single subscriber."""
    try:
        # Send initial state
        yield {
            "event": "state_change",
            "data": json.dumps({
                "state": demo_state.state.value,
                "message": "Connected to TradePulse agent stream",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }),
        }

        while True:
            try:
                event = await asyncio.wait_for(subscriber_queue.get(), timeout=30.0)
                yield {
                    "event": event.get("type", "message"),
                    "data": json.dumps(event.get("data", {})),
                }
            except asyncio.TimeoutError:
                # Send keepalive
                yield {
                    "event": "keepalive",
                    "data": json.dumps({"timestamp": datetime.now(timezone.utc).isoformat()}),
                }
    except asyncio.CancelledError:
        pass


@app.get("/events")
async def events():
    """SSE endpoint for real-time agent progress streaming."""
    subscriber_queue: asyncio.Queue = asyncio.Queue(maxsize=100)
    sse_subscribers.append(subscriber_queue)

    async def on_disconnect():
        if subscriber_queue in sse_subscribers:
            sse_subscribers.remove(subscriber_queue)

    return EventSourceResponse(
        event_generator(subscriber_queue),
        headers={"X-Accel-Buffering": "no"},
    )


# --- Agent Control Endpoints ---

@app.post("/agent/start")
async def start_agent():
    """Start the AI agent run."""
    global agent_task

    try:
        from agent import run_agent
    except Exception as e:
        logger.error("Failed to import agent module: %s", e)
        return JSONResponse(
            status_code=503,
            content={"error": f"Agent module unavailable: {e}"},
        )

    if demo_state.state != AgentState.IDLE:
        return {"error": "Agent is already running", "state": demo_state.state.value}

    approval_event.clear()

    async def _run():
        result = await run_agent(event_queue, demo_state, approval_event)
        run_history.record_run(
            outcome=result.get("status", "unknown"),
            steps=result.get("iterations", 0),
            duration_ms=result.get("duration_ms", 0),
            details=result,
        )

    agent_task = asyncio.create_task(_run())
    return {"status": "started", "message": "Agent run initiated"}


@app.post("/agent/approve")
async def approve_action():
    """Human approves the proposed fix."""
    if demo_state.state != AgentState.AWAITING_APPROVAL:
        return {"error": "Agent is not awaiting approval", "state": demo_state.state.value}

    demo_state.transition(AgentState.APPROVED)
    approval_event.set()
    return {"status": "approved", "message": "Fix approved — agent will resolve incident"}


@app.post("/agent/reject")
async def reject_action():
    """Human rejects the proposed fix."""
    if demo_state.state != AgentState.AWAITING_APPROVAL:
        return {"error": "Agent is not awaiting approval", "state": demo_state.state.value}

    demo_state.transition(AgentState.REJECTED)
    approval_event.set()
    return {"status": "rejected", "message": "Fix rejected — incident remains open"}


@app.get("/agent/status")
async def agent_status():
    """Get current agent state and run data."""
    return demo_state.to_dict()


# --- Admin Endpoints ---

@app.post("/admin/reset")
async def admin_reset():
    """Full demo reset: resolve PD, disable chaos, reset state."""
    global agent_task
    errors = []

    # Cancel running agent if any
    if agent_task and not agent_task.done():
        agent_task.cancel()

    # Try to resolve any open PD incident
    dedup_key = demo_state.run_data.get("create_pagerduty_incident", {}).get("dedup_key", "")
    if dedup_key:
        try:
            async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
                await client.post(
                    "https://events.pagerduty.com/v2/enqueue",
                    json={
                        "routing_key": PAGERDUTY_ROUTING_KEY,
                        "dedup_key": dedup_key,
                        "event_action": "resolve",
                    },
                )
        except Exception as e:
            errors.append(f"PagerDuty resolve failed: {str(e)}")

    # Disable chaos mode on trading service
    try:
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
            await client.post(f"{TRADING_SERVICE_URL}/chaos/disable")
    except Exception as e:
        errors.append(f"Chaos disable failed: {str(e)}")

    # Deactivate short-term response controls
    try:
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
            await client.post(f"{TRADING_SERVICE_URL}/admin/cache/deactivate")
    except Exception as e:
        errors.append(f"Cache deactivate failed: {str(e)}")

    try:
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
            await client.post(f"{TRADING_SERVICE_URL}/admin/load-shedding/deactivate")
    except Exception as e:
        errors.append(f"Load shedding deactivate failed: {str(e)}")

    try:
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
            await client.post(f"{TRADING_SERVICE_URL}/admin/pricing-source/primary")
    except Exception as e:
        errors.append(f"Pricing source reset failed: {str(e)}")

    # Reset state
    demo_state.reset()
    approval_event.clear()

    await event_queue.put({
        "type": "state_change",
        "data": {"state": "idle", "message": "Demo reset complete"},
    })

    return {
        "status": "reset",
        "errors": errors if errors else None,
        "message": "Demo reset complete" + (f" (with {len(errors)} warnings)" if errors else ""),
    }


@app.post("/admin/chaos/{mode}")
async def admin_chaos(mode: str):
    """Toggle chaos mode on the trading service."""
    if mode not in ("enable", "disable"):
        return JSONResponse(
            status_code=422,
            content={"error": "Mode must be 'enable' or 'disable'"},
        )

    try:
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
            response = await client.post(f"{TRADING_SERVICE_URL}/chaos/{mode}")
            return response.json()
    except Exception as e:
        return JSONResponse(
            status_code=502,
            content={"error": f"Failed to toggle chaos mode: {str(e)}"},
        )


@app.get("/admin/chaos/status")
async def admin_chaos_status():
    """Get current chaos mode status from the trading service."""
    try:
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
            response = await client.get(f"{TRADING_SERVICE_URL}/chaos/status")
            return response.json()
    except Exception as e:
        return JSONResponse(
            status_code=502,
            content={"error": f"Failed to fetch chaos status: {str(e)}"},
        )


@app.get("/admin/platform-status")
async def admin_platform_status():
    """Proxy platform status from the trading service."""
    try:
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
            response = await client.get(f"{TRADING_SERVICE_URL}/admin/platform-status")
            return response.json()
    except Exception as e:
        return JSONResponse(
            status_code=502,
            content={"error": f"Failed to fetch platform status: {str(e)}"},
        )


@app.post("/admin/cache/{mode}")
async def admin_cache(mode: str):
    """Toggle price cache on the trading service."""
    if mode not in ("activate", "deactivate"):
        return JSONResponse(
            status_code=422,
            content={"error": "Mode must be 'activate' or 'deactivate'"},
        )
    try:
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
            response = await client.post(f"{TRADING_SERVICE_URL}/admin/cache/{mode}")
            return response.json()
    except Exception as e:
        return JSONResponse(
            status_code=502,
            content={"error": f"Failed to toggle cache: {str(e)}"},
        )


@app.post("/admin/load-shedding/{mode}")
async def admin_load_shedding(mode: str):
    """Toggle load shedding on the trading service."""
    if mode not in ("activate", "deactivate"):
        return JSONResponse(
            status_code=422,
            content={"error": "Mode must be 'activate' or 'deactivate'"},
        )
    try:
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
            response = await client.post(
                f"{TRADING_SERVICE_URL}/admin/load-shedding/{mode}"
            )
            return response.json()
    except Exception as e:
        return JSONResponse(
            status_code=502,
            content={"error": f"Failed to toggle load shedding: {str(e)}"},
        )


@app.post("/admin/pricing-source/{mode}")
async def admin_pricing_source(mode: str):
    """Switch pricing source on the trading service."""
    if mode not in ("backup", "primary"):
        return JSONResponse(
            status_code=422,
            content={"error": "Mode must be 'backup' or 'primary'"},
        )
    try:
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
            response = await client.post(
                f"{TRADING_SERVICE_URL}/admin/pricing-source/{mode}"
            )
            return response.json()
    except Exception as e:
        return JSONResponse(
            status_code=502,
            content={"error": f"Failed to switch pricing source: {str(e)}"},
        )


@app.get("/economic-profile")
async def get_economic_profile():
    """Return the current economic profile used for risk calculations."""
    return demo_state.economic_profile


@app.post("/economic-profile")
async def set_economic_profile(request: Request):
    """Update the economic profile used for risk calculations."""
    body = await request.json()
    allowed_keys = {
        "avg_order_value_usd",
        "orders_per_minute",
        "sla_breach_penalty_usd",
        "downtime_cost_per_hour_usd",
        "currency",
    }
    for key, value in body.items():
        if key in allowed_keys:
            demo_state.economic_profile[key] = value
    return demo_state.economic_profile


@app.get("/admin/config")
async def admin_config():
    """Return environment variable names (not values) and their configuration status."""
    config = {}
    for var in ENV_VAR_NAMES:
        value = os.environ.get(var, "")
        config[var] = {
            "configured": bool(value),
            "length": len(value) if value else 0,
        }
    return {"config": config}


@app.get("/admin/history")
async def admin_history():
    """Return history of agent runs."""
    return {"runs": run_history.get_runs()}


# --- AI Market Commentary ---

_commentary_client = None


def _get_commentary_client():
    global _commentary_client
    if _commentary_client is None and ANTHROPIC_API_KEY:
        import anthropic
        _commentary_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    return _commentary_client


@app.post("/market/commentary")
async def market_commentary():
    """Generate brief AI market commentary based on current stock prices."""
    # Fetch current prices
    try:
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
            response = await client.get(f"{TRADING_SERVICE_URL}/market/prices")
            price_data = response.json()
    except Exception as e:
        return JSONResponse(
            status_code=502,
            content={"error": f"Failed to fetch prices for commentary: {str(e)}"},
        )

    quotes = price_data.get("quotes", [])
    if not quotes:
        return {"commentary": "Waiting for market data...", "timestamp": datetime.now(timezone.utc).isoformat()}

    # Check if in incident state
    is_incident = demo_state.state.value not in ("idle", "monitoring", "resolved")

    price_summary = ", ".join(
        f"{q['symbol']}: ${q['price']} ({'+' if q['change'] >= 0 else ''}{q['change']:.2f}, {'+' if q['changePercent'] >= 0 else ''}{q['changePercent']:.1f}%)"
        for q in quotes
    )

    incident_context = ""
    if is_incident:
        incident_context = "\nCRITICAL: The trading platform is currently experiencing a latency incident. Price feeds are delayed. Emphasize the URGENCY and RISK of trading with stale data. Be alarming but professional."

    prompt = f"""You are a trading floor AI analyst. Give a brief, punchy market commentary (2-3 sentences max) based on current prices.
Be specific about individual stocks. Sound like a Bloomberg terminal alert — concise, data-driven, actionable.{incident_context}

Current prices: {price_summary}"""

    try:
        api_client = _get_commentary_client()
        if not api_client:
            return {"commentary": "AI commentary unavailable — API key not configured.", "timestamp": datetime.now(timezone.utc).isoformat()}

        loop = asyncio.get_event_loop()
        message = await loop.run_in_executor(None, lambda: api_client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=150,
            messages=[{"role": "user", "content": prompt}],
        ))
        commentary = message.content[0].text
    except Exception as e:
        commentary = f"Commentary temporarily unavailable."
        logger.warning("AI commentary failed: %s", str(e))

    return {
        "commentary": commentary,
        "isIncident": is_incident,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# --- Market Data Proxy Endpoints ---

@app.get("/market/prices")
async def market_prices():
    """Proxy live stock prices from the trading service."""
    try:
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
            response = await client.get(f"{TRADING_SERVICE_URL}/market/prices")
            return response.json()
    except Exception as e:
        return JSONResponse(
            status_code=502,
            content={"error": f"Failed to fetch market prices: {str(e)}"},
        )


@app.get("/market/activity")
async def market_activity():
    """Proxy trade activity from the trading service."""
    try:
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
            response = await client.get(f"{TRADING_SERVICE_URL}/market/activity")
            return response.json()
    except Exception as e:
        return JSONResponse(
            status_code=502,
            content={"error": f"Failed to fetch trade activity: {str(e)}"},
        )


@app.get("/market/status")
async def market_status():
    """Proxy market status from the trading service."""
    try:
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
            response = await client.get(f"{TRADING_SERVICE_URL}/market/status")
            return response.json()
    except Exception as e:
        return JSONResponse(
            status_code=502,
            content={"error": f"Failed to fetch market status: {str(e)}"},
        )


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "agent_state": demo_state.state.value,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
