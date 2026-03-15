"""Tests for the TradePulse Agent State Machine."""

import pytest
from state import AgentState, DemoState, RunHistory, VALID_TRANSITIONS


class TestAgentState:
    def test_all_states_have_transitions(self):
        for state in AgentState:
            assert state in VALID_TRANSITIONS, f"Missing transitions for {state}"

    def test_idle_can_transition_to_monitoring(self):
        assert AgentState.MONITORING in VALID_TRANSITIONS[AgentState.IDLE]

    def test_every_state_can_reach_error(self):
        for state in AgentState:
            if state in (AgentState.REJECTED, AgentState.RESOLVED, AgentState.ERROR):
                continue
            assert AgentState.ERROR in VALID_TRANSITIONS[state], f"{state} cannot reach ERROR"


class TestDemoState:
    def test_initial_state_is_idle(self):
        ds = DemoState()
        assert ds.state == AgentState.IDLE

    def test_valid_transition(self):
        ds = DemoState()
        ds.transition(AgentState.MONITORING)
        assert ds.state == AgentState.MONITORING

    def test_invalid_transition_raises(self):
        ds = DemoState()
        with pytest.raises(ValueError, match="Invalid transition"):
            ds.transition(AgentState.RESOLVED)

    def test_transition_records_history(self):
        ds = DemoState()
        ds.transition(AgentState.MONITORING)
        assert len(ds.history) == 1
        assert ds.history[0]["from_state"] == "idle"
        assert ds.history[0]["to_state"] == "monitoring"
        assert "timestamp" in ds.history[0]

    def test_transition_with_data(self):
        ds = DemoState()
        ds.transition(AgentState.MONITORING, data={"p99": 3000})
        assert ds.run_data.get("p99") == 3000

    def test_reset(self):
        ds = DemoState()
        ds.transition(AgentState.MONITORING, data={"key": "value"})
        ds.reset()
        assert ds.state == AgentState.IDLE
        assert ds.history == []
        assert ds.run_data == {}

    def test_to_dict(self):
        ds = DemoState()
        d = ds.to_dict()
        assert d["state"] == "idle"
        assert d["history"] == []
        assert d["run_data"] == {}

    def test_full_happy_path_transitions(self):
        ds = DemoState()
        states = [
            AgentState.MONITORING,
            AgentState.ANOMALY_DETECTED,
            # Short-term track
            AgentState.CACHE_ACTIVATED,
            AgentState.LOAD_SHEDDING_ENABLED,
            AgentState.BACKUP_PRICING_ACTIVE,
            # Long-term track
            AgentState.INCIDENT_CREATED,
            AgentState.INVESTIGATING,
            AgentState.ANALYZING,
            AgentState.FIX_GENERATED,
            AgentState.TICKET_CREATED,
            AgentState.AWAITING_APPROVAL,
            AgentState.APPROVED,
            AgentState.RESOLVED,
            AgentState.IDLE,
        ]
        for state in states:
            ds.transition(state)
        assert ds.state == AgentState.IDLE
        assert len(ds.history) == len(states)

    def test_short_term_track_transitions(self):
        ds = DemoState()
        ds.transition(AgentState.MONITORING)
        ds.transition(AgentState.ANOMALY_DETECTED)
        ds.transition(AgentState.CACHE_ACTIVATED)
        ds.transition(AgentState.LOAD_SHEDDING_ENABLED)
        ds.transition(AgentState.BACKUP_PRICING_ACTIVE)
        ds.transition(AgentState.INCIDENT_CREATED)
        assert ds.state == AgentState.INCIDENT_CREATED

    def test_skip_short_term_track(self):
        """Agent can skip short-term and go directly to incident creation."""
        ds = DemoState()
        ds.transition(AgentState.MONITORING)
        ds.transition(AgentState.ANOMALY_DETECTED)
        ds.transition(AgentState.INCIDENT_CREATED)
        assert ds.state == AgentState.INCIDENT_CREATED


class TestRunHistory:
    def test_record_and_get(self):
        rh = RunHistory()
        rh.record_run(outcome="completed", steps=7, duration_ms=15000.0)
        runs = rh.get_runs()
        assert len(runs) == 1
        assert runs[0]["outcome"] == "completed"
        assert runs[0]["steps"] == 7
        assert runs[0]["duration_ms"] == 15000.0

    def test_runs_are_reversed(self):
        rh = RunHistory()
        rh.record_run(outcome="first", steps=1, duration_ms=100.0)
        rh.record_run(outcome="second", steps=2, duration_ms=200.0)
        runs = rh.get_runs()
        assert runs[0]["outcome"] == "second"
        assert runs[1]["outcome"] == "first"
