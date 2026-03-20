"""Tests for the TradePulse Agent Tool functions."""

import asyncio
import json
import pytest
import respx
import httpx
from unittest.mock import patch, MagicMock

from agent import (
    tool_detect_latency_anomaly,
    tool_assess_economic_risk,
    tool_create_pagerduty_incident,
    tool_investigate_github_source,
    tool_identify_missing_patterns,
    tool_generate_optimized_code,
    tool_create_jira_ticket,
    tool_resolve_pagerduty_incident,
    tool_activate_price_cache,
    tool_enable_load_shedding,
    tool_switch_to_backup_pricing,
    _update_risk_neutralization,
    TOOLS,
)
from state import DemoState


class TestToolDefinitions:
    def test_all_tools_have_names(self):
        for tool in TOOLS:
            assert "name" in tool
            assert "description" in tool
            assert "input_schema" in tool

    def test_eleven_tools_defined(self):
        assert len(TOOLS) == 11

    def test_tool_names(self):
        names = {t["name"] for t in TOOLS}
        expected = {
            "detect_latency_anomaly",
            "assess_economic_risk",
            "create_pagerduty_incident",
            "investigate_github_source",
            "identify_missing_patterns",
            "generate_optimized_code",
            "create_jira_ticket",
            "resolve_pagerduty_incident",
            "activate_price_cache",
            "enable_load_shedding",
            "switch_to_backup_pricing",
        }
        assert names == expected


class TestDetectLatencyAnomaly:
    @pytest.mark.asyncio
    @respx.mock
    async def test_returns_latency_data_from_prometheus(self):
        respx.get("http://prometheus:9090/api/v1/query").mock(
            return_value=httpx.Response(200, json={
                "status": "success",
                "data": {
                    "resultType": "vector",
                    "result": [{"metric": {}, "value": [1700000000, "3.24"]}],
                },
            })
        )

        result = await tool_detect_latency_anomaly()
        assert result["p99_latency_ms"] == 3240.0
        assert result["breached"] is True
        assert result["threshold_ms"] == 2000
        assert result["source"] == "prometheus"

    @pytest.mark.asyncio
    @respx.mock
    async def test_falls_back_to_trading_service(self):
        # Prometheus fails
        respx.get("http://prometheus:9090/api/v1/query").mock(
            return_value=httpx.Response(500, text="Internal Server Error")
        )
        # Trading service responds
        respx.get("http://trading-service:8001/metrics/summary").mock(
            return_value=httpx.Response(200, json={
                "p99_latency_ms": 3100.0,
                "total_orders": 50,
                "chaos_mode": True,
                "timestamp": "2026-03-01T00:00:00Z",
            })
        )

        result = await tool_detect_latency_anomaly()
        assert result["p99_latency_ms"] == 3100.0
        assert result["breached"] is True
        assert result["source"] == "trading-service"

    @pytest.mark.asyncio
    @respx.mock
    async def test_no_breach_from_prometheus(self):
        respx.get("http://prometheus:9090/api/v1/query").mock(
            return_value=httpx.Response(200, json={
                "status": "success",
                "data": {
                    "resultType": "vector",
                    "result": [{"metric": {}, "value": [1700000000, "0.187"]}],
                },
            })
        )

        result = await tool_detect_latency_anomaly()
        assert result["p99_latency_ms"] == 187.0
        assert result["breached"] is False

    @pytest.mark.asyncio
    @respx.mock
    async def test_handles_both_sources_failing(self):
        respx.get("http://prometheus:9090/api/v1/query").mock(
            return_value=httpx.Response(500, text="error")
        )
        respx.get("http://trading-service:8001/metrics/summary").mock(
            return_value=httpx.Response(500, text="error")
        )

        result = await tool_detect_latency_anomaly()
        assert "error" in result
        assert result["p99_latency_ms"] is None


