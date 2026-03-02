"""
TradePulse Backend API
FastAPI server with SSE streaming for real-time agent progress.
"""

import asyncio
import json
import os
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import AsyncGenerator

import httpx
from fastapi import FastAPI, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sse_starlette.sse import EventSourceResponse

from state import AgentState, DemoState, RunHistory
from agent import (
    run_agent,
    PAGERDUTY_ROUTING_KEY,
    HTTP_TIMEOUT,
)

# --- Configuration ---

TRADING_SERVICE_URL = os.environ.get("TRADING_SERVICE_URL", "http://trading-service:8001")

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
    broadcast_task = asyncio.create_task(broadcast_events())
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


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "agent_state": demo_state.state.value,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
