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
from datetime import datetime, date, timedelta, timezone
from zoneinfo import ZoneInfo

import yfinance as yf

ET = ZoneInfo("America/New_York")

# NYSE market holidays for 2025-2026 (dates when the market is fully closed)
_NYSE_HOLIDAYS: set[date] = {
    # 2025
    date(2025, 1, 1),    # New Year's Day
    date(2025, 1, 20),   # MLK Day
    date(2025, 2, 17),   # Presidents' Day
    date(2025, 4, 18),   # Good Friday
    date(2025, 5, 26),   # Memorial Day
    date(2025, 6, 19),   # Juneteenth
    date(2025, 7, 4),    # Independence Day
    date(2025, 9, 1),    # Labor Day
    date(2025, 11, 27),  # Thanksgiving
    date(2025, 12, 25),  # Christmas
    # 2026
    date(2026, 1, 1),    # New Year's Day
    date(2026, 1, 19),   # MLK Day
    date(2026, 2, 16),   # Presidents' Day
    date(2026, 4, 3),    # Good Friday
    date(2026, 5, 25),   # Memorial Day
    date(2026, 6, 19),   # Juneteenth
    date(2026, 7, 3),    # Independence Day (observed)
    date(2026, 9, 7),    # Labor Day
    date(2026, 11, 26),  # Thanksgiving
    date(2026, 12, 25),  # Christmas
}

MARKET_OPEN_HOUR, MARKET_OPEN_MIN = 9, 30
MARKET_CLOSE_HOUR, MARKET_CLOSE_MIN = 16, 0


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


def _is_trading_day(d: date) -> bool:
    """Check if a date is a NYSE trading day (weekday, not a holiday)."""
    return d.weekday() < 5 and d not in _NYSE_HOLIDAYS


class PricingClient:
    """Fetches live market prices. No resiliency patterns implemented."""

    def __init__(self):
        self.chaos_mode = False
        # Price history per symbol for sparklines and change calculation
        self.price_history: dict[str, collections.deque[PriceSnapshot]] = {
            sym: collections.deque(maxlen=MAX_PRICE_HISTORY)
            for sym in SUPPORTED_SYMBOLS
        }

    @staticmethod
    def is_market_open() -> bool:
        """Check if NYSE is currently in regular trading hours."""
        now_et = datetime.now(ET)
        if not _is_trading_day(now_et.date()):
            return False
        market_open = now_et.replace(hour=MARKET_OPEN_HOUR, minute=MARKET_OPEN_MIN, second=0, microsecond=0)
        market_close = now_et.replace(hour=MARKET_CLOSE_HOUR, minute=MARKET_CLOSE_MIN, second=0, microsecond=0)
        return market_open <= now_et < market_close

    @staticmethod
    def next_market_open() -> datetime:
        """Return the next NYSE market open as a UTC datetime."""
        now_et = datetime.now(ET)
        candidate = now_et.replace(hour=MARKET_OPEN_HOUR, minute=MARKET_OPEN_MIN, second=0, microsecond=0)
        # If market hasn't opened yet today and today is a trading day, it's today
        if _is_trading_day(now_et.date()) and now_et < candidate:
            return candidate.astimezone(timezone.utc)
        # Otherwise, advance to next trading day
        candidate += timedelta(days=1)
        while not _is_trading_day(candidate.date()):
            candidate += timedelta(days=1)
        candidate = candidate.replace(hour=MARKET_OPEN_HOUR, minute=MARKET_OPEN_MIN, second=0, microsecond=0)
        return candidate.astimezone(timezone.utc)

    def get_market_status(self) -> dict:
        """Return current market open/closed status with countdown info."""
        now_et = datetime.now(ET)
        return {
            "is_open": self.is_market_open(),
            "exchange": "NYSE",
            "next_open_utc": self.next_market_open().isoformat(),
            "current_time_et": now_et.strftime("%I:%M %p ET"),
        }

    def get_price(self, symbol: str) -> float:
        """
        Get the current market price for a symbol.

        Makes a direct call to Yahoo Finance with no retry,
        no timeout, and no circuit breaker protection.
        Falls back to previousClose when lastPrice is unavailable.
        """
        if symbol not in SUPPORTED_SYMBOLS:
            raise ValueError(f"Unsupported symbol: {symbol}")

        # In chaos mode, simulate upstream latency / degradation
        if self.chaos_mode:
            delay = random.uniform(2.0, 5.0)
            time.sleep(delay)

        ticker = yf.Ticker(symbol)
        data = ticker.fast_info
        try:
            price = data["lastPrice"]
        except (KeyError, Exception):
            # Fallback to previous close when live price unavailable
            price = data["previousClose"]
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
