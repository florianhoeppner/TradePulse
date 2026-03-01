"""Tests for the TradePulse Trading Service."""

import pytest
from unittest.mock import patch, MagicMock
from httpx import AsyncClient, ASGITransport

from main import app
from pricing_client import PricingClient, SUPPORTED_SYMBOLS


# --- PricingClient unit tests ---


class TestPricingClient:
    def test_supported_symbols(self):
        assert "AAPL" in SUPPORTED_SYMBOLS
        assert "MSFT" in SUPPORTED_SYMBOLS
        assert "GOOGL" in SUPPORTED_SYMBOLS
        assert "JPM" in SUPPORTED_SYMBOLS
        assert "GS" in SUPPORTED_SYMBOLS

    def test_unsupported_symbol_raises(self):
        client = PricingClient()
        with pytest.raises(ValueError, match="Unsupported symbol"):
            client.get_price("INVALID")

    @patch("pricing_client.yf.Ticker")
    def test_get_price_returns_float(self, mock_ticker_cls):
        mock_fast_info = {"lastPrice": 150.25}
        mock_ticker_cls.return_value.fast_info = mock_fast_info

        client = PricingClient()
        price = client.get_price("AAPL")

        assert price == 150.25
        mock_ticker_cls.assert_called_once_with("AAPL")

    @patch("pricing_client.yf.Ticker")
    def test_chaos_mode_adds_delay(self, mock_ticker_cls):
        mock_fast_info = {"lastPrice": 200.0}
        mock_ticker_cls.return_value.fast_info = mock_fast_info

        client = PricingClient()
        client.chaos_mode = True

        with patch("pricing_client.time.sleep") as mock_sleep:
            price = client.get_price("MSFT")
            mock_sleep.assert_called_once()
            delay = mock_sleep.call_args[0][0]
            assert 2.0 <= delay <= 5.0

        assert price == 200.0

    def test_chaos_mode_default_off(self):
        client = PricingClient()
        assert client.chaos_mode is False


# --- FastAPI endpoint tests ---


@pytest.fixture
def transport():
    return ASGITransport(app=app, raise_app_exceptions=False)


@pytest.mark.asyncio
async def test_health(transport):
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "chaos_mode" in data


@pytest.mark.asyncio
async def test_metrics_endpoint(transport):
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/metrics")
    assert response.status_code == 200
    body = response.text
    assert "tradepulse_order_latency_seconds" in body or "# HELP" in body


@pytest.mark.asyncio
async def test_chaos_toggle(transport):
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Enable chaos
        response = await client.post("/chaos/enable")
        assert response.status_code == 200
        assert response.json()["chaos_mode"] is True

        # Check status
        response = await client.get("/chaos/status")
        assert response.json()["chaos_mode"] is True

        # Disable chaos
        response = await client.post("/chaos/disable")
        assert response.status_code == 200
        assert response.json()["chaos_mode"] is False

        # Check status again
        response = await client.get("/chaos/status")
        assert response.json()["chaos_mode"] is False


@pytest.mark.asyncio
@patch("main.pricing_client")
async def test_create_order(mock_client, transport):
    mock_client.get_price.return_value = 175.50
    mock_client.chaos_mode = False

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/orders?symbol=AAPL&quantity=10")

    assert response.status_code == 200
    data = response.json()
    assert data["symbol"] == "AAPL"
    assert data["quantity"] == 10
    assert data["price"] == 175.50
    assert data["status"] == "filled"
    assert "order_id" in data
    assert "latency_ms" in data