class TestCreatePagerDutyIncident:
    @pytest.mark.asyncio
    @respx.mock
    async def test_creates_incident(self):
        respx.post("https://events.pagerduty.com/v2/enqueue").mock(
            return_value=httpx.Response(202, json={
                "status": "success",
                "message": "Event processed",
                "dedup_key": "test-dedup-key-123",
            })
        )

        result = await tool_create_pagerduty_incident(
            summary="High latency detected",
            severity="critical",
            latency_ms=3240.0,
        )
        assert result["status"] == "success"
        assert result["dedup_key"] == "test-dedup-key-123"

    @pytest.mark.asyncio
    @respx.mock
    async def test_handles_pd_error(self):
        respx.post("https://events.pagerduty.com/v2/enqueue").mock(
            return_value=httpx.Response(400, json={"status": "invalid", "message": "Bad request"})
        )

        result = await tool_create_pagerduty_incident(
            summary="Test", severity="critical", latency_ms=3000.0,
        )
        assert "error" in result


class TestInvestigateGitHubSource:
    @pytest.mark.asyncio
    @respx.mock
    async def test_retrieves_source(self):
        import base64
        code = "class PricingClient:\n    pass\n"
        encoded = base64.b64encode(code.encode()).decode()

        respx.get(
            "https://api.github.com/repos/florianhoeppner/TradePulse/contents/trading-service/pricing_client.py"
        ).mock(
            return_value=httpx.Response(200, json={
                "content": encoded,
                "sha": "abc123",
                "size": len(code),
            })
        )

        result = await tool_investigate_github_source("trading-service/pricing_client.py")
        assert result["content"] == code
        assert result["line_count"] == 2
        assert result["sha"] == "abc123"

    @pytest.mark.asyncio
    @respx.mock
    async def test_handles_github_404(self):
        respx.get(
            "https://api.github.com/repos/florianhoeppner/TradePulse/contents/nonexistent.py"
        ).mock(
            return_value=httpx.Response(404, json={"message": "Not Found"})
        )

        result = await tool_investigate_github_source("nonexistent.py")
        assert "error" in result


class TestIdentifyMissingPatterns:
    @pytest.mark.asyncio
    async def test_returns_patterns(self):
        result = await tool_identify_missing_patterns(
            source_code="class PricingClient:\n    pass",
            file_name="pricing_client.py",
        )
        assert result["patterns_analyzed"] == 3
        patterns = result["missing_patterns"]
        assert len(patterns) == 3
        names = {p["name"] for p in patterns}
        assert "Retry with Exponential Backoff" in names
        assert "Circuit Breaker" in names
        assert "Timeout Handling" in names


class TestGenerateOptimizedCode:
    @pytest.mark.asyncio
    async def test_returns_optimized_code(self):
        result = await tool_generate_optimized_code(
            source_code="class PricingClient:\n    pass",
            patterns=["retry", "circuit_breaker", "timeout"],
        )
        assert "optimized_code" in result
        assert "CircuitBreaker" in result["optimized_code"]
        assert "retry_with_backoff" in result["optimized_code"]
        assert "changes_summary" in result


class TestCreateJiraTicket:
    @pytest.mark.asyncio
    @respx.mock
    async def test_creates_ticket(self):
        respx.post("https://florianhoeppner.atlassian.net/rest/api/3/issue").mock(
            return_value=httpx.Response(201, json={
                "id": "10001",
                "key": "SCRUM-42",
            })
        )

        result = await tool_create_jira_ticket(
            summary="Resiliency fix: pricing_client.py",
            description_context="Latency spike detected, missing patterns identified.",
            code_block="class PricingClient:\n    pass",
        )
        assert result["key"] == "SCRUM-42"
        assert "url" in result

    @pytest.mark.asyncio
    @respx.mock
    async def test_handles_jira_error(self):
        respx.post("https://florianhoeppner.atlassian.net/rest/api/3/issue").mock(
            return_value=httpx.Response(401, json={"message": "Unauthorized"})
        )

        result = await tool_create_jira_ticket(
            summary="Test", description_context="Test", code_block="pass",
        )
        assert "error" in result


class TestResolvePagerDutyIncident:
    @pytest.mark.asyncio
    @respx.mock
    async def test_resolves_incident(self):
        respx.post("https://events.pagerduty.com/v2/enqueue").mock(
            return_value=httpx.Response(202, json={
                "status": "success",
                "message": "Event processed",
                "dedup_key": "test-key",
            })
        )
        respx.post("https://events.pagerduty.com/v2/change/enqueue").mock(
            return_value=httpx.Response(202, json={"status": "success"})
        )

        result = await tool_resolve_pagerduty_incident(
            dedup_key="test-key",
            resolution_summary="Applied resiliency patterns",
        )
        assert result["resolve_status"] == "success"
        assert result["change_event_status"] == "logged"


