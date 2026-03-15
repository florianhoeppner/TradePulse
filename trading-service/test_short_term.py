"""Tests for short-term response features: price cache, load shedding, backup pricing."""

import asyncio
import collections
import pytest
from unittest.mock import patch, MagicMock
from httpx import AsyncClient, ASGITransport

import main
from main import app
from price_cache import PriceCache
from load_shedder import LoadShedder
from pricing_client import PricingClient, PriceSnapshot


@pytest.fixture(autouse=True)
def clean_state():
    """Reset short-term response state before each test."""
    main.price_cache.active = False
    main.price_cache.activated_at = None
    main.load_shedder.active = False
    main.load_shedder.shed_count = 0
    main.load_shedder.queue_depth = 0
    main.pricing_client.pricing_source = "primary"
    main.pricing_client.chaos_mode = False
    yield
    main.price_cache.active = False
    main.price_cache.activated_at = None
    main.load_shedder.active = False
    main.load_shedder.shed_count = 0
    main.load_shedder.queue_depth = 0
    main.pricing_client.pricing_source = "primary"
    main.pricing_client.chaos_mode = False


@pytest.fixture
def transport():
    return ASGITransport(app=app, raise_app_exceptions=False)


# --- PriceCache unit tests ---


class TestPriceCache:
    def test_initial_state(self):
        cache = PriceCache()
        assert cache.active is False
        assert cache.activated_at is None
        assert cache.age_seconds() == 0.0

    def test_activate(self):
        cache = PriceCache()
        result = cache.activate()
        assert cache.active is True
        assert cache.activated_at is not None
        assert result["cache_active"] is True

    def test_deactivate(self):
        cache = PriceCache()
        cache.activate()
        result = cache.deactivate()
        assert cache.active is False
        assert cache.activated_at is None
        assert result["cache_active"] is False

    def test_age_seconds_when_active(self):
        cache = PriceCache()
        cache.activate()
        age = cache.age_seconds()
        assert age >= 0.0

    def test_age_seconds_when_inactive(self):
        cache = PriceCache()
        assert cache.age_seconds() == 0.0

    def test_get_cached_price_with_data(self):
        cache = PriceCache()
        history = {
            "AAPL": collections.deque([PriceSnapshot(150.25, "2025-01-01T00:00:00Z")])
        }
        price = cache.get_cached_price(history, "AAPL")
        assert price == 150.25

    def test_get_cached_price_empty_history(self):
        cache = PriceCache()
        history = {"AAPL": collections.deque()}
        assert cache.get_cached_price(history, "AAPL") is None

    def test_get_cached_price_missing_symbol(self):
        cache = PriceCache()
        assert cache.get_cached_price({}, "AAPL") is None

    def test_status(self):
        cache = PriceCache()
        status = cache.status()
        assert "active" in status
        assert "age_seconds" in status


# --- LoadShedder unit tests ---


class TestLoadShedder:
    def test_initial_state(self):
        shedder = LoadShedder()
        assert shedder.active is False
        assert shedder.shed_count == 0
        assert shedder.queue_depth == 0

    def test_activate(self):
        shedder = LoadShedder()
        result = shedder.activate()
        assert shedder.active is True
        assert result["load_shedding_active"] is True

    def test_deactivate(self):
        shedder = LoadShedder()
        shedder.activate()
        result = shedder.deactivate()
        assert shedder.active is False
        assert result["load_shedding_active"] is False

    @pytest.mark.asyncio
    async def test_acquire_succeeds(self):
        shedder = LoadShedder(max_concurrent=3)
        result = await shedder.acquire()
        assert result is True
        shedder.release()

    @pytest.mark.asyncio
    async def test_acquire_sheds_when_full(self):
        shedder = LoadShedder(max_concurrent=1, wait_timeout=0.1)
        # Acquire the only slot
        await shedder.acquire()
        # Next acquire should be shed
        result = await shedder.acquire()
        assert result is False
        assert shedder.shed_count == 1
        shedder.release()

    def test_status(self):
        shedder = LoadShedder()
        status = shedder.status()
        assert "active" in status
        assert "shed_count" in status
        assert "queue_depth" in status


