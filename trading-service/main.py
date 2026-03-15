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
from prometheus_client import Counter, Gauge, Histogram, generate_latest, CONTENT_TYPE_LATEST

from pricing_client import PricingClient, SUPPORTED_SYMBOLS
from price_cache import PriceCache
from load_shedder import LoadShedder


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

# Short-term response metrics
CACHE_ACTIVE = Gauge(
    "tradepulse_cache_active",
    "Whether the price cache is active (0 or 1)",
)

CACHE_AGE_SECONDS = Gauge(
    "tradepulse_cache_age_seconds",
    "Seconds since the price cache was activated",
)

SHED_REQUESTS_TOTAL = Counter(
    "tradepulse_shed_requests_total",
    "Total number of requests shed by load shedder",
)

QUEUE_DEPTH = Gauge(
    "tradepulse_queue_depth",
    "Current number of requests queued by load shedder",
)

PRICING_SOURCE = Gauge(
    "tradepulse_pricing_source",
    "Active pricing source (0=primary, 1=backup)",
)

# --- Latency Tracker (direct p99 without Prometheus) ---

MAX_LATENCY_SAMPLES = 200
latency_samples: collections.deque[float] = collections.deque(maxlen=MAX_LATENCY_SAMPLES)
order_count = 0
error_count = 0

# --- Trade Activity Log ---

MAX_ACTIVITY_LOG = 50


class TradeEntry:
    __slots__ = ("symbol", "side", "quantity", "price", "latency_ms", "timestamp", "status")

    def __init__(self, symbol, side, quantity, price, latency_ms, timestamp, status):
        self.symbol = symbol
        self.side = side
        self.quantity = quantity
        self.price = price
        self.latency_ms = latency_ms
        self.timestamp = timestamp
        self.status = status

    def to_dict(self):
        return {
            "symbol": self.symbol,
            "side": self.side,
            "quantity": self.quantity,
            "price": self.price,
            "latency_ms": self.latency_ms,
            "timestamp": self.timestamp,
            "status": self.status,
        }


trade_activity: collections.deque[TradeEntry] = collections.deque(maxlen=MAX_ACTIVITY_LOG)

# --- Globals ---

pricing_client = PricingClient()
price_cache = PriceCache()
load_shedder = LoadShedder()
background_task = None


async def simulate_orders():
    """Background task: seed prices on startup, then execute simulated orders to generate metrics."""
    global order_count, error_count

    # Seed all symbols on startup so market data is available immediately
    loop = asyncio.get_event_loop()
    for symbol in SUPPORTED_SYMBOLS:
        try:
            await loop.run_in_executor(None, pricing_client.get_price, symbol)
        except Exception:
            pass  # Non-fatal — will be populated on next cycle

    while True:
        # Update Prometheus gauges for short-term response state
        CACHE_ACTIVE.set(1 if price_cache.active else 0)
        CACHE_AGE_SECONDS.set(price_cache.age_seconds())
        QUEUE_DEPTH.set(load_shedder.queue_depth)
        PRICING_SOURCE.set(1 if pricing_client.pricing_source == "backup" else 0)

        # Process 2 symbols per cycle for a more active trading floor feel
        for _ in range(2):
            symbol = random.choice(SUPPORTED_SYMBOLS)
            side = random.choice(["BUY", "SELL"])
            quantity = random.choice([50, 100, 200, 500, 1000])
            try:
                start = time.monotonic()

                # Short-term: serve from cache if active and price available
                cached_price = None
                if price_cache.active:
                    cached_price = price_cache.get_cached_price(
                        pricing_client.price_history, symbol
                    )

                if cached_price is not None:
                    price = cached_price
                elif load_shedder.active:
                    # Load shedding: limit concurrent requests
                    acquired = await load_shedder.acquire()
                    if acquired:
                        try:
                            price = await loop.run_in_executor(
                                None, pricing_client.get_price, symbol
                            )
                        finally:
                            load_shedder.release()
                    else:
                        # Shed: serve from cache if possible, else skip
                        SHED_REQUESTS_TOTAL.inc()
                        cached_price = price_cache.get_cached_price(
                            pricing_client.price_history, symbol
                        )
                        if cached_price is not None:
                            price = cached_price
                        else:
                            raise RuntimeError(f"Load shed and no cached price for {symbol}")
                else:
                    price = await loop.run_in_executor(
                        None, pricing_client.get_price, symbol
                    )

                elapsed = time.monotonic() - start

                ORDER_LATENCY.observe(elapsed)
                ORDERS_TOTAL.labels(symbol=symbol, status="success").inc()
                latency_samples.append(elapsed * 1000)  # store in ms
                order_count += 1

                trade_activity.append(TradeEntry(
                    symbol=symbol, side=side, quantity=quantity, price=price,
                    latency_ms=round(elapsed * 1000, 1),
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    status="filled",
                ))
            except Exception as e:
                elapsed = time.monotonic() - start
                ORDER_LATENCY.observe(elapsed)
                ORDERS_TOTAL.labels(symbol=symbol, status="error").inc()
                PRICING_ERRORS.labels(symbol=symbol, error_type=type(e).__name__).inc()
                latency_samples.append(elapsed * 1000)
                order_count += 1
                error_count += 1

                trade_activity.append(TradeEntry(
                    symbol=symbol, side=side, quantity=quantity, price=None,
                    latency_ms=round(elapsed * 1000, 1),
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    status="error",
                ))

        await asyncio.sleep(1)


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


