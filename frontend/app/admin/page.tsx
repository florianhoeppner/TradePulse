"use client";

import { useState, useEffect, useCallback } from "react";
import { useAgentStreamContext } from "@/lib/AgentStreamContext";
import {
  startAgent,
  resetDemo,
  toggleChaos,
  getChaosStatus,
  getConfig,
  getHistory,
  fetchPlatformStatus,
  toggleCache,
  toggleLoadShedding,
  switchPricingSource,
} from "@/lib/api";
import Navbar from "@/components/Navbar";
import type { ConfigEntry, RunHistoryEntry, PlatformStatus } from "@/lib/types";

export default function AdminPage() {
  const { isConnected, currentState, resetStream } = useAgentStreamContext();
  const [config, setConfig] = useState<Record<string, ConfigEntry>>({});
  const [history, setHistory] = useState<RunHistoryEntry[]>([]);
  const [chaosEnabled, setChaosEnabled] = useState(false);
  const [platformStatus, setPlatformStatus] = useState<PlatformStatus | null>(null);
  const [confirmReset, setConfirmReset] = useState(false);
  const [loading, setLoading] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  // Auto-dismiss error after 6 seconds
  useEffect(() => {
    if (!actionError) return;
    const timer = setTimeout(() => setActionError(null), 6000);
    return () => clearTimeout(timer);
  }, [actionError]);

  const [configError, setConfigError] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    const [configRes, historyRes, chaosRes, platformRes] = await Promise.all([
      getConfig(),
      getHistory(),
      getChaosStatus(),
      fetchPlatformStatus(),
    ]);
    if (chaosRes.ok && chaosRes.data) {
      setChaosEnabled((chaosRes.data as { chaos_mode: boolean }).chaos_mode);
    }
    if (configRes.ok && configRes.data) {
      setConfig(
        (configRes.data as { config: Record<string, ConfigEntry> }).config
      );
      setConfigError(null);
    } else if (configRes.error) {
      setConfigError(configRes.error);
    }
    if (historyRes.ok && historyRes.data) {
      setHistory(
        (historyRes.data as { runs: RunHistoryEntry[] }).runs
      );
    }
    if (platformRes.ok && platformRes.data) {
      setPlatformStatus(platformRes.data as PlatformStatus);
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

  const handleCacheToggle = async () => {
    setLoading("cache");
    setActionError(null);
    const newState = !(platformStatus?.cache.active ?? false);
    const res = await toggleCache(newState);
    setLoading(null);
    if (!res.ok) {
      setActionError(res.error ?? "Failed to toggle cache");
    }
    await loadData();
  };

  const handleLoadSheddingToggle = async () => {
    setLoading("loadshed");
    setActionError(null);
    const newState = !(platformStatus?.load_shedding.active ?? false);
    const res = await toggleLoadShedding(newState);
    setLoading(null);
    if (!res.ok) {
      setActionError(res.error ?? "Failed to toggle load shedding");
    }
    await loadData();
  };

  const handlePricingSourceToggle = async () => {
    setLoading("pricing");
    setActionError(null);
    const switchToBackup = platformStatus?.pricing_source !== "backup";
    const res = await switchPricingSource(switchToBackup);
    setLoading(null);
    if (!res.ok) {
      setActionError(res.error ?? "Failed to switch pricing source");
    }
    await loadData();
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
          {/* Platform State */}
          <div className="bg-navy-800/50 border border-navy-700 rounded-lg p-5 md:col-span-2 lg:col-span-3">
            <h3 className="text-sm font-semibold text-gray-300 mb-4 uppercase tracking-wider">
              Platform State
            </h3>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
              {/* Price Cache */}
              <div className="flex items-center justify-between bg-navy-900/50 rounded p-3">
                <div>
                  <span className="text-xs text-gray-400">Price Cache</span>
                  <div className="flex items-center gap-2 mt-1">
                    <span
                      className={`text-xs font-mono px-1.5 py-0.5 rounded ${
                        platformStatus?.cache.active
                          ? "text-accent-green bg-accent-green/10"
                          : "text-gray-500 bg-navy-700"
                      }`}
                    >
                      {platformStatus?.cache.active ? "ACTIVE" : "OFF"}
                    </span>
                    {platformStatus?.cache.active && (
                      <span className="text-xs text-gray-500">
                        {Math.round(platformStatus.cache.age_seconds)}s
                      </span>
                    )}
                  </div>
                </div>
                <button
                  onClick={handleCacheToggle}
                  disabled={loading === "cache"}
                  className="text-xs px-2 py-1 rounded border border-navy-600 text-gray-400 hover:text-white hover:border-navy-500 disabled:opacity-50"
                >
                  {loading === "cache"
                    ? "..."
                    : platformStatus?.cache.active
                    ? "Deactivate"
                    : "Activate"}
                </button>
              </div>

              {/* Load Shedding */}
              <div className="flex items-center justify-between bg-navy-900/50 rounded p-3">
                <div>
                  <span className="text-xs text-gray-400">Load Shedding</span>
                  <div className="flex items-center gap-2 mt-1">
                    <span
                      className={`text-xs font-mono px-1.5 py-0.5 rounded ${
                        platformStatus?.load_shedding.active
                          ? "text-accent-green bg-accent-green/10"
                          : "text-gray-500 bg-navy-700"
                      }`}
                    >
                      {platformStatus?.load_shedding.active ? "ACTIVE" : "OFF"}
                    </span>
                    {platformStatus?.load_shedding.active && (
                      <span className="text-xs text-gray-500">
                        shed: {platformStatus.load_shedding.shed_count}
                      </span>
                    )}
                  </div>
                </div>
                <button
                  onClick={handleLoadSheddingToggle}
                  disabled={loading === "loadshed"}
                  className="text-xs px-2 py-1 rounded border border-navy-600 text-gray-400 hover:text-white hover:border-navy-500 disabled:opacity-50"
                >
                  {loading === "loadshed"
                    ? "..."
                    : platformStatus?.load_shedding.active
                    ? "Deactivate"
                    : "Activate"}
                </button>
              </div>

              {/* Pricing Source */}
              <div className="flex items-center justify-between bg-navy-900/50 rounded p-3">
                <div>
                  <span className="text-xs text-gray-400">Pricing Source</span>
                  <div className="mt-1">
                    <span
                      className={`text-xs font-mono px-1.5 py-0.5 rounded ${
                        platformStatus?.pricing_source === "backup"
                          ? "text-accent-amber bg-accent-amber/10"
                          : "text-gray-500 bg-navy-700"
                      }`}
                    >
                      {(platformStatus?.pricing_source ?? "primary").toUpperCase()}
                    </span>
                  </div>
                </div>
                <button
                  onClick={handlePricingSourceToggle}
                  disabled={loading === "pricing"}
                  className="text-xs px-2 py-1 rounded border border-navy-600 text-gray-400 hover:text-white hover:border-navy-500 disabled:opacity-50"
                >
                  {loading === "pricing"
                    ? "..."
                    : platformStatus?.pricing_source === "backup"
                    ? "Primary"
                    : "Backup"}
                </button>
              </div>

              {/* Chaos Mode (moved here for grouping) */}
              <div className="flex items-center justify-between bg-navy-900/50 rounded p-3">
                <div>
                  <span className="text-xs text-gray-400">Chaos Mode</span>
                  <div className="mt-1">
                    <span
                      className={`text-xs font-mono px-1.5 py-0.5 rounded ${
                        chaosEnabled
                          ? "text-accent-red bg-accent-red/10"
                          : "text-gray-500 bg-navy-700"
                      }`}
                    >
                      {chaosEnabled ? "ON" : "OFF"}
                    </span>
                  </div>
                </div>
                <button
                  onClick={handleChaosToggle}
                  disabled={loading === "chaos"}
                  className="text-xs px-2 py-1 rounded border border-navy-600 text-gray-400 hover:text-white hover:border-navy-500 disabled:opacity-50"
                >
                  {loading === "chaos"
                    ? "..."
                    : chaosEnabled
                    ? "Disable"
                    : "Enable"}
                </button>
              </div>
            </div>
          </div>

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
                <p className={`text-xs ${configError ? "text-accent-red" : "text-gray-500"}`}>
                  {configError ?? "Loading config..."}
                </p>
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
