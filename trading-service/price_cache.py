"""
TradePulse Price Cache
Tracks cache activation state. Reuses PricingClient.price_history
for actual cached price data — no duplicate storage.
"""

import time


class PriceCache:
    """Controls whether the trading service serves cached prices instead of live ones."""

    def __init__(self):
        self.active: bool = False
        self.activated_at: float | None = None

    def activate(self) -> dict:
        """Activate cache mode. Returns status dict."""
        self.active = True
        self.activated_at = time.monotonic()
        return {
            "status": "activated",
            "cache_active": True,
            "message": "Price cache activated — serving last-known-good prices",
        }

    def deactivate(self) -> dict:
        """Deactivate cache mode. Returns status dict."""
        self.active = False
        self.activated_at = None
        return {
            "status": "deactivated",
            "cache_active": False,
            "message": "Price cache deactivated — serving live prices",
        }

    def get_cached_price(self, price_history: dict, symbol: str) -> float | None:
        """Return the latest cached price for a symbol, or None if unavailable."""
        history = price_history.get(symbol)
        if not history:
            return None
        return history[-1].price

    def age_seconds(self) -> float:
        """Seconds since cache was activated, or 0 if inactive."""
        if not self.active or self.activated_at is None:
            return 0.0
        return round(time.monotonic() - self.activated_at, 1)

    def status(self) -> dict:
        """Return current cache status."""
        return {
            "active": self.active,
            "age_seconds": self.age_seconds(),
        }
