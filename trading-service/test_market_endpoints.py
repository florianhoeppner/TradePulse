"""Tests for TradePulse Trading Service market data and metrics endpoints."""

import collections
import pytest
from unittest.mock import patch, MagicMock
from httpx import AsyncClient, ASGITransport

import main
from main import app, TradeEntry


@pytest.fixture(autouse=True)
def clean_global_state():
    """Reset global state before each test."""
    main.trade_activity.clear()
    main.latency_samples.clear()
    main.order_count = 0
    main.error_count = 0
    main.pricing_client.chaos_mode = False
    yield
    main.trade_activity.clear()
    main.latency_samples.clear()
    main.order_count = 0
    main.error_count = 0
    main.pricing_client.chaos_mode = False


@pytest.fixture
def transport():
    return ASGITransport(app=app, raise_app_exceptions=False)


# --- Market Prices ---


class TestMarketPrices:
    @pytest.mark.asyncio
    @patch("main.pricing_client")
    async def test_returns_quotes(self, mock_client, transport):
        mock_client.get_all_quotes.return_value = [
            {"symbol": "AAPL", "name": "Apple Inc.", "price": 150.0,
             "change": 1.5, "changePercent": 1.0, "lastUpdated": "2026-01-01T00:00:00Z",
             "history": [149.0, 150.0]},
        ]
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/market/prices")
        assert response.status_code == 200
        data = response.json()
        assert "quotes" in data
        assert len(data["quotes"]) == 1
        assert data["quotes"][0]["symbol"] == "AAPL"

    @pytest.mark.asyncio
    @patch("main.pricing_client")
    async def test_empty_quotes(self, mock_client, transport):
        mock_client.get_all_quotes.return_value = []
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/market/prices")
        assert response.status_code == 200
        assert response.json() == {"quotes": []}


# --- Market Activity ---


class TestMarketActivity:
    @pytest.mark.asyncio
    async def test_returns_trades(self, transport):
        main.trade_activity.append(TradeEntry(
            symbol="AAPL", side="BUY", quantity=100, price=150.0,
            latency_ms=12.5, timestamp="2026-01-01T00:00:00Z", status="filled",
        ))
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/market/activity")
        assert response.status_code == 200
        data = response.json()
        assert len(data["trades"]) == 1
        trade = data["trades"][0]
        assert trade["symbol"] == "AAPL"
        assert trade["side"] == "BUY"
        assert trade["status"] == "filled"

    @pytest.mark.asyncio
    async def test_empty_activity(self, transport):
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/market/activity")
        assert response.status_code == 200
        assert response.json() == {"trades": []}

    @pytest.mark.asyncio
    async def test_limited_to_15(self, transport):
        """Only the 15 most recent trades are returned."""
        for i in range(20):
            main.trade_activity.append(TradeEntry(
                symbol="AAPL", side="BUY", quantity=i + 1, price=150.0,
                latency_ms=10.0, timestamp=f"2026-01-01T00:00:{i:02d}Z", status="filled",
            ))
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/market/activity")
        data = response.json()
        assert len(data["trades"]) == 15
        # First returned trade should be quantity=6 (20 entries, last 15 = indices 5-19, quantity 6-20)
        assert data["trades"][0]["quantity"] == 6


# --- Market Status ---


class TestMarketStatus:
    @pytest.mark.asyncio
    @patch("main.pricing_client")
    async def test_returns_status(self, mock_client, transport):
        mock_client.get_market_status.return_value = {
            "is_open": True,
            "exchange": "NYSE",
            "next_open_utc": "2026-01-02T14:30:00Z",
            "current_time_et": "2026-01-01T10:00:00-05:00",
        }
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/market/status")
        assert response.status_code == 200
        data = response.json()
        assert data["is_open"] is True
        assert data["exchange"] == "NYSE"

    @pytest.mark.asyncio
    @patch("main.pricing_client")
    async def test_market_closed(self, mock_client, transport):
        mock_client.get_market_status.return_value = {
            "is_open": False,
            "exchange": "NYSE",
            "next_open_utc": "2026-01-02T14:30:00Z",
            "current_time_et": "2026-01-01T20:00:00-05:00",
        }
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/market/status")
        assert response.status_code == 200
        assert response.json()["is_open"] is False


# --- Metrics Summary ---


class TestMetricsSummary:
    @pytest.mark.asyncio
    async def test_with_samples(self, transport):
        """p99 and p50 are computed correctly from latency samples."""
        # Add 100 samples: 1.0, 2.0, ..., 100.0
        for i in range(1, 101):
            main.latency_samples.append(float(i))
        main.order_count = 100
        main.error_count = 5

        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/metrics/summary")
        assert response.status_code == 200
        data = response.json()
        assert data["p99_latency_ms"] == 100.0  # index 99 of 100 sorted samples
        assert data["p50_latency_ms"] == 51.0   # index 50 of 100 sorted samples
        assert data["total_orders"] == 100
        assert data["total_errors"] == 5
        assert data["sample_count"] == 100

    @pytest.mark.asyncio
    async def test_empty_samples(self, transport):
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/metrics/summary")
        assert response.status_code == 200
        data = response.json()
        assert data["p99_latency_ms"] == 0.0
        assert data["p50_latency_ms"] == 0.0
        assert data["total_orders"] == 0
        assert data["sample_count"] == 0
