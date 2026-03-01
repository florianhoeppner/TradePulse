"""
TradePulse Pricing Client
Fetches live stock prices from Yahoo Finance.

WARNING: This client is intentionally simple — no retry logic,
no circuit breaker, no timeout handling. A single failure in the
upstream Yahoo Finance API will cascade directly to the caller.
"""

import time
import random
import yfinance as yf


# Supported symbols for the trading demo
SUPPORTED_SYMBOLS = ["AAPL", "MSFT", "GOOGL", "JPM", "GS"]


class PricingClient:
    """Fetches live market prices. No resiliency patterns implemented."""

    def __init__(self):
        self.chaos_mode = False

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

        return round(price, 2)
