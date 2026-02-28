"""
TradePulse Trading Service
Simulated order execution platform with real market data and Prometheus metrics.
"""

import asyncio
import random
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

from pricing_client import PricingClient, SUPPORTED_SYMBOLS


# --- Prometheus Metrics ---

ORDER_LATENCY = Histogram(
    "tradepulse_order_latency_seconds",
    "Order execution latency in seconds",
    buckets=(0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

ORDERS_TOTAL = Counter(
    "tradepulse_orders_total",
    "Total number of orders executed",
    ["symbol", "status"],
)

PRICING_ERRORS = Counter(
    "tradepulse_pricing_errors_total",
    "Total pricing errors",
    ["symbol", "error_type"],
)

# --- Globals ---

pricing_client = PricingClient()
background_task = None


async def simulate_orders():
    """Background task: execute simulated orders every 2 seconds to generate metrics."""
    while True:
        symbol = random.choice(SUPPORTED_SYMBOLS)
        try:
            start = time.monotonic()
            # Run the synchronous pricing call in a thread to not block the event loop
            loop = asyncio.get_event_loop()
            price = await loop.run_in_executor(None, pricing_client.get_price, symbol)
            elapsed = time.monotonic() - start

            ORDER_LATENCY.observe(elapsed)
            ORDERS_TOTAL.labels(symbol=symbol, status="success").inc()
        except Exception as e:
            elapsed = time.monotonic() - start
            ORDER_LATENCY.observe(elapsed)
            ORDERS_TOTAL.labels(symbol=symbol, status="error").inc()
            PRICING_ERRORS.labels(symbol=symbol, error_type=type(e).__name__).inc()

        await asyncio.sleep(2)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start background order simulation on startup."""
    global background_task
    background_task = asyncio.create_task(simulate_orders())
    yield
    background_task.cancel()
    try:
        await background_task
    except asyncio.CancelledError:
        pass


# --- FastAPI App ---

app = FastAPI(
    title="TradePulse Trading Service",
    description="Simulated order execution platform with live market data",
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


@app.get("/health")
async def health():
    return {"status": "ok", "chaos_mode": pricing_client.chaos_mode}


@app.get("/metrics")
async def metrics():
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST,
    )


@app.post("/orders")
async def create_order(symbol: str = "AAPL", quantity: int = 100):
    """Execute a simulated order using live market prices."""
    order_id = str(uuid.uuid4())[:8]

    try:
        start = time.monotonic()
        loop = asyncio.get_event_loop()
        price = await loop.run_in_executor(None, pricing_client.get_price, symbol)
        elapsed = time.monotonic() - start

        ORDER_LATENCY.observe(elapsed)
        ORDERS_TOTAL.labels(symbol=symbol, status="success").inc()

        return {
            "order_id": order_id,
            "symbol": symbol,
            "quantity": quantity,
            "price": price,
            "total": round(price * quantity, 2),
            "latency_ms": round(elapsed * 1000, 1),
            "status": "filled",
        }
    except Exception as e:
        elapsed = time.monotonic() - start if "start" in dir() else 0
        ORDER_LATENCY.observe(elapsed)
        ORDERS_TOTAL.labels(symbol=symbol, status="error").inc()
        PRICING_ERRORS.labels(symbol=symbol, error_type=type(e).__name__).inc()

        return {
            "order_id": order_id,
            "symbol": symbol,
            "quantity": quantity,
            "price": None,
            "total": None,
            "latency_ms": round(elapsed * 1000, 1),
            "status": "error",
            "error": str(e),
        }


@app.post("/chaos/enable")
async def chaos_enable():
    pricing_client.chaos_mode = True
    return {"chaos_mode": True, "message": "Chaos mode enabled — latency will spike"}


@app.post("/chaos/disable")
async def chaos_disable():
    pricing_client.chaos_mode = False
    return {"chaos_mode": False, "message": "Chaos mode disabled — normal operation"}


@app.get("/chaos/status")
async def chaos_status():
    return {"chaos_mode": pricing_client.chaos_mode}
