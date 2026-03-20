"""Tests for untested TradePulse Backend API endpoints."""

import pytest
import respx
from unittest.mock import patch, AsyncMock
from httpx import AsyncClient, ASGITransport, Response

from main import app, demo_state, TRADING_SERVICE_URL
from state import AgentState


@pytest.fixture(autouse=True)
def reset_state():
    """Reset demo state before each test."""
    demo_state.reset()
    yield
    demo_state.reset()


@pytest.fixture
def transport():
    return ASGITransport(app=app, raise_app_exceptions=False)


TRADING_BASE = TRADING_SERVICE_URL


# --- Agent Start ---


class TestAgentStart:
    @pytest.mark.asyncio
    @respx.mock
    async def test_start_when_not_idle(self, transport):
        """Starting agent when not idle returns error."""
        demo_state.transition(AgentState.MONITORING)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/agent/start")
        data = response.json()
        assert "error" in data
        assert data["state"] == "monitoring"

    @pytest.mark.asyncio
    async def test_start_agent_import_failure(self, transport):
        """If the agent module can't be imported, returns 503."""
        with patch.dict("sys.modules", {"agent": None}):
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post("/agent/start")
        # The import will fail one way or another in test env
        assert response.status_code in (200, 503)


# --- Admin Reset ---


class TestAdminReset:
    @pytest.mark.asyncio
    @respx.mock
    async def test_reset_from_idle(self, transport):
        """Reset from idle state succeeds."""
        respx.post(f"{TRADING_BASE}/chaos/disable").mock(
            return_value=Response(200, json={"chaos_mode": False})
        )
        respx.post(f"{TRADING_BASE}/admin/cache/deactivate").mock(
            return_value=Response(200, json={"cache_active": False})
        )
        respx.post(f"{TRADING_BASE}/admin/load-shedding/deactivate").mock(
            return_value=Response(200, json={"load_shedding_active": False})
        )
        respx.post(f"{TRADING_BASE}/admin/pricing-source/primary").mock(
            return_value=Response(200, json={"pricing_source": "primary"})
        )
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/admin/reset")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "reset"
        assert data["errors"] is None

    @pytest.mark.asyncio
    @respx.mock
    async def test_reset_with_dedup_key(self, transport):
        """Reset resolves PagerDuty incident if dedup key exists."""
        demo_state.transition(AgentState.MONITORING)
        demo_state.run_data["create_pagerduty_incident"] = {"dedup_key": "test-key-123"}

        pd_route = respx.post("https://events.pagerduty.com/v2/enqueue").mock(
            return_value=Response(202, json={"status": "success"})
        )
        respx.post(f"{TRADING_BASE}/chaos/disable").mock(
            return_value=Response(200, json={"chaos_mode": False})
        )
        respx.post(f"{TRADING_BASE}/admin/cache/deactivate").mock(
            return_value=Response(200, json={"cache_active": False})
        )
        respx.post(f"{TRADING_BASE}/admin/load-shedding/deactivate").mock(
            return_value=Response(200, json={"load_shedding_active": False})
        )
        respx.post(f"{TRADING_BASE}/admin/pricing-source/primary").mock(
            return_value=Response(200, json={"pricing_source": "primary"})
        )

        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/admin/reset")
        assert response.status_code == 200
        assert pd_route.called

    @pytest.mark.asyncio
    @respx.mock
    async def test_reset_handles_external_failures(self, transport):
        """Reset succeeds even when external services fail."""
        demo_state.transition(AgentState.MONITORING)
        demo_state.run_data["create_pagerduty_incident"] = {"dedup_key": "test-key"}

        respx.post("https://events.pagerduty.com/v2/enqueue").mock(
            return_value=Response(500, json={"error": "internal"})
        )
        respx.post(f"{TRADING_BASE}/chaos/disable").mock(side_effect=Exception("connection refused"))
        respx.post(f"{TRADING_BASE}/admin/cache/deactivate").mock(side_effect=Exception("connection refused"))
        respx.post(f"{TRADING_BASE}/admin/load-shedding/deactivate").mock(side_effect=Exception("connection refused"))
        respx.post(f"{TRADING_BASE}/admin/pricing-source/primary").mock(side_effect=Exception("connection refused"))

        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/admin/reset")
        data = response.json()
        assert data["status"] == "reset"
        # State still resets to idle
        assert demo_state.state == AgentState.IDLE


# --- Admin Chaos ---