# --- Backup pricing unit tests ---


class TestBackupPricing:
    def test_pricing_source_default(self):
        client = PricingClient()
        assert client.pricing_source == "primary"

    @patch("pricing_client.yf.download")
    def test_backup_pricing(self, mock_download):
        import pandas as pd
        mock_download.return_value = pd.DataFrame({"Close": [152.50]})
        client = PricingClient()
        client.pricing_source = "backup"
        price = client.get_price("AAPL")
        assert price == 152.5
        mock_download.assert_called_once_with("AAPL", period="1d", progress=False)

    @patch("pricing_client.yf.download")
    def test_backup_pricing_empty_data(self, mock_download):
        import pandas as pd
        mock_download.return_value = pd.DataFrame()
        client = PricingClient()
        client.pricing_source = "backup"
        with pytest.raises(ValueError, match="No data from backup source"):
            client.get_price("AAPL")

    @patch("pricing_client.yf.download")
    def test_backup_records_history(self, mock_download):
        import pandas as pd
        mock_download.return_value = pd.DataFrame({"Close": [152.50]})
        client = PricingClient()
        client.pricing_source = "backup"
        client.get_price("AAPL")
        assert len(client.price_history["AAPL"]) == 1
        assert client.price_history["AAPL"][-1].price == 152.5


# --- Endpoint tests ---


class TestCacheEndpoints:
    @pytest.mark.asyncio
    async def test_activate_cache(self, transport):
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/admin/cache/activate")
            assert response.status_code == 200
            data = response.json()
            assert data["cache_active"] is True

    @pytest.mark.asyncio
    async def test_deactivate_cache(self, transport):
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            await client.post("/admin/cache/activate")
            response = await client.post("/admin/cache/deactivate")
            assert response.status_code == 200
            data = response.json()
            assert data["cache_active"] is False


class TestLoadSheddingEndpoints:
    @pytest.mark.asyncio
    async def test_activate_load_shedding(self, transport):
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/admin/load-shedding/activate")
            assert response.status_code == 200
            data = response.json()
            assert data["load_shedding_active"] is True

    @pytest.mark.asyncio
    async def test_deactivate_load_shedding(self, transport):
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            await client.post("/admin/load-shedding/activate")
            response = await client.post("/admin/load-shedding/deactivate")
            assert response.status_code == 200
            data = response.json()
            assert data["load_shedding_active"] is False


class TestPricingSourceEndpoints:
    @pytest.mark.asyncio
    async def test_switch_to_backup(self, transport):
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/admin/pricing-source/backup")
            assert response.status_code == 200
            data = response.json()
            assert data["pricing_source"] == "backup"

    @pytest.mark.asyncio
    async def test_switch_to_primary(self, transport):
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            await client.post("/admin/pricing-source/backup")
            response = await client.post("/admin/pricing-source/primary")
            assert response.status_code == 200
            data = response.json()
            assert data["pricing_source"] == "primary"


class TestPlatformStatus:
    @pytest.mark.asyncio
    async def test_platform_status(self, transport):
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/admin/platform-status")
            assert response.status_code == 200
            data = response.json()
            assert "cache" in data
            assert "load_shedding" in data
            assert "pricing_source" in data
            assert "chaos_mode" in data

    @pytest.mark.asyncio
    async def test_platform_status_reflects_changes(self, transport):
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            await client.post("/admin/cache/activate")
            await client.post("/admin/pricing-source/backup")
            response = await client.get("/admin/platform-status")
            data = response.json()
            assert data["cache"]["active"] is True
            assert data["pricing_source"] == "backup"


class TestMetricsSummaryWithPlatformState:
    @pytest.mark.asyncio
    async def test_metrics_summary_includes_platform_state(self, transport):
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/metrics/summary")
            assert response.status_code == 200
            data = response.json()
            assert "cache_active" in data
            assert "load_shedding_active" in data
            assert "pricing_source" in data