class TestActivatePriceCache:
    @pytest.mark.asyncio
    @respx.mock
    async def test_activates_cache(self):
        respx.post("http://trading-service:8001/admin/cache/activate").mock(
            return_value=httpx.Response(200, json={
                "status": "activated",
                "cache_active": True,
                "message": "Price cache activated",
            })
        )
        result = await tool_activate_price_cache()
        assert result["cache_active"] is True
        assert "reasoning" in result
        assert "impact" in result

    @pytest.mark.asyncio
    @respx.mock
    async def test_handles_failure(self):
        respx.post("http://trading-service:8001/admin/cache/activate").mock(
            return_value=httpx.Response(500, text="Internal Server Error")
        )
        result = await tool_activate_price_cache()
        assert "error" in result


class TestEnableLoadShedding:
    @pytest.mark.asyncio
    @respx.mock
    async def test_enables_load_shedding(self):
        respx.post("http://trading-service:8001/admin/load-shedding/activate").mock(
            return_value=httpx.Response(200, json={
                "status": "activated",
                "load_shedding_active": True,
                "max_concurrent": 3,
                "message": "Load shedding active",
            })
        )
        result = await tool_enable_load_shedding()
        assert result["load_shedding_active"] is True
        assert "reasoning" in result
        assert "impact" in result

    @pytest.mark.asyncio
    @respx.mock
    async def test_handles_failure(self):
        respx.post("http://trading-service:8001/admin/load-shedding/activate").mock(
            return_value=httpx.Response(500, text="Internal Server Error")
        )
        result = await tool_enable_load_shedding()
        assert "error" in result


class TestSwitchToBackupPricing:
    @pytest.mark.asyncio
    @respx.mock
    async def test_switches_to_backup(self):
        respx.post("http://trading-service:8001/admin/pricing-source/backup").mock(
            return_value=httpx.Response(200, json={
                "pricing_source": "backup",
                "message": "Switched to backup pricing source",
            })
        )
        result = await tool_switch_to_backup_pricing()
        assert result["pricing_source"] == "backup"
        assert "reasoning" in result
        assert "impact" in result

    @pytest.mark.asyncio
    @respx.mock
    async def test_handles_failure(self):
        respx.post("http://trading-service:8001/admin/pricing-source/backup").mock(
            return_value=httpx.Response(500, text="Internal Server Error")
        )
        result = await tool_switch_to_backup_pricing()
        assert "error" in result