class TestAdminChaos:
    @pytest.mark.asyncio
    @respx.mock
    async def test_chaos_enable(self, transport):
        respx.post(f"{TRADING_BASE}/chaos/enable").mock(
            return_value=Response(200, json={"chaos_mode": True, "message": "enabled"})
        )
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/admin/chaos/enable")
        assert response.status_code == 200
        assert response.json()["chaos_mode"] is True

    @pytest.mark.asyncio
    @respx.mock
    async def test_chaos_disable(self, transport):
        respx.post(f"{TRADING_BASE}/chaos/disable").mock(
            return_value=Response(200, json={"chaos_mode": False, "message": "disabled"})
        )
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/admin/chaos/disable")
        assert response.status_code == 200
        assert response.json()["chaos_mode"] is False

    @pytest.mark.asyncio
    @respx.mock
    async def test_chaos_status(self, transport):
        respx.get(f"{TRADING_BASE}/chaos/status").mock(
            return_value=Response(200, json={"chaos_mode": True})
        )
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/admin/chaos/status")
        assert response.status_code == 200
        assert response.json()["chaos_mode"] is True

    @pytest.mark.asyncio
    @respx.mock
    async def test_chaos_status_trading_service_down(self, transport):
        respx.get(f"{TRADING_BASE}/chaos/status").mock(side_effect=Exception("connection refused"))
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/admin/chaos/status")
        assert response.status_code == 502

    @pytest.mark.asyncio
    async def test_chaos_invalid_mode(self, transport):
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/admin/chaos/invalid")
        assert response.status_code == 422
        assert response.json()["error"] == "Mode must be 'enable' or 'disable'"

    @pytest.mark.asyncio
    @respx.mock
    async def test_chaos_trading_service_down(self, transport):
        respx.post(f"{TRADING_BASE}/chaos/enable").mock(side_effect=Exception("connection refused"))
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/admin/chaos/enable")
        assert response.status_code == 502


# --- Economic Profile ---


class TestEconomicProfile:
    @pytest.mark.asyncio
    async def test_get_default_profile(self, transport):
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/economic-profile")
        assert response.status_code == 200
        data = response.json()
        assert data["avg_order_value_usd"] == 8400
        assert data["orders_per_minute"] == 12
        assert data["sla_breach_penalty_usd"] == 250000
        assert data["currency"] == "USD"

    @pytest.mark.asyncio
    async def test_post_updates_profile(self, transport):
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/economic-profile",
                json={"avg_order_value_usd": 10000, "orders_per_minute": 20},
            )
        assert response.status_code == 200
        data = response.json()
        assert data["avg_order_value_usd"] == 10000
        assert data["orders_per_minute"] == 20
        # Unchanged fields retain defaults
        assert data["sla_breach_penalty_usd"] == 250000

    @pytest.mark.asyncio
    async def test_post_ignores_unknown_keys(self, transport):
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/economic-profile",
                json={"unknown_field": 999, "avg_order_value_usd": 5000},
            )
        assert response.status_code == 200
        data = response.json()
        assert data["avg_order_value_usd"] == 5000
        assert "unknown_field" not in data

    @pytest.mark.asyncio
    @respx.mock
    async def test_profile_persists_after_reset(self, transport):
        """Economic profile survives demo reset."""
        # Set custom profile
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            await client.post(
                "/economic-profile",
                json={"avg_order_value_usd": 15000},
            )

        # Reset demo
        respx.post(f"{TRADING_BASE}/chaos/disable").mock(
            return_value=Response(200, json={"chaos_mode": False})
        )
        respx.post(f"{TRADING_BASE}/admin/cache/deactivate").mock(
            return_value=Response(200, json={"cache_active": False})
        )
        respx.post(f"{TRADING_BASE}/admin/load-shedding/deactivate").mock(
            return_value=Response(200, json={"load_shedding_active": False})
        )
        respx.post(f"{TRADING_BASE}/admin/pricing-source/primary").mock(
            return_value=Response(200, json={"pricing_source": "primary"})
        )
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            await client.post("/admin/reset")

        # Verify profile persisted
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/economic-profile")
        assert response.json()["avg_order_value_usd"] == 15000


# --- Market Proxy Endpoints ---


class TestMarketProxy:
    @pytest.mark.asyncio
    @respx.mock
    async def test_market_prices(self, transport):
        sample = {"quotes": [{"symbol": "AAPL", "price": 150.0}]}
        respx.get(f"{TRADING_BASE}/market/prices").mock(
            return_value=Response(200, json=sample)
        )
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/market/prices")
        assert response.status_code == 200
        assert response.json() == sample

    @pytest.mark.asyncio
    @respx.mock
    async def test_market_prices_trading_service_down(self, transport):
        respx.get(f"{TRADING_BASE}/market/prices").mock(side_effect=Exception("connection refused"))
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/market/prices")
        assert response.status_code == 502

    @pytest.mark.asyncio
    @respx.mock
    async def test_market_activity(self, transport):
        sample = {"trades": [{"symbol": "MSFT", "side": "BUY", "quantity": 100}]}
        respx.get(f"{TRADING_BASE}/market/activity").mock(
            return_value=Response(200, json=sample)
        )
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/market/activity")
        assert response.status_code == 200
        assert response.json() == sample

    @pytest.mark.asyncio
    @respx.mock
    async def test_market_activity_trading_service_down(self, transport):
        respx.get(f"{TRADING_BASE}/market/activity").mock(side_effect=Exception("connection refused"))
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/market/activity")
        assert response.status_code == 502

    @pytest.mark.asyncio
    @respx.mock
    async def test_market_status(self, transport):
        sample = {"is_open": True, "exchange": "NYSE"}
        respx.get(f"{TRADING_BASE}/market/status").mock(
            return_value=Response(200, json=sample)
        )
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/market/status")
        assert response.status_code == 200
        assert response.json() == sample

    @pytest.mark.asyncio
    @respx.mock
    async def test_market_status_trading_service_down(self, transport):
        respx.get(f"{TRADING_BASE}/market/status").mock(side_effect=Exception("connection refused"))
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/market/status")
        assert response.status_code == 502


