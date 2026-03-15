"""Shared test fixtures for trading service tests.

Mocks yfinance at import time since it may not be installable in all environments.
"""

import sys
from unittest.mock import MagicMock

# Mock yfinance before any test module imports pricing_client
if "yfinance" not in sys.modules:
    sys.modules["yfinance"] = MagicMock()
