"""
TradePulse Pricing Client
Fetches live stock prices from Yahoo Finance.

WARNING: This client is intentionally simple — no retry logic,
no circuit breaker, no timeout handling. A single failure in the
upstream Yahoo Finance API will cascade directly to the caller.
"""

import collections
import time
import random
from datetime import datetime, timezone

import yfinance as yf


# Supported symbols for the trading demo
SUPPORTED_SYMBOLS = ["AAPL", "MSFT", "GOOGL", "JPM", "GS"]

COMPANY_NAMES = {
    "AAPL": "Apple Inc.",
    "MSFT": "Microsoft Corp.",
    "GOOGL": "Alphabet Inc.",
    "JPM": "JPMorgan Chase",
    "GS": "Goldman Sachs",
}

MAX_PRICE_HISTORY = 30


class PriceSnapshot:
    """A single price observation with timestamp."""
    __slots__ = ("price", "timestamp")

    def __init__(self, price: float, timestamp: str):
        self.price = price
        self.timestamp = timestamp


class PricingClient:
    """Fetches live market prices. No resiliency patterns implemented."""

    def __init__(self):
        self.chaos_mode = False
        # Price history per symbol for sparklines and change calculation
        self.price_history: dict[str, collections.deque[PriceSnapshot]] = {
            sym: collections.deque(maxlen=MAX_PRICE_HISTORY)
            for sym in SUPPORTED_SYMBOLS
        }

    def get_price(self, symbol: str) -> float:
        """
        Get the current market price for a symbol.

        Makes a direct call to Yahoo Finance with no retry,
        no timeout, and no circuit breaker protection.
        """
        if symbol not in SUPPORTED_SYMBOLS:
            raise ValueError(f"Unsupported symbol: {symbol}")

        # In chaos mode, simulate upstream latency / degradation
        if self.chaos_mode:
            delay = random.uniform(2.0, 5.0)
            time.sleep(delay)

        ticker = yf.Ticker(symbol)
        data = ticker.fast_info
        price = data["lastPrice"]
        price = round(price, 2)

        # Record price snapshot
        self.price_history[symbol].append(
            PriceSnapshot(price, datetime.now(timezone.utc).isoformat())
        )

        return price

    def get_all_quotes(self) -> list[dict]:
        """Return latest quote data for all symbols with history for sparklines."""
        quotes = []
        for sym in SUPPORTED_SYMBOLS:
            history = self.price_history[sym]
            if not history:
                continue
            latest = history[-1]
            # Calculate change from first available snapshot
            first = history[0]
            change = round(latest.price - first.price, 2)
            change_pct = round((change / first.price) * 100, 2) if first.price else 0.0
            quotes.append({
                "symbol": sym,
                "name": COMPANY_NAMES.get(sym, sym),
                "price": latest.price,
                "change": change,
                "changePercent": change_pct,
                "lastUpdated": latest.timestamp,
                "history": [s.price for s in history],
            })
        return quotes