class TestAssessEconomicRisk:
    @pytest.mark.asyncio
    async def test_fallback_when_claude_unavailable(self):
        """When Claude API is unavailable, uses deterministic fallback."""
        ds = DemoState()
        eq = asyncio.Queue()

        with patch("agent.ANTHROPIC_API_KEY", ""):
            result = await tool_assess_economic_risk(
                demo_state=ds,
                event_queue=eq,
                p99_latency_ms=3200,
                threshold_ms=2000,
                estimated_minutes_to_breach=5.0,
            )

        assert "risk_table" in result
        assert result["total_risk_usd_low"] > 0
        assert result["total_risk_usd_high"] > result["total_risk_usd_low"]
        assert result["revenue_at_risk_per_minute"] == 8400 * 12

        # Verify state was updated
        assert ds.total_risk_usd_low == result["total_risk_usd_low"]
        assert ds.total_risk_usd_high == result["total_risk_usd_high"]
        assert ds.economic_risk_assessment is not None

    @pytest.mark.asyncio
    async def test_emits_narration_events(self):
        """Tool emits thinking, action, risk_table, and impact events."""
        ds = DemoState()
        eq = asyncio.Queue()

        with patch("agent.ANTHROPIC_API_KEY", ""):
            await tool_assess_economic_risk(
                demo_state=ds,
                event_queue=eq,
                p99_latency_ms=3200,
                threshold_ms=2000,
            )

        events = []
        while not eq.empty():
            events.append(await eq.get())

        event_types = [e["type"] for e in events]
        assert "economic_narration" in event_types
        assert "risk_table" in event_types

        # Check subtypes
        narrations = [e for e in events if e["type"] == "economic_narration"]
        subtypes = {n["data"]["subtype"] for n in narrations}
        assert "thinking" in subtypes
        assert "action" in subtypes
        assert "impact" in subtypes

    @pytest.mark.asyncio
    async def test_risk_table_structure(self):
        """Risk table has correct structure."""
        ds = DemoState()
        eq = asyncio.Queue()

        with patch("agent.ANTHROPIC_API_KEY", ""):
            result = await tool_assess_economic_risk(
                demo_state=ds,
                event_queue=eq,
                p99_latency_ms=3200,
                threshold_ms=2000,
            )

        table = result["risk_table"]
        assert table["type"] == "risk_table"
        assert len(table["findings"]) == 4
        assert table["total_low"] > 0
        assert table["total_high"] > 0

        finding_names = {f["finding_name"] for f in table["findings"]}
        assert finding_names == {
            "latency_spike",
            "pricing_source_degradation",
            "queue_depth_buildup",
            "cache_miss_rate",
        }

    @pytest.mark.asyncio
    async def test_fallback_when_claude_returns_empty_findings(self):
        """When Claude returns empty findings, uses deterministic fallback."""
        ds = DemoState()
        eq = asyncio.Queue()

        # Mock Claude returning valid JSON but with empty findings
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='{"findings": []}')]

        import anthropic as anthropic_mod
        with patch("agent.ANTHROPIC_API_KEY", "test-key"), \
             patch.object(anthropic_mod, "Anthropic") as mock_anthropic:
            mock_client = MagicMock()
            mock_client.messages.create.return_value = mock_response
            mock_anthropic.return_value = mock_client

            result = await tool_assess_economic_risk(
                demo_state=ds,
                event_queue=eq,
                p99_latency_ms=3200,
                threshold_ms=2000,
                estimated_minutes_to_breach=5.0,
            )

        # Should have used fallback — 4 findings with meaningful risk
        assert len(result["risk_table"]["findings"]) == 4
        assert result["total_risk_usd_low"] > 0
        assert result["total_risk_usd_high"] > 0

    @pytest.mark.asyncio
    async def test_fallback_when_claude_returns_zero_risk(self):
        """When Claude returns all-zero risk findings, uses deterministic fallback."""
        ds = DemoState()
        eq = asyncio.Queue()

        zero_findings = json.dumps({"findings": [
            {"finding_name": "latency_spike", "risk_usd_low": 0, "risk_usd_high": 0, "sla_relevant": True, "rationale": "No risk"},
            {"finding_name": "pricing_source_degradation", "risk_usd_low": 0, "risk_usd_high": 0, "sla_relevant": True, "rationale": "No risk"},
        ]})
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text=zero_findings)]

        import anthropic as anthropic_mod
        with patch("agent.ANTHROPIC_API_KEY", "test-key"), \
             patch.object(anthropic_mod, "Anthropic") as mock_anthropic:
            mock_client = MagicMock()
            mock_client.messages.create.return_value = mock_response
            mock_anthropic.return_value = mock_client

            result = await tool_assess_economic_risk(
                demo_state=ds,
                event_queue=eq,
                p99_latency_ms=3200,
                threshold_ms=2000,
                estimated_minutes_to_breach=5.0,
            )

        assert len(result["risk_table"]["findings"]) == 4
        assert result["total_risk_usd_low"] > 0

    @pytest.mark.asyncio
    async def test_sla_relevant_string_coercion(self):
        """Coerces sla_relevant from string 'true'/'false' to boolean."""
        ds = DemoState()
        eq = asyncio.Queue()

        findings_with_strings = json.dumps({"findings": [
            {"finding_name": "latency_spike", "risk_usd_low": 300000, "risk_usd_high": 600000, "sla_relevant": "true", "rationale": "High risk"},
            {"finding_name": "pricing_source_degradation", "risk_usd_low": 80000, "risk_usd_high": 120000, "sla_relevant": "false", "rationale": "Low risk"},
            {"finding_name": "queue_depth_buildup", "risk_usd_low": 0, "risk_usd_high": 15000, "sla_relevant": "false", "rationale": "Negligible"},
            {"finding_name": "cache_miss_rate", "risk_usd_low": 0, "risk_usd_high": 0, "sla_relevant": "false", "rationale": "None"},
        ]})
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text=findings_with_strings)]

        import anthropic as anthropic_mod
        with patch("agent.ANTHROPIC_API_KEY", "test-key"), \
             patch.object(anthropic_mod, "Anthropic") as mock_anthropic:
            mock_client = MagicMock()
            mock_client.messages.create.return_value = mock_response
            mock_anthropic.return_value = mock_client

            result = await tool_assess_economic_risk(
                demo_state=ds,
                event_queue=eq,
                p99_latency_ms=3200,
                threshold_ms=2000,
                estimated_minutes_to_breach=5.0,
            )

        # Only sla_relevant=True (coerced from "true") should count toward totals
        assert result["total_risk_usd_low"] == 300000
        assert result["total_risk_usd_high"] == 600000

        # Verify coercion happened
        findings = result["risk_table"]["findings"]
        assert findings[0]["sla_relevant"] is True
        assert findings[1]["sla_relevant"] is False

    @pytest.mark.asyncio
    async def test_with_custom_economic_profile(self):
        """Tool uses custom economic profile values."""
        ds = DemoState()
        ds.economic_profile["avg_order_value_usd"] = 20000
        ds.economic_profile["orders_per_minute"] = 50
        eq = asyncio.Queue()

        with patch("agent.ANTHROPIC_API_KEY", ""):
            result = await tool_assess_economic_risk(
                demo_state=ds,
                event_queue=eq,
                p99_latency_ms=3200,
                threshold_ms=2000,
            )

        assert result["revenue_at_risk_per_minute"] == 20000 * 50


