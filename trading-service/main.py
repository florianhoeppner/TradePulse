"""
TradePulse Trading Service
Simulated order execution platform with real market data and Prometheus metrics.
"""

import asyncio
import collections
import random
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone

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

# --- Latency Tracker (direct p99 without Prometheus) ---

MAX_LATENCY_SAMPLES = 200
latency_samples: collections.deque[float] = collections.deque(maxlen=MAX_LATENCY_SAMPLES)
order_count = 0
error_count = 0

# --- Globals ---

pricing_client = PricingClient()
background_task = None


async def simulate_orders():
    """Background task: execute simulated orders every 2 seconds to generate metrics."""
    global order_count, error_count
    while True:
        symbol = random.choice(SUPPORTED_SYMBOLS)
        try:
            start = time.monotonic()
            loop = asyncio.get_event_loop()
            price = await loop.run_in_executor(None, pricing_client.get_price, symbol)
            elapsed = time.monotonic() - start

            ORDER_LATENCY.observe(elapsed)
            ORDERS_TOTAL.labels(symbol=symbol, status="success").inc()
            latency_samples.append(elapsed * 1000)  # store in ms
            order_count += 1
        except Exception as e:
            elapsed = time.monotonic() - start
            ORDER_LATENCY.observe(elapsed)
            ORDERS_TOTAL.labels(symbol=symbol, status="error").inc()
            PRICING_ERRORS.labels(symbol=symbol, error_type=type(e).__name__).inc()
            latency_samples.append(elapsed * 1000)
            order_count += 1
            error_count += 1

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
    global order_count, error_count
    order_id = str(uuid.uuid4())[:8]

    try:
        start = time.monotonic()
        loop = asyncio.get_event_loop()
        price = await loop.run_in_executor(None, pricing_client.get_price, symbol)
        elapsed = time.monotonic() - start

        ORDER_LATENCY.observe(elapsed)
        ORDERS_TOTAL.labels(symbol=symbol, status="success").inc()
        latency_samples.append(elapsed * 1000)
        order_count += 1

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
        latency_samples.append(elapsed * 1000)
        order_count += 1
        error_count += 1

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


@app.get("/metrics/summary")
async def metrics_summary():
    """Return computed p99 latency and order counts directly — no Prometheus needed."""
    samples = list(latency_samples)
    if samples:
        samples_sorted = sorted(samples)
        idx_p99 = int(len(samples_sorted) * 0.99)
        idx_p50 = int(len(samples_sorted) * 0.50)
        p99 = round(samples_sorted[min(idx_p99, len(samples_sorted) - 1)], 1)
        p50 = round(samples_sorted[min(idx_p50, len(samples_sorted) - 1)], 1)
    else:
        p99 = 0.0
        p50 = 0.0

    return {
        "p99_latency_ms": p99,
        "p50_latency_ms": p50,
        "total_orders": order_count,
        "total_errors": error_count,
        "sample_count": len(samples),
        "chaos_mode": pricing_client.chaos_mode,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