@app.get("/market/prices")
async def market_prices():
    """Return current prices, changes, and history for all monitored symbols."""
    return {"quotes": pricing_client.get_all_quotes()}


@app.get("/market/activity")
async def market_activity():
    """Return recent trade activity log."""
    return {"trades": [t.to_dict() for t in list(trade_activity)[-15:]]}


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


# --- Short-Term Response Endpoints ---


@app.post("/admin/cache/activate")
async def cache_activate():
    """Activate price cache — serve last-known-good prices."""
    result = price_cache.activate()
    CACHE_ACTIVE.set(1)
    return result


@app.post("/admin/cache/deactivate")
async def cache_deactivate():
    """Deactivate price cache — resume live pricing."""
    result = price_cache.deactivate()
    CACHE_ACTIVE.set(0)
    CACHE_AGE_SECONDS.set(0)
    return result


@app.post("/admin/load-shedding/activate")
async def load_shedding_activate():
    """Activate load shedding — limit concurrent pricing requests."""
    result = load_shedder.activate()
    return result


@app.post("/admin/load-shedding/deactivate")
async def load_shedding_deactivate():
    """Deactivate load shedding — allow unlimited concurrent requests."""
    result = load_shedder.deactivate()
    QUEUE_DEPTH.set(0)
    return result


@app.post("/admin/pricing-source/backup")
async def pricing_source_backup():
    """Switch to backup pricing source (yfinance download method)."""
    pricing_client.pricing_source = "backup"
    PRICING_SOURCE.set(1)
    return {
        "pricing_source": "backup",
        "message": "Switched to backup pricing source (bulk download method)",
    }


@app.post("/admin/pricing-source/primary")
async def pricing_source_primary():
    """Switch to primary pricing source (yfinance fast_info method)."""
    pricing_client.pricing_source = "primary"
    PRICING_SOURCE.set(0)
    return {
        "pricing_source": "primary",
        "message": "Switched to primary pricing source (fast_info method)",
    }


@app.get("/admin/platform-status")
async def platform_status():
    """Return combined status of all short-term response controls."""
    return {
        "cache": price_cache.status(),
        "load_shedding": load_shedder.status(),
        "pricing_source": pricing_client.pricing_source,
        "chaos_mode": pricing_client.chaos_mode,
    }


@app.get("/market/status")
async def market_status():
    """Return whether the NYSE market is currently open and when it next opens."""
    return pricing_client.get_market_status()


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
        "cache_active": price_cache.active,
        "load_shedding_active": load_shedder.active,
        "pricing_source": pricing_client.pricing_source,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
