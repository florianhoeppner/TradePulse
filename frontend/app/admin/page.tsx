"use client";

import { useState, useEffect, useCallback } from "react";
import { useAgentStream } from "@/lib/useAgentStream";
import {
  startAgent,
  resetDemo,
  toggleChaos,
  getConfig,
  getHistory,
} from "@/lib/api";
import Navbar from "@/components/Navbar";
import type { ConfigEntry, RunHistoryEntry } from "@/lib/types";

export default function AdminPage() {
  const { isConnected, currentState, resetStream } = useAgentStream();
  const [config, setConfig] = useState<Record<string, ConfigEntry>>({});
  const [history, setHistory] = useState<RunHistoryEntry[]>([]);
  const [chaosEnabled, setChaosEnabled] = useState(false);
  const [confirmReset, setConfirmReset] = useState(false);
  const [loading, setLoading] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  // Auto-dismiss error after 6 seconds
  useEffect(() => {
    if (!actionError) return;
    const timer = setTimeout(() => setActionError(null), 6000);
    return () => clearTimeout(timer);
  }, [actionError]);

  const loadData = useCallback(async () => {
    const [configRes, historyRes] = await Promise.all([
      getConfig(),
      getHistory(),
    ]);
    if (configRes.ok && configRes.data) {
      setConfig(
        (configRes.data as { config: Record<string, ConfigEntry> }).config
      );
    }
    if (historyRes.ok && historyRes.data) {
      setHistory(
        (historyRes.data as { runs: RunHistoryEntry[] }).runs
      );
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleReset = async () => {
    if (!confirmReset) {
      setConfirmReset(true);
      setTimeout(() => setConfirmReset(false), 3000);
      return;
    }
    setLoading("reset");
    setActionError(null);
    const res = await resetDemo();
    resetStream();
    setConfirmReset(false);
    setLoading(null);
    if (!res.ok) {
      setActionError(res.error ?? "Failed to reset demo");
    }
    await loadData();
  };

  const handleChaosToggle = async () => {
    setLoading("chaos");
    setActionError(null);
    const newState = !chaosEnabled;
    const res = await toggleChaos(newState);
    setLoading(null);
    if (!res.ok) {
      setActionError(res.error ?? `Failed to ${newState ? "enable" : "disable"} chaos mode`);
    } else {
      setChaosEnabled(newState);
    }
  };

  const handleManualTrigger = async () => {
    setLoading("trigger");
    setActionError(null);
    const res = await startAgent();
    setLoading(null);
    if (!res.ok) {
      setActionError(res.error ?? "Failed to start agent");
    }
  };

  return (
    <div className="min-h-screen">
      <Navbar isConnected={isConnected} />

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        <div className="mb-6">
          <h1 className="text-2xl font-bold text-white">Admin Panel</h1>
          <p className="text-sm text-gray-400 mt-1">
            Demo controls, configuration, and run history
          </p>
        </div>

        {/* Error banner */}
        {actionError && (
          <div className="mb-4 px-4 py-3 rounded-md bg-accent-red/10 border border-accent-red/30 flex items-center justify-between">
            <span className="text-sm text-accent-red">{actionError}</span>
            <button
              onClick={() => setActionError(null)}
              className="text-accent-red/60 hover:text-accent-red text-lg leading-none ml-4"
            >
              &times;
            </button>
          </div>
        )}

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {/* Controls */}
          <div className="bg-navy-800/50 border border-navy-700 rounded-lg p-5">
            <h3 className="text-sm font-semibold text-gray-300 mb-4 uppercase tracking-wider">
              Controls
            </h3>
            <div className="space-y-3">
              {/* Demo Reset */}
              <button
                onClick={handleReset}
                disabled={loading === "reset"}
                className={`w-full py-2.5 rounded-md font-medium text-sm transition-colors ${
                  confirmReset
                    ? "bg-accent-red text-white"
                    : "bg-accent-red/20 text-accent-red border border-accent-red/30 hover:bg-accent-red/30"
                } disabled:opacity-50`}
              >
                {loading === "reset"
                  ? "Resetting..."
                  : confirmReset
                  ? "Click again to confirm"
                  : "Reset Demo"}
              </button>

              {/* Chaos Toggle */}
              <button
                onClick={handleChaosToggle}
                disabled={loading === "chaos"}
                className={`w-full py-2.5 rounded-md font-medium text-sm transition-colors border ${
                  chaosEnabled
                    ? "bg-accent-amber/20 text-accent-amber border-accent-amber/30"
                    : "bg-navy-700 text-gray-300 border-navy-600 hover:bg-navy-600"
                } disabled:opacity-50`}
              >
                {loading === "chaos"
                  ? "Toggling..."
                  : chaosEnabled
                  ? "Disable Chaos Mode"
                  : "Enable Chaos Mode"}
              </button>

              {/* Manual Trigger */}
              <button
                onClick={handleManualTrigger}
                disabled={
                  loading === "trigger" || currentState !== "idle"
                }
                className="w-full py-2.5 rounded-md bg-accent-blue/20 text-accent-blue border border-accent-blue/30 hover:bg-accent-blue/30 font-medium text-sm transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {loading === "trigger"
                  ? "Starting..."
                  : "Manual Agent Trigger"}
              </button>
            </div>

            <div className="mt-4 text-xs text-gray-500">
              Agent state:{" "}
              <span className="text-gray-300 font-mono">
                {currentState}
              </span>
            </div>
          </div>

          {/* Environment Config */}
          <div className="bg-navy-800/50 border border-navy-700 rounded-lg p-5">
            <h3 className="text-sm font-semibold text-gray-300 mb-4 uppercase tracking-wider">
              Environment Config
            </h3>
            <div className="space-y-2">
              {Object.entries(config).map(([key, val]) => (
                <div
                  key={key}
                  className="flex items-center justify-between text-xs"
                >
                  <span className="text-gray-400 font-mono truncate mr-2">
                    {key}
                  </span>
                  <span
                    className={`flex-shrink-0 ${
                      val.configured
                        ? "text-accent-green"
                        : "text-accent-red"
                    }`}
                  >
                    {val.configured ? "\u2713" : "\u2717"}
                  </span>
                </div>
              ))}
              {Object.keys(config).length === 0 && (
                <p className="text-gray-500 text-xs">Loading config...</p>
              )}
            </div>
          </div>

          {/* Run History */}
          <div className="bg-navy-800/50 border border-navy-700 rounded-lg p-5 md:col-span-2 lg:col-span-1">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm font-semibold text-gray-300 uppercase tracking-wider">
                Run History
              </h3>
              <button
                onClick={loadData}
                className="text-xs text-gray-500 hover:text-gray-300"
              >
                Refresh
              </button>
            </div>
            <div className="space-y-2 max-h-64 overflow-y-auto scrollbar-thin">
              {history.length === 0 && (
                <p className="text-gray-500 text-xs">No runs yet</p>
              )}
              {history.map((run, i) => (
                <div
                  key={i}
                  className="bg-navy-900/50 rounded p-2 text-xs"
                >
                  <div className="flex items-center justify-between">
                    <span className="text-gray-400">
                      {new Date(run.timestamp).toLocaleString()}
                    </span>
                    <span
                      className={`font-mono ${
                        run.outcome === "completed"
                          ? "text-accent-green"
                          : "text-accent-red"
                      }`}
                    >
                      {run.outcome}
                    </span>
                  </div>
                  <div className="flex gap-4 mt-1 text-gray-500">
                    <span>{run.steps} steps</span>
                    <span>{(run.duration_ms / 1000).toFixed(1)}s</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
