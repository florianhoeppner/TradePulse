"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { BACKEND_URL } from "./api";
import type {
  AgentState,
  TimelineStepData,
  ConsoleEntry,
  MetricsDataPoint,
  RiskTableData,
  RiskNeutralized,
} from "./types";

const SHORT_TERM_STATES = new Set([
  "cache_activated",
  "load_shedding_enabled",
  "backup_pricing_active",
]);

const STEP_DEFINITIONS: Record<string, { title: string; subtitle: string }> = {
  monitoring: {
    title: "Monitoring",
    subtitle: "Checking TradePulse p99 latency",
  },
  anomaly_detected: {
    title: "Anomaly Detected",
    subtitle: "p99 latency threshold breached",
  },
  cache_activated: {
    title: "Price Cache Activated",
    subtitle: "Serving cached prices to reduce latency",
  },
  load_shedding_enabled: {
    title: "Load Shedding Enabled",
    subtitle: "Limiting concurrent pricing requests",
  },
  backup_pricing_active: {
    title: "Backup Pricing Active",
    subtitle: "Switched to reliable backup data source",
  },
  incident_created: {
    title: "PagerDuty",
    subtitle: "Incident created",
  },
  investigating: {
    title: "GitHub Investigation",
    subtitle: "Retrieving pricing_client.py",
  },
  analyzing: {
    title: "Code Analysis",
    subtitle: "Identifying missing patterns",
  },
  fix_generated: {
    title: "Fix Generated",
    subtitle: "Optimized code ready",
  },
  ticket_created: {
    title: "Jira Ticket",
    subtitle: "Ticket created for review",
  },
  awaiting_approval: {
    title: "Human Approval",
    subtitle: "Waiting for approval",
  },
  approved: {
    title: "Approved",
    subtitle: "Human approved the fix",
  },
  resolved: {
    title: "Resolved",
    subtitle: "Incident closed, change logged",
  },
  rejected: {
    title: "Rejected",
    subtitle: "Human rejected the fix",
  },
  error: {
    title: "Error",
    subtitle: "An error occurred",
  },
};

