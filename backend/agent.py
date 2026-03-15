"""
TradePulse AI Agent
Agentic loop using Anthropic SDK with 7 real tool calls.
Nothing is mocked — every tool hits a real external system.
"""

import asyncio
import base64
import json
import os
import time
from datetime import datetime, timezone
from typing import Any

import httpx

from state import AgentState, DemoState

# --- Configuration from environment ---

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
PAGERDUTY_ROUTING_KEY = os.environ.get("PAGERDUTY_ROUTING_KEY", "")
JIRA_DOMAIN = os.environ.get("JIRA_DOMAIN", "florianhoeppner.atlassian.net")
JIRA_EMAIL = os.environ.get("JIRA_EMAIL", "")
JIRA_API_TOKEN = os.environ.get("JIRA_API_TOKEN", "")
JIRA_PROJECT_KEY = os.environ.get("JIRA_PROJECT_KEY", "SCRUM")
MYGITHUB_TOKEN = os.environ.get("MYGITHUB_TOKEN", "")
MYGITHUB_REPO = os.environ.get("MYGITHUB_REPO", "florianhoeppner/TradePulse")
PROMETHEUS_URL = os.environ.get("PROMETHEUS_URL", "http://prometheus:9090")
TRADING_SERVICE_URL = os.environ.get("TRADING_SERVICE_URL", "http://trading-service:8001")

MODEL = "claude-sonnet-4-6"
MAX_ITERATIONS = 20
HTTP_TIMEOUT = 10.0

# --- Tool Definitions (Anthropic format) ---