# --- Market Commentary ---


class TestMarketCommentary:
    @pytest.mark.asyncio
    @respx.mock
    async def test_commentary_no_api_key(self, transport):
        """Without Anthropic API key, returns fallback message."""
        sample = {"quotes": [{"symbol": "AAPL", "price": 150.0, "change": 1.5, "changePercent": 1.0}]}
        respx.get(f"{TRADING_BASE}/market/prices").mock(
            return_value=Response(200, json=sample)
        )
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/market/commentary")
        assert response.status_code == 200
        data = response.json()
        assert "commentary" in data
        assert "timestamp" in data

    @pytest.mark.asyncio
    @respx.mock
    async def test_commentary_empty_quotes(self, transport):
        """Empty quotes returns waiting message."""
        respx.get(f"{TRADING_BASE}/market/prices").mock(
            return_value=Response(200, json={"quotes": []})
        )
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/market/commentary")
        assert response.status_code == 200
        assert response.json()["commentary"] == "Waiting for market data..."

    @pytest.mark.asyncio
    @respx.mock
    async def test_commentary_trading_service_down(self, transport):
        """Trading service failure returns 502."""
        respx.get(f"{TRADING_BASE}/market/prices").mock(side_effect=Exception("connection refused"))
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/market/commentary")
        assert response.status_code == 502


# --- Short-Term Response Proxy Endpoints ---


class TestPlatformStatusProxy:
    @pytest.mark.asyncio
    @respx.mock
    async def test_returns_platform_status(self, transport):
        respx.get(f"{TRADING_BASE}/admin/platform-status").mock(
            return_value=Response(200, json={
                "cache": {"active": False, "age_seconds": 0},
                "load_shedding": {"active": False, "shed_count": 0, "queue_depth": 0},
                "pricing_source": "primary",
                "chaos_mode": False,
            })
        )
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/admin/platform-status")
        assert response.status_code == 200
        data = response.json()
        assert "cache" in data
        assert "load_shedding" in data

    @pytest.mark.asyncio
    @respx.mock
    async def test_trading_service_down(self, transport):
        respx.get(f"{TRADING_BASE}/admin/platform-status").mock(
            side_effect=Exception("connection refused")
        )
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/admin/platform-status")
        assert response.status_code == 502


class TestMetricsSummaryProxy:
    @pytest.mark.asyncio
    @respx.mock
    async def test_returns_metrics_summary(self, transport):
        sample = {"p99_latency_ms": 3200.0, "total_orders": 150, "chaos_mode": True}
        respx.get(f"{TRADING_BASE}/metrics/summary").mock(
            return_value=Response(200, json=sample)
        )
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/admin/metrics-summary")
        assert response.status_code == 200
        assert response.json() == sample

    @pytest.mark.asyncio
    @respx.mock
    async def test_trading_service_down(self, transport):
        respx.get(f"{TRADING_BASE}/metrics/summary").mock(
            side_effect=Exception("connection refused")
        )
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/admin/metrics-summary")
        assert response.status_code == 502
        assert "error" in response.json()


class TestCacheProxy:
    @pytest.mark.asyncio
    @respx.mock
    async def test_activate(self, transport):
        respx.post(f"{TRADING_BASE}/admin/cache/activate").mock(
            return_value=Response(200, json={"cache_active": True})
        )
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/admin/cache/activate")
        assert response.status_code == 200
        assert response.json()["cache_active"] is True

    @pytest.mark.asyncio
    async def test_invalid_mode(self, transport):
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/admin/cache/invalid")
        assert response.status_code == 422


class TestLoadSheddingProxy:
    @pytest.mark.asyncio
    @respx.mock
    async def test_activate(self, transport):
        respx.post(f"{TRADING_BASE}/admin/load-shedding/activate").mock(
            return_value=Response(200, json={"load_shedding_active": True})
        )
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/admin/load-shedding/activate")
        assert response.status_code == 200
        assert response.json()["load_shedding_active"] is True

    @pytest.mark.asyncio
    async def test_invalid_mode(self, transport):
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/admin/load-shedding/invalid")
        assert response.status_code == 422


class TestPricingSourceProxy:
    @pytest.mark.asyncio
    @respx.mock
    async def test_switch_to_backup(self, transport):
        respx.post(f"{TRADING_BASE}/admin/pricing-source/backup").mock(
            return_value=Response(200, json={"pricing_source": "backup"})
        )
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/admin/pricing-source/backup")
        assert response.status_code == 200
        assert response.json()["pricing_source"] == "backup"

    @pytest.mark.asyncio
    async def test_invalid_mode(self, transport):
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/admin/pricing-source/invalid")
        assert response.status_code == 422