export function useAgentStream() {
  const [currentState, setCurrentState] = useState<AgentState>("idle");
  const [steps, setSteps] = useState<TimelineStepData[]>([]);
  const [consoleLog, setConsoleLog] = useState<ConsoleEntry[]>([]);
  const [metrics, setMetrics] = useState<MetricsDataPoint[]>([]);
  const [sseConnected, setSseConnected] = useState(false);
  const [backendReachable, setBackendReachable] = useState(false);
  const [jiraUrl, setJiraUrl] = useState<string>("");
  const [originalCode, setOriginalCode] = useState<string>("");
  const [optimizedCode, setOptimizedCode] = useState<string>("");
  const [riskTable, setRiskTable] = useState<RiskTableData | null>(null);
  const [riskNeutralized, setRiskNeutralized] = useState<RiskNeutralized | null>(null);
  const eventSourceRef = useRef<EventSource | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  // Derive connection status: connected if SSE works OR backend is reachable via HTTP
  const isConnected = sseConnected || backendReachable;

  // Periodic health check as fallback for connection status
  useEffect(() => {
    const checkHealth = async () => {
      try {
        const res = await fetch(`${BACKEND_URL}/health`, { method: "GET" });
        setBackendReachable(res.ok);
      } catch {
        setBackendReachable(false);
      }
    };
    checkHealth();
    const intervalId = setInterval(checkHealth, 10_000);
    return () => clearInterval(intervalId);
  }, []);

  // Poll live p99 latency from trading service so the chart/gauge
  // shows data even before the agent runs
  useEffect(() => {
    let cancelled = false;
    const poll = async () => {
      try {
        const res = await fetch(`${BACKEND_URL}/admin/metrics-summary`, {
          headers: { "Content-Type": "application/json" },
        });
        if (!cancelled && res.ok) {
          const data = await res.json();
          const p99 = data.p99_latency_ms;
          if (p99 != null && typeof p99 === "number") {
            setMetrics((prev) => [
              ...prev,
              { time: Date.now(), value: p99 },
            ]);
          }
        }
      } catch {
        // Silently ignore — health check handles connectivity
      }
    };
    poll();
    const intervalId = setInterval(poll, 5000);
    return () => {
      cancelled = true;
      clearInterval(intervalId);
    };
  }, []);

  const addConsoleEntry = useCallback(
    (type: ConsoleEntry["type"], data: Record<string, unknown>) => {
      setConsoleLog((prev) => [
        ...prev,
        {
          id: `${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
          type,
          timestamp: new Date().toISOString(),
          data,
        },
      ]);
    },
    []
  );

  const updateSteps = useCallback(
    (state: AgentState, extraData?: Record<string, unknown>) => {
      const def = STEP_DEFINITIONS[state];
      if (!def) return;

      setSteps((prev) => {
        const updated = prev.map((step) => {
          if (step.status === "active") {
            return { ...step, status: "done" as const };
          }
          return step;
        });

        const existing = updated.find((s) => s.id === state);
        if (existing) {
          return updated.map((s) =>
            s.id === state
              ? { ...s, status: "active" as const, data: extraData }
              : s
          );
        }

        return [
          ...updated,
          {
            id: state,
            status: "active" as const,
            title: def.title,
            subtitle: def.subtitle,
            data: extraData,
            timestamp: new Date().toISOString(),
            track: SHORT_TERM_STATES.has(state)
              ? ("short-term" as const)
              : ("long-term" as const),
          },
        ];
      });
    },
    []
  );

  const connect = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
    }

    const es = new EventSource(`${BACKEND_URL}/events`);
    eventSourceRef.current = es;

    es.onopen = () => {
      setSseConnected(true);
    };

    es.addEventListener("state_change", (event) => {
      const data = JSON.parse(event.data);
      const state = data.state as AgentState;
      setCurrentState(state);
      updateSteps(state, data);
      addConsoleEntry("state_change", data);

      if (data.jira_url) {
        setJiraUrl(data.jira_url);
      }

      if (state === "idle") {
        setSteps((prev) =>
          prev.map((s) =>
            s.status === "active" ? { ...s, status: "done" as const } : s
          )
        );
      }
    });

    es.addEventListener("agent_thinking", (event) => {
      const data = JSON.parse(event.data);
      addConsoleEntry("thinking", data);
    });

    es.addEventListener("tool_call", (event) => {
      const data = JSON.parse(event.data);
      addConsoleEntry("tool_call", data);

      if (
        data.tool === "investigate_github_source" &&
        data.output?.content
      ) {
        setOriginalCode(data.output.content as string);
      }
      if (
        data.tool === "generate_optimized_code" &&
        data.output?.optimized_code
      ) {
        setOptimizedCode(data.output.optimized_code as string);
      }

      if (data.output?.p99_latency_ms != null) {
        setMetrics((prev) => [
          ...prev,
          {
            time: Date.now(),
            value: data.output.p99_latency_ms as number,
          },
        ]);
      }
    });

    // Economic risk events
    es.addEventListener("risk_table", (event) => {
      const data = JSON.parse(event.data) as RiskTableData;
      setRiskTable(data);
      addConsoleEntry("tool_call", { tool: "assess_economic_risk", output: data, status: "done" });
    });

    es.addEventListener("risk_update", (event) => {
      const data = JSON.parse(event.data) as RiskNeutralized;
      setRiskNeutralized(data);
    });

    es.addEventListener("economic_narration", (event) => {
      const data = JSON.parse(event.data);
      addConsoleEntry("thinking", { reasoning: data.message, subtype: data.subtype });
    });

    es.addEventListener("error", (event) => {
      try {
        const data = JSON.parse((event as MessageEvent).data);
        addConsoleEntry("error", data);
      } catch {
        // SSE connection error, not a data event
      }
    });

    es.addEventListener("keepalive", () => {
      // Just confirms connection is alive
    });

    es.onerror = () => {
      setSseConnected(false);
      es.close();
      // Reconnect after 2s
      reconnectTimeoutRef.current = setTimeout(() => {
        connect();
      }, 2000);
    };
  }, [addConsoleEntry, updateSteps]);

  useEffect(() => {
    connect();
    return () => {
      eventSourceRef.current?.close();
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
    };
  }, [connect]);

  const resetStream = useCallback(() => {
    setSteps([]);
    setConsoleLog([]);
    setMetrics([]);
    setCurrentState("idle");
    setJiraUrl("");
    setOriginalCode("");
    setOptimizedCode("");
    setRiskTable(null);
    setRiskNeutralized(null);
  }, []);

  return {
    currentState,
    steps,
    consoleLog,
    metrics,
    isConnected,
    jiraUrl,
    originalCode,
    optimizedCode,
    riskTable,
    riskNeutralized,
    resetStream,
  };
}