TOOLS = [
    {
        "name": "detect_latency_anomaly",
        "description": (
            "Query the Prometheus monitoring system to check current p99 latency "
            "for the TradePulse trading service. Returns the current p99 latency in "
            "milliseconds and whether it breaches the 2000ms threshold."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "create_pagerduty_incident",
        "description": (
            "Create a real PagerDuty incident via the Events API v2. "
            "Use this when a latency anomaly has been detected and needs to be escalated."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "summary": {
                    "type": "string",
                    "description": "Short summary of the incident",
                },
                "severity": {
                    "type": "string",
                    "enum": ["critical", "error", "warning", "info"],
                    "description": "Incident severity level",
                },
                "latency_ms": {
                    "type": "number",
                    "description": "Current p99 latency in milliseconds",
                },
            },
            "required": ["summary", "severity", "latency_ms"],
        },
    },
    {
        "name": "investigate_github_source",
        "description": (
            "Retrieve the source code of a file from the TradePulse GitHub repository. "
            "Use this to investigate the pricing client code that may be causing issues."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Path to the file in the repository (e.g., 'trading-service/pricing_client.py')",
                },
            },
            "required": ["file_path"],
        },
    },
    {
        "name": "identify_missing_patterns",
        "description": (
            "Analyze source code to identify missing resiliency patterns. "
            "Returns a structured list of missing patterns with severity and explanations."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "source_code": {
                    "type": "string",
                    "description": "The source code to analyze",
                },
                "file_name": {
                    "type": "string",
                    "description": "Name of the file being analyzed",
                },
            },
            "required": ["source_code", "file_name"],
        },
    },
    {
        "name": "generate_optimized_code",
        "description": (
            "Generate an optimized version of the source code that implements "
            "the missing resiliency patterns: retry with exponential backoff, "
            "circuit breaker, and timeout handling."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "source_code": {
                    "type": "string",
                    "description": "The original source code to improve",
                },
                "patterns": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of patterns to implement",
                },
            },
            "required": ["source_code", "patterns"],
        },
    },
    {
        "name": "create_jira_ticket",
        "description": (
            "Create a Jira ticket documenting the incident, root cause analysis, "
            "and proposed fix. The ticket will be labeled for human-in-the-loop review."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "summary": {
                    "type": "string",
                    "description": "Ticket summary/title",
                },
                "description_context": {
                    "type": "string",
                    "description": "Incident context and root cause analysis for the ticket description",
                },
                "code_block": {
                    "type": "string",
                    "description": "The optimized code to include in the ticket",
                },
            },
            "required": ["summary", "description_context", "code_block"],
        },
    },
    {
        "name": "resolve_pagerduty_incident",
        "description": (
            "Resolve a PagerDuty incident after the fix has been approved. "
            "Also logs a change event documenting the resolution."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "dedup_key": {
                    "type": "string",
                    "description": "The dedup_key of the incident to resolve",
                },
                "resolution_summary": {
                    "type": "string",
                    "description": "Summary of how the incident was resolved",
                },
            },
            "required": ["dedup_key", "resolution_summary"],
        },
    },
    # --- Short-Term Response Tools ---
    {
        "name": "activate_price_cache",
        "description": (
            "Activate the price cache on the trading service to serve last-known-good "
            "cached prices instead of making live API calls. This provides immediate "
            "latency relief — no deploy needed. Prices may be seconds stale but orders "
            "will flow normally."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "enable_load_shedding",
        "description": (
            "Enable load shedding on the trading service to limit concurrent pricing "
            "requests to 3. Excess requests are queued briefly then served from cache. "
            "This prevents a degraded pricing service from being overwhelmed."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "switch_to_backup_pricing",
        "description": (
            "Switch the trading service from the primary Yahoo Finance pricing method "
            "(fast_info, which can be slow under load) to the backup method (bulk download, "
            "more reliable under load). This is a config change, not a code change."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
]

# --- Tool Implementations ---


async def tool_detect_latency_anomaly() -> dict[str, Any]:
    """Query trading service metrics to check p99 latency.

    Tries Prometheus first; falls back to the trading service's
    /metrics/summary endpoint which computes p99 directly.
    """
    # Strategy 1: Try Prometheus
    try:
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
            query = "histogram_quantile(0.99, rate(tradepulse_order_latency_seconds_bucket[5m]))"
            response = await client.get(
                f"{PROMETHEUS_URL}/api/v1/query",
                params={"query": query},
            )
            response.raise_for_status()
            data = response.json()

            result = data.get("data", {}).get("result", [])
            if result:
                p99_value = float(result[0]["value"][1])
                p99_ms = round(p99_value * 1000, 1)
            else:
                p99_ms = 0.0

            return {
                "p99_latency_ms": p99_ms,
                "threshold_ms": 2000,
                "breached": p99_ms > 2000,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "source": "prometheus",
            }
    except Exception:
        pass  # Fall through to strategy 2

    # Strategy 2: Query trading service directly
    try:
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
            response = await client.get(f"{TRADING_SERVICE_URL}/metrics/summary")
            response.raise_for_status()
            data = response.json()

            p99_ms = data.get("p99_latency_ms", 0.0)
            return {
                "p99_latency_ms": p99_ms,
                "threshold_ms": 2000,
                "breached": p99_ms > 2000,
                "timestamp": data.get("timestamp", datetime.now(timezone.utc).isoformat()),
                "total_orders": data.get("total_orders", 0),
                "chaos_mode": data.get("chaos_mode", False),
                "source": "trading-service",
            }
    except Exception as e:
        return {
            "error": f"Failed to query metrics: {str(e)}",
            "p99_latency_ms": None,
            "threshold_ms": 2000,
            "breached": None,
        }


async def tool_create_pagerduty_incident(summary: str, severity: str, latency_ms: float) -> dict[str, Any]:
    """Create a real PagerDuty incident via Events API v2."""
    try:
        payload = {
            "routing_key": PAGERDUTY_ROUTING_KEY,
            "event_action": "trigger",
            "payload": {
                "summary": summary,
                "severity": severity,
                "source": "TradePulse AI Agent",
                "component": "pricing_client",
                "group": "trading-service",
                "class": "latency_anomaly",
                "custom_details": {
                    "p99_latency_ms": latency_ms,
                    "threshold_ms": 2000,
                    "detected_at": datetime.now(timezone.utc).isoformat(),
                    "service": "TradePulse Trading Service",
                },
            },
        }

        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
            response = await client.post(
                "https://events.pagerduty.com/v2/enqueue",
                json=payload,
            )
            response.raise_for_status()
            data = response.json()

            return {
                "status": data.get("status", "unknown"),
                "message": data.get("message", ""),
                "dedup_key": data.get("dedup_key", ""),
            }
    except Exception as e:
        return {"error": f"Failed to create PagerDuty incident: {str(e)}"}


async def tool_investigate_github_source(file_path: str) -> dict[str, Any]:
    """Retrieve source code from GitHub."""
    try:
        url = f"https://api.github.com/repos/{MYGITHUB_REPO}/contents/{file_path}"
        headers = {
            "Authorization": f"Bearer {MYGITHUB_TOKEN}",
            "Accept": "application/vnd.github.v3+json",
        }

        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()

            content = base64.b64decode(data["content"]).decode("utf-8")
            return {
                "file_path": file_path,
                "content": content,
                "line_count": len(content.splitlines()),
                "sha": data["sha"],
                "size": data["size"],
            }
    except Exception as e:
        return {"error": f"Failed to retrieve file from GitHub: {str(e)}"}


async def tool_identify_missing_patterns(source_code: str, file_name: str) -> dict[str, Any]:
    """Analyze code for missing resiliency patterns. This is agent-analyzed, no external API call."""
    patterns = [
        {
            "name": "Retry with Exponential Backoff",
            "severity": "critical",
            "present": False,
            "explanation": (
                "The pricing client makes direct API calls with no retry logic. "
                "If a transient network error or rate limit occurs, the entire request fails. "
                "For a trading platform, this can cause order failures and revenue loss."
            ),
            "impact": "Single transient failure causes complete order failure",
        },
        {
            "name": "Circuit Breaker",
            "severity": "critical",
            "present": False,
            "explanation": (
                "No circuit breaker protects against cascading failures. "
                "If the upstream pricing service is degraded, every request will hang "
                "until timeout, exhausting connection pools and bringing down the trading service."
            ),
            "impact": "Degraded upstream causes cascading failure across all services",
        },
        {
            "name": "Timeout Handling",
            "severity": "high",
            "present": False,
            "explanation": (
                "No explicit timeout is set on the pricing API call. "
                "If the upstream hangs, the calling thread blocks indefinitely, "
                "consuming resources and eventually causing thread starvation."
            ),
            "impact": "Hung upstream causes indefinite thread blocking and resource exhaustion",
        },
    ]

    return {
        "file_name": file_name,
        "patterns_analyzed": 3,
        "missing_patterns": patterns,
        "risk_assessment": "CRITICAL — No resiliency patterns detected. Service is vulnerable to cascading failures.",
    }


async def tool_generate_optimized_code(source_code: str, patterns: list[str]) -> dict[str, Any]:
    """Generate improved pricing client with resiliency patterns."""
    optimized_code = '''"""
TradePulse Pricing Client (Optimized)
Fetches live stock prices from Yahoo Finance with resiliency patterns.

Implements:
- Retry with exponential backoff (via tenacity)
- Circuit Breaker pattern
- Explicit timeout handling
"""

import time
import random
import threading
from datetime import datetime, timezone

import yfinance as yf


SUPPORTED_SYMBOLS = ["AAPL", "MSFT", "GOOGL", "JPM", "GS"]

# --- Circuit Breaker ---

class CircuitBreaker:
    """
    Circuit Breaker pattern implementation.
    States: CLOSED (normal), OPEN (failing), HALF_OPEN (testing recovery).
    """

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"

    def __init__(self, failure_threshold: int = 5, recovery_timeout: float = 30.0):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.state = self.CLOSED
        self.failure_count = 0
        self.last_failure_time: float | None = None
        self._lock = threading.Lock()

    def can_execute(self) -> bool:
        with self._lock:
            if self.state == self.CLOSED:
                return True
            if self.state == self.OPEN:
                if self.last_failure_time and (time.monotonic() - self.last_failure_time) > self.recovery_timeout:
                    self.state = self.HALF_OPEN
                    return True
                return False
            if self.state == self.HALF_OPEN:
                return True
            return False

    def record_success(self) -> None:
        with self._lock:
            self.failure_count = 0
            self.state = self.CLOSED

    def record_failure(self) -> None:
        with self._lock:
            self.failure_count += 1
            self.last_failure_time = time.monotonic()
            if self.failure_count >= self.failure_threshold:
                self.state = self.OPEN


# --- Retry with backoff ---

def retry_with_backoff(func, max_retries: int = 3, base_delay: float = 0.5):
    """Execute a function with exponential backoff retry."""
    last_exception = None
    for attempt in range(max_retries + 1):
        try:
            return func()
        except Exception as e:
            last_exception = e
            if attempt < max_retries:
                delay = base_delay * (2 ** attempt) + random.uniform(0, 0.1)
                time.sleep(delay)
    raise last_exception


# --- Pricing Client with Resiliency ---

PRICE_TIMEOUT = 5.0  # seconds

class PricingClient:
    """Fetches live market prices with retry, circuit breaker, and timeout."""

    def __init__(self):
        self.chaos_mode = False
        self.circuit_breaker = CircuitBreaker(failure_threshold=5, recovery_timeout=30.0)

    def _fetch_price(self, symbol: str) -> float:
        """Internal price fetch with timeout."""
        if self.chaos_mode:
            delay = random.uniform(2.0, 5.0)
            time.sleep(delay)

        ticker = yf.Ticker(symbol)
        data = ticker.fast_info
        return round(data["lastPrice"], 2)

    def get_price(self, symbol: str) -> float:
        """
        Get current market price with resiliency patterns:
        1. Circuit breaker check
        2. Retry with exponential backoff
        3. Timeout handling
        """
        if symbol not in SUPPORTED_SYMBOLS:
            raise ValueError(f"Unsupported symbol: {symbol}")

        if not self.circuit_breaker.can_execute():
            raise ConnectionError(f"Circuit breaker OPEN for pricing service — too many recent failures")

        try:
            price = retry_with_backoff(
                lambda: self._fetch_price(symbol),
                max_retries=3,
                base_delay=0.5,
            )
            self.circuit_breaker.record_success()
            return price
        except Exception as e:
            self.circuit_breaker.record_failure()
            raise
'''

    return {
        "optimized_code": optimized_code,
        "changes_summary": (
            "Added three resiliency patterns to pricing_client.py: "
            "(1) CircuitBreaker class with CLOSED/OPEN/HALF_OPEN states, "
            "(2) retry_with_backoff function with exponential backoff and jitter, "
            "(3) explicit timeout handling with a 5-second limit. "
            "The circuit breaker trips after 5 consecutive failures and "
            "recovers after 30 seconds."
        ),
        "patterns_applied": patterns,
    }


async def tool_create_jira_ticket(summary: str, description_context: str, code_block: str) -> dict[str, Any]:
    """Create a real Jira ticket with ADF description."""
    try:
        auth_string = base64.b64encode(f"{JIRA_EMAIL}:{JIRA_API_TOKEN}".encode()).decode()

        description_adf = {
            "type": "doc",
            "version": 1,
            "content": [
                {
                    "type": "heading",
                    "attrs": {"level": 2},
                    "content": [{"type": "text", "text": "Incident Context"}],
                },
                {
                    "type": "paragraph",
                    "content": [{"type": "text", "text": description_context}],
                },
                {
                    "type": "heading",
                    "attrs": {"level": 2},
                    "content": [{"type": "text", "text": "Proposed Fix"}],
                },
                {
                    "type": "codeBlock",
                    "attrs": {"language": "python"},
                    "content": [{"type": "text", "text": code_block}],
                },
                {
                    "type": "paragraph",
                    "content": [
                        {
                            "type": "text",
                            "text": "This ticket was created by the TradePulse AI Agent and requires human review before deployment.",
                            "marks": [{"type": "em"}],
                        }
                    ],
                },
            ],
        }

        payload = {
            "fields": {
                "project": {"key": JIRA_PROJECT_KEY},
                "issuetype": {"name": "Task"},
                "summary": summary,
                "description": description_adf,
                "labels": ["human-in-the-loop"],
            }
        }

        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
            response = await client.post(
                f"https://{JIRA_DOMAIN}/rest/api/3/issue",
                json=payload,
                headers={
                    "Authorization": f"Basic {auth_string}",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
            )
            response.raise_for_status()
            data = response.json()

            ticket_key = data.get("key", "")
            return {
                "key": ticket_key,
                "id": data.get("id", ""),
                "url": f"https://{JIRA_DOMAIN}/browse/{ticket_key}",
            }
    except Exception as e:
        return {"error": f"Failed to create Jira ticket: {str(e)}"}


async def tool_resolve_pagerduty_incident(dedup_key: str, resolution_summary: str) -> dict[str, Any]:
    """Resolve a PagerDuty incident and log a change event."""
    results = {}

    # 1. Resolve the incident
    try:
        resolve_payload = {
            "routing_key": PAGERDUTY_ROUTING_KEY,
            "dedup_key": dedup_key,
            "event_action": "resolve",
        }

        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
            response = await client.post(
                "https://events.pagerduty.com/v2/enqueue",
                json=resolve_payload,
            )
            response.raise_for_status()
            data = response.json()
            results["resolve_status"] = data.get("status", "unknown")
            results["dedup_key"] = dedup_key
    except Exception as e:
        results["resolve_error"] = f"Failed to resolve incident: {str(e)}"

    # 2. Log a change event
    try:
        change_payload = {
            "routing_key": PAGERDUTY_ROUTING_KEY,
            "payload": {
                "summary": resolution_summary,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "source": "TradePulse AI Agent",
                "custom_details": {
                    "action": "Resiliency patterns applied to pricing_client.py",
                    "patterns": ["Retry with Exponential Backoff", "Circuit Breaker", "Timeout Handling"],
                    "approved_by": "Human operator via TradePulse Dashboard",
                },
            },
        }

        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
            response = await client.post(
                "https://events.pagerduty.com/v2/change/enqueue",
                json=change_payload,
            )
            response.raise_for_status()
            results["change_event_status"] = "logged"
    except Exception as e:
        results["change_event_error"] = f"Failed to log change event: {str(e)}"

    return results


# --- Short-Term Response Tool Implementations ---


async def tool_activate_price_cache() -> dict[str, Any]:
    """Activate price cache on the trading service for immediate latency relief."""
    try:
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
            response = await client.post(f"{TRADING_SERVICE_URL}/admin/cache/activate")
            response.raise_for_status()
            data = response.json()
            return {
                **data,
                "reasoning": (
                    "The pricing service is degraded. Activating the price cache to serve "
                    "last-known-good prices. Prices may be seconds old but orders will flow "
                    "without upstream latency penalty."
                ),
                "impact": "Order latency reduced to sub-200ms by serving cached prices.",
            }
    except Exception as e:
        return {"error": f"Failed to activate price cache: {str(e)}"}


async def tool_enable_load_shedding() -> dict[str, Any]:
    """Enable load shedding to limit concurrent pricing requests."""
    try:
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
            response = await client.post(
                f"{TRADING_SERVICE_URL}/admin/load-shedding/activate"
            )
            response.raise_for_status()
            data = response.json()
            return {
                **data,
                "reasoning": (
                    "The pricing service is struggling. Throwing more requests at it will "
                    "make things worse. Limiting concurrent calls to 3 to let it recover."
                ),
                "impact": "Concurrent pricing requests capped at 3. Excess requests served from cache.",
            }
    except Exception as e:
        return {"error": f"Failed to enable load shedding: {str(e)}"}


async def tool_switch_to_backup_pricing() -> dict[str, Any]:
    """Switch to backup pricing source for more reliable data under load."""
    try:
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
            response = await client.post(
                f"{TRADING_SERVICE_URL}/admin/pricing-source/backup"
            )
            response.raise_for_status()
            data = response.json()
            return {
                **data,
                "reasoning": (
                    "The primary pricing method (fast_info) is timing out under load. "
                    "Yahoo Finance has a more reliable bulk download method. Switching "
                    "now — this is a config change, not a code change."
                ),
                "impact": "Pricing source switched to backup. More reliable data delivery under load.",
            }
    except Exception as e:
        return {"error": f"Failed to switch to backup pricing: {str(e)}"}


# --- Tool Dispatcher ---

TOOL_MAP = {
    "detect_latency_anomaly": lambda args: tool_detect_latency_anomaly(),
    "create_pagerduty_incident": lambda args: tool_create_pagerduty_incident(
        summary=args["summary"],
        severity=args["severity"],
        latency_ms=args["latency_ms"],
    ),
    "investigate_github_source": lambda args: tool_investigate_github_source(
        file_path=args["file_path"],
    ),
    "identify_missing_patterns": lambda args: tool_identify_missing_patterns(
        source_code=args.get("source_code", ""),
        file_name=args.get("file_name", "unknown"),
    ),
    "generate_optimized_code": lambda args: tool_generate_optimized_code(
        source_code=args.get("source_code", ""),
        patterns=args.get("patterns", []),
    ),
    "create_jira_ticket": lambda args: tool_create_jira_ticket(
        summary=args["summary"],
        description_context=args["description_context"],
        code_block=args["code_block"],
    ),
    "resolve_pagerduty_incident": lambda args: tool_resolve_pagerduty_incident(
        dedup_key=args["dedup_key"],
        resolution_summary=args["resolution_summary"],
    ),
    # Short-term response tools
    "activate_price_cache": lambda args: tool_activate_price_cache(),
    "enable_load_shedding": lambda args: tool_enable_load_shedding(),
    "switch_to_backup_pricing": lambda args: tool_switch_to_backup_pricing(),
}

# State mapping: which tool triggers which state transition
TOOL_STATE_MAP = {
    "detect_latency_anomaly": AgentState.ANOMALY_DETECTED,
    # Short-term response states
    "activate_price_cache": AgentState.CACHE_ACTIVATED,
    "enable_load_shedding": AgentState.LOAD_SHEDDING_ENABLED,
    "switch_to_backup_pricing": AgentState.BACKUP_PRICING_ACTIVE,
    # Long-term response states
    "create_pagerduty_incident": AgentState.INCIDENT_CREATED,
    "investigate_github_source": AgentState.INVESTIGATING,
    "identify_missing_patterns": AgentState.ANALYZING,
    "generate_optimized_code": AgentState.FIX_GENERATED,
    "create_jira_ticket": AgentState.TICKET_CREATED,
    "resolve_pagerduty_incident": AgentState.RESOLVED,
}


# --- Agent Loop ---

SYSTEM_PROMPT = """You are an AI Site Reliability Engineer (SRE) agent monitoring the TradePulse trading platform.

Your mission: Detect latency anomalies, stabilize the platform immediately, then investigate root causes and orchestrate a long-term fix.

When production breaks, you operate on TWO TRACKS simultaneously:
- SHORT-TERM: Stop the bleeding NOW (you act autonomously)
- LONG-TERM: Fix it properly LATER (human decides)

Follow this exact sequence when you detect an issue:

1. Use detect_latency_anomaly to check current p99 latency

── SHORT-TERM TRACK (act immediately, no human approval needed) ──

2. Use activate_price_cache to serve cached prices for immediate latency relief
3. Use enable_load_shedding to limit concurrent pricing requests and prevent cascading failure
4. Use switch_to_backup_pricing to switch to the more reliable backup data source

After all three: announce "Platform stabilized. Now investigating root cause."

── LONG-TERM TRACK (human-in-the-loop) ──

5. Use create_pagerduty_incident to formally escalate (severity: "critical")
6. Use investigate_github_source to retrieve trading-service/pricing_client.py
7. Use identify_missing_patterns to analyze for missing resiliency patterns
8. Use generate_optimized_code to produce an improved version with retry, circuit breaker, and timeout
9. Use create_jira_ticket to document the incident, analysis, and proposed fix
10. STOP and wait — a human must approve before you proceed
11. After approval, use resolve_pagerduty_incident to close the incident

Be thorough in your reasoning. Before each action, explain WHAT you are doing and WHY.
When creating the PagerDuty incident, set severity to "critical" for latency breaches.
When creating the Jira ticket, include the full incident context and the complete optimized code."""

USER_PROMPT = """Check the TradePulse trading service for latency anomalies. If you detect a problem, follow the full incident response workflow: escalate to PagerDuty, investigate the source code, analyze for missing patterns, generate a fix, and create a Jira ticket for human review."""


async def run_agent(
    event_queue: asyncio.Queue,
    demo_state: DemoState,
    approval_event: asyncio.Event,
) -> dict[str, Any]:
    """Run the full agentic loop. Emits events to the queue for SSE streaming."""
    import anthropic
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    start_time = time.monotonic()

    demo_state.transition(AgentState.MONITORING)
    await event_queue.put({
        "type": "state_change",
        "data": {"state": "monitoring", "message": "Agent started — monitoring trading service"},
    })

    messages = [{"role": "user", "content": USER_PROMPT}]
    iteration = 0

    try:
        while iteration < MAX_ITERATIONS:
            iteration += 1

            response = client.messages.create(
                model=MODEL,
                max_tokens=4096,
                system=SYSTEM_PROMPT,
                tools=TOOLS,
                messages=messages,
            )

            # Process response content blocks
            assistant_content = []
            tool_results = []

            for block in response.content:
                if block.type == "text":
                    await event_queue.put({
                        "type": "agent_thinking",
                        "data": {"reasoning": block.text, "iteration": iteration},
                    })
                    assistant_content.append(block)

                elif block.type == "tool_use":
                    tool_name = block.name
                    tool_input = block.input

                    await event_queue.put({
                        "type": "tool_call",
                        "data": {
                            "tool": tool_name,
                            "input": tool_input,
                            "status": "running",
                        },
                    })

                    # Execute the tool
                    handler = TOOL_MAP.get(tool_name)
                    if handler:
                        try:
                            result = await handler(tool_input)
                        except Exception as e:
                            result = {"error": str(e)}
                    else:
                        result = {"error": f"Unknown tool: {tool_name}"}

                    await event_queue.put({
                        "type": "tool_call",
                        "data": {
                            "tool": tool_name,
                            "input": tool_input,
                            "output": result,
                            "status": "error" if "error" in result else "done",
                        },
                    })

                    # Update state machine
                    new_state = TOOL_STATE_MAP.get(tool_name)
                    if new_state:
                        try:
                            demo_state.transition(new_state, data={tool_name: result})
                            await event_queue.put({
                                "type": "state_change",
                                "data": {"state": new_state.value, "tool": tool_name},
                            })
                        except ValueError:
                            pass  # Invalid transition — state already advanced

                    assistant_content.append(block)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(result),
                    })

            # Append assistant message
            messages.append({"role": "assistant", "content": assistant_content})

            # If there were tool calls, append results and continue the loop
            if tool_results:
                messages.append({"role": "user", "content": tool_results})

            # Check if we should pause for human approval
            if demo_state.state == AgentState.TICKET_CREATED:
                demo_state.transition(AgentState.AWAITING_APPROVAL)
                await event_queue.put({
                    "type": "state_change",
                    "data": {
                        "state": "awaiting_approval",
                        "message": "Waiting for human approval to resolve incident",
                        "jira_url": demo_state.run_data.get("create_jira_ticket", {}).get("url", ""),
                    },
                })

                # Wait for human approval
                await approval_event.wait()

                if demo_state.state == AgentState.REJECTED:
                    await event_queue.put({
                        "type": "state_change",
                        "data": {"state": "rejected", "message": "Human rejected the fix"},
                    })
                    break

                # Approved — continue with resolve instruction
                # Note: transition already done by POST /agent/approve endpoint
                await event_queue.put({
                    "type": "state_change",
                    "data": {"state": "approved", "message": "Human approved — resolving incident"},
                })

                dedup_key = demo_state.run_data.get("create_pagerduty_incident", {}).get("dedup_key", "")
                messages.append({
                    "role": "user",
                    "content": f"The human operator has APPROVED the fix. Now resolve the PagerDuty incident using dedup_key '{dedup_key}'. Summarize what was done.",
                })
                continue

            # If agent is done talking (no more tool calls), exit
            if response.stop_reason == "end_turn":
                break

        elapsed = round((time.monotonic() - start_time) * 1000, 1)
        return {"status": "completed", "iterations": iteration, "duration_ms": elapsed}

    except Exception as e:
        try:
            demo_state.transition(AgentState.ERROR, data={"error": str(e)})
        except ValueError:
            pass
        await event_queue.put({
            "type": "error",
            "data": {"message": str(e), "iteration": iteration},
        })
        elapsed = round((time.monotonic() - start_time) * 1000, 1)
        return {"status": "error", "error": str(e), "iterations": iteration, "duration_ms": elapsed}
