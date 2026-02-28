"""Tests for the TradePulse Backend API endpoints."""

import pytest
from httpx import AsyncClient, ASGITransport

from main import app, demo_state


@pytest.fixture(autouse=True)
def reset_state():
    """Reset demo state before each test."""
    demo_state.reset()
    yield
    demo_state.reset()


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
    assert data["agent_state"] == "idle"
    assert "timestamp" in data


@pytest.mark.asyncio
async def test_agent_status(transport):
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/agent/status")
    assert response.status_code == 200
    data = response.json()
    assert data["state"] == "idle"
    assert data["history"] == []
    assert data["run_data"] == {}


@pytest.mark.asyncio
async def test_admin_config(transport):
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/admin/config")
    assert response.status_code == 200
    data = response.json()
    assert "config" in data
    assert "ANTHROPIC_API_KEY" in data["config"]
    assert "configured" in data["config"]["ANTHROPIC_API_KEY"]


@pytest.mark.asyncio
async def test_admin_history_empty(transport):
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/admin/history")
    assert response.status_code == 200
    data = response.json()
    assert data["runs"] == []


@pytest.mark.asyncio
async def test_approve_without_awaiting(transport):
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/agent/approve")
    assert response.status_code == 200
    data = response.json()
    assert "error" in data


@pytest.mark.asyncio
async def test_reject_without_awaiting(transport):
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/agent/reject")
    assert response.status_code == 200
    data = response.json()
    assert "error" in data