class TestRiskNeutralization:
    @pytest.mark.asyncio
    async def test_cache_neutralizes_latency_risk(self):
        """activate_price_cache neutralizes 60% of latency_spike risk."""
        ds = DemoState()
        ds.economic_risk_assessment = {
            "findings": [
                {"finding_name": "latency_spike", "risk_usd_low": 400000, "risk_usd_high": 650000, "sla_relevant": True},
                {"finding_name": "pricing_source_degradation", "risk_usd_low": 80000, "risk_usd_high": 120000, "sla_relevant": True},
            ]
        }
        ds.total_risk_usd_low = 480000
        ds.total_risk_usd_high = 770000
        eq = asyncio.Queue()

        await _update_risk_neutralization("activate_price_cache", ds, eq)

        assert ds.risk_neutralized_usd_low == 240000  # 60% of 400K
        assert ds.risk_neutralized_usd_high == 390000  # 60% of 650K

    @pytest.mark.asyncio
    async def test_backup_pricing_neutralizes_degradation_fully(self):
        """switch_to_backup_pricing neutralizes 100% of pricing_source_degradation."""
        ds = DemoState()
        ds.economic_risk_assessment = {
            "findings": [
                {"finding_name": "pricing_source_degradation", "risk_usd_low": 80000, "risk_usd_high": 120000, "sla_relevant": True},
            ]
        }
        ds.total_risk_usd_low = 80000
        ds.total_risk_usd_high = 120000
        eq = asyncio.Queue()

        await _update_risk_neutralization("switch_to_backup_pricing", ds, eq)

        assert ds.risk_neutralized_usd_low == 80000
        assert ds.risk_neutralized_usd_high == 120000

    @pytest.mark.asyncio
    async def test_emits_risk_update_event(self):
        """Neutralization emits risk_update and economic_narration events."""
        ds = DemoState()
        ds.economic_risk_assessment = {
            "findings": [
                {"finding_name": "latency_spike", "risk_usd_low": 400000, "risk_usd_high": 650000, "sla_relevant": True},
            ]
        }
        ds.total_risk_usd_low = 400000
        ds.total_risk_usd_high = 650000
        eq = asyncio.Queue()

        await _update_risk_neutralization("activate_price_cache", ds, eq)

        events = []
        while not eq.empty():
            events.append(await eq.get())

        types = [e["type"] for e in events]
        assert "risk_update" in types
        assert "economic_narration" in types

        risk_update = next(e for e in events if e["type"] == "risk_update")
        assert risk_update["data"]["neutralized_low"] == 240000
        assert risk_update["data"]["remaining_low"] == 160000

    @pytest.mark.asyncio
    async def test_no_update_without_assessment(self):
        """Does nothing if no risk assessment has been done."""
        ds = DemoState()
        eq = asyncio.Queue()

        await _update_risk_neutralization("activate_price_cache", ds, eq)

        assert eq.empty()
        assert ds.risk_neutralized_usd_low == 0
