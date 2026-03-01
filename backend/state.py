"""
TradePulse Agent State Machine
Manages the demo flow states and transitions.
"""

from enum import Enum
from datetime import datetime, timezone
from typing import Any


class AgentState(str, Enum):
    IDLE = "idle"
    MONITORING = "monitoring"
    ANOMALY_DETECTED = "anomaly_detected"
    INCIDENT_CREATED = "incident_created"
    INVESTIGATING = "investigating"
    ANALYZING = "analyzing"
    FIX_GENERATED = "fix_generated"
    TICKET_CREATED = "ticket_created"
    AWAITING_APPROVAL = "awaiting_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    RESOLVED = "resolved"
    ERROR = "error"


# Valid state transitions — each state maps to its allowed next states
VALID_TRANSITIONS: dict[AgentState, set[AgentState]] = {
    AgentState.IDLE: {AgentState.MONITORING, AgentState.ERROR},
    AgentState.MONITORING: {AgentState.ANOMALY_DETECTED, AgentState.MONITORING, AgentState.ERROR},
    AgentState.ANOMALY_DETECTED: {AgentState.INCIDENT_CREATED, AgentState.ERROR},
    AgentState.INCIDENT_CREATED: {AgentState.INVESTIGATING, AgentState.ERROR},
    AgentState.INVESTIGATING: {AgentState.ANALYZING, AgentState.ERROR},
    AgentState.ANALYZING: {AgentState.FIX_GENERATED, AgentState.ERROR},
    AgentState.FIX_GENERATED: {AgentState.TICKET_CREATED, AgentState.ERROR},
    AgentState.TICKET_CREATED: {AgentState.AWAITING_APPROVAL, AgentState.ERROR},
    AgentState.AWAITING_APPROVAL: {AgentState.APPROVED, AgentState.REJECTED, AgentState.ERROR},
    AgentState.APPROVED: {AgentState.RESOLVED, AgentState.ERROR},
    AgentState.REJECTED: {AgentState.IDLE},
    AgentState.RESOLVED: {AgentState.IDLE},
    AgentState.ERROR: {AgentState.IDLE},
}


class DemoState:
    """Singleton state manager for the demo agent flow."""

    def __init__(self):
        self.state = AgentState.IDLE
        self.history: list[dict[str, Any]] = []
        self.run_data: dict[str, Any] = {}
        self._start_time: float | None = None

    def transition(self, new_state: AgentState, data: dict[str, Any] | None = None) -> None:
        """Transition to a new state. Validates the transition is legal."""
        allowed = VALID_TRANSITIONS.get(self.state, set())
        if new_state not in allowed:
            raise ValueError(
                f"Invalid transition: {self.state.value} → {new_state.value}. "
                f"Allowed: {[s.value for s in allowed]}"
            )

        self.history.append({
            "from_state": self.state.value,
            "to_state": new_state.value,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": data,
        })
        self.state = new_state

        if data:
            self.run_data.update(data)

    def reset(self) -> None:
        """Reset to IDLE state, clearing all run data."""
        self.state = AgentState.IDLE
        self.history = []
        self.run_data = {}
        self._start_time = None

    def to_dict(self) -> dict[str, Any]:
        """Return a serializable snapshot of current state."""
        return {
            "state": self.state.value,
            "history": self.history,
            "run_data": self.run_data,
        }


class RunHistory:
    """Stores history of completed demo runs."""

    def __init__(self):
        self.runs: list[dict[str, Any]] = []

    def record_run(self, outcome: str, steps: int, duration_ms: float, details: dict[str, Any] | None = None) -> None:
        self.runs.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "outcome": outcome,
            "steps": steps,
            "duration_ms": round(duration_ms, 1),
            "details": details or {},
        })

    def get_runs(self) -> list[dict[str, Any]]:
        return list(reversed(self.runs))
