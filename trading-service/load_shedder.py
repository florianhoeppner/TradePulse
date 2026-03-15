"""
TradePulse Load Shedder
Limits concurrent pricing requests via asyncio.Semaphore.
When the semaphore can't be acquired within the timeout,
the caller should serve from cache instead.
"""

import asyncio


class LoadShedder:
    """Controls concurrent pricing request limits to protect a degraded upstream."""

    def __init__(self, max_concurrent: int = 3, wait_timeout: float = 0.5):
        self.active: bool = False
        self.max_concurrent = max_concurrent
        self.wait_timeout = wait_timeout
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self.shed_count: int = 0
        self.queue_depth: int = 0

    def activate(self) -> dict:
        """Activate load shedding. Returns status dict."""
        self.active = True
        self.shed_count = 0
        self.queue_depth = 0
        self._semaphore = asyncio.Semaphore(self.max_concurrent)
        return {
            "status": "activated",
            "load_shedding_active": True,
            "max_concurrent": self.max_concurrent,
            "message": f"Load shedding active — limiting to {self.max_concurrent} concurrent pricing requests",
        }

    def deactivate(self) -> dict:
        """Deactivate load shedding. Returns status dict."""
        self.active = False
        self.shed_count = 0
        self.queue_depth = 0
        self._semaphore = asyncio.Semaphore(self.max_concurrent)
        return {
            "status": "deactivated",
            "load_shedding_active": False,
            "message": "Load shedding deactivated — unlimited concurrent requests",
        }

    async def acquire(self) -> bool:
        """Try to acquire a slot. Returns True if acquired, False if shed."""
        self.queue_depth += 1
        try:
            await asyncio.wait_for(self._semaphore.acquire(), timeout=self.wait_timeout)
            return True
        except asyncio.TimeoutError:
            self.shed_count += 1
            return False
        finally:
            self.queue_depth = max(0, self.queue_depth - 1)

    def release(self) -> None:
        """Release a slot back to the semaphore."""
        self._semaphore.release()

    def status(self) -> dict:
        """Return current load shedding status."""
        return {
            "active": self.active,
            "shed_count": self.shed_count,
            "queue_depth": self.queue_depth,
        }
