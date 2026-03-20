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
  getEconomicProfile,
  saveEconomicProfile,
  fetchMetricsSummary,
} from "@/lib/api";
import Navbar from "@/components/Navbar";
import type { ConfigEntry, RunHistoryEntry, PlatformStatus, EconomicProfile } from "@/lib/types";

const usdDisplay = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  maximumFractionDigits: 0,
});

export default function AdminPage() {
  const { isConnected, currentState, resetStream } = useAgentStreamContext();
  const [config, setConfig] = useState<Record<string, ConfigEntry>>({});
  const [history, setHistory] = useState<RunHistoryEntry[]>([]);
  const [chaosEnabled, setChaosEnabled] = useState(false);
  const [platformStatus, setPlatformStatus] = useState<PlatformStatus | null>(null);
  const [confirmReset, setConfirmReset] = useState(false);
  const [loading, setLoading] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  // Economic profile state
  const [ecoProfile, setEcoProfile] = useState<EconomicProfile>({
    avg_order_value_usd: 8400,
    orders_per_minute: 12,
    sla_breach_penalty_usd: 250000,
    downtime_cost_per_hour_usd: 6048000,
    currency: "USD",
  });
  const [ecoSaved, setEcoSaved] = useState(false);

  // Chaos warmup state
  const [chaosP99, setChaosP99] = useState<number | null>(null);
  const [chaosSamples, setChaosSamples] = useState<number | null>(null);

  // Poll metrics summary when chaos is enabled to show warmup status
  useEffect(() => {
    if (!chaosEnabled) {
      setChaosP99(null);
      setChaosSamples(null);
      return;
    }
    let cancelled = false;
    const poll = async () => {
      const res = await fetchMetricsSummary();
      if (!cancelled && res.ok && res.data) {
        const d = res.data as { p99_latency_ms: number; total_orders: number };
        setChaosP99(d.p99_latency_ms ?? 0);
        setChaosSamples(d.total_orders ?? 0);
      }
    };
    poll();
    const interval = setInterval(poll, 5000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [chaosEnabled]);

  // Auto-dismiss error after 6 seconds
  useEffect(() => {
    if (!actionError) return;
    const timer = setTimeout(() => setActionError(null), 6000);
    return () => clearTimeout(timer);
  }, [actionError]);

  const [configError, setConfigError] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    const [configRes, historyRes, chaosRes, platformRes, ecoRes] = await Promise.all([
      getConfig(),
      getHistory(),
      getChaosStatus(),
      fetchPlatformStatus(),
      getEconomicProfile(),
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
    if (ecoRes.ok && ecoRes.data) {
      setEcoProfile(ecoRes.data as EconomicProfile);
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
    const { toggleCache } = await import("@/lib/api");
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
    const { toggleLoadShedding } = await import("@/lib/api");
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
    const { switchPricingSource } = await import("@/lib/api");
    const switchToBackup = platformStatus?.pricing_source !== "backup";
    const res = await switchPricingSource(switchToBackup);
    setLoading(null);
    if (!res.ok) {
      setActionError(res.error ?? "Failed to switch pricing source");
    }
    await loadData();
  };

  const handleSaveProfile = async () => {
    setLoading("eco");
    setActionError(null);
    const res = await saveEconomicProfile(ecoProfile);
    setLoading(null);
    if (!res.ok) {
      setActionError(res.error ?? "Failed to save economic profile");
    } else {
      setEcoSaved(true);
      setTimeout(() => setEcoSaved(false), 2000);
    }
  };

  const revenueAtRisk = ecoProfile.avg_order_value_usd * ecoProfile.orders_per_minute;

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
          {/* Economic Profile — above Platform State */}
          <div className="bg-navy-800/50 border border-navy-700 rounded-lg p-5 md:col-span-2 lg:col-span-3">
            <h3 className="text-sm font-semibold text-gray-300 mb-1 uppercase tracking-wider">
              Economic Profile
            </h3>
            <p className="text-xs text-gray-500 mb-4">
              These numbers are used by the agent to quantify risk during the demo. Set them once before presenting.
            </p>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              <div>
                <label className="block text-xs text-gray-400 mb-1">Avg order value</label>
                <div className="relative">
                  <span className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500 text-sm">$</span>
                  <input
                    type="number"
                    value={ecoProfile.avg_order_value_usd}
                    onChange={(e) =>
                      setEcoProfile((p) => ({ ...p, avg_order_value_usd: Number(e.target.value) || 0 }))
                    }
                    className="w-full pl-7 pr-3 py-2 rounded-md bg-navy-900/50 border border-navy-600 text-white text-sm font-mono focus:outline-none focus:border-accent-blue"
                  />
                </div>
              </div>
              <div>
                <label className="block text-xs text-gray-400 mb-1">Orders per minute</label>
                <input
                  type="number"
                  value={ecoProfile.orders_per_minute}
                  onChange={(e) =>
                    setEcoProfile((p) => ({ ...p, orders_per_minute: Number(e.target.value) || 0 }))
                  }
                  className="w-full px-3 py-2 rounded-md bg-navy-900/50 border border-navy-600 text-white text-sm font-mono focus:outline-none focus:border-accent-blue"
                />
              </div>
              <div>
                <label className="block text-xs text-gray-400 mb-1">SLA breach penalty</label>
                <div className="relative">
                  <span className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500 text-sm">$</span>
                  <input
                    type="number"
                    value={ecoProfile.sla_breach_penalty_usd}
                    onChange={(e) =>
                      setEcoProfile((p) => ({ ...p, sla_breach_penalty_usd: Number(e.target.value) || 0 }))
                    }
                    className="w-full pl-7 pr-3 py-2 rounded-md bg-navy-900/50 border border-navy-600 text-white text-sm font-mono focus:outline-none focus:border-accent-blue"
                  />
                </div>
              </div>
              <div>
                <label className="block text-xs text-gray-400 mb-1">Downtime cost/hour</label>
                <div className="relative">
                  <span className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500 text-sm">$</span>
                  <input
                    type="number"
                    value={ecoProfile.downtime_cost_per_hour_usd}
                    onChange={(e) =>
                      setEcoProfile((p) => ({ ...p, downtime_cost_per_hour_usd: Number(e.target.value) || 0 }))
                    }
                    className="w-full pl-7 pr-3 py-2 rounded-md bg-navy-900/50 border border-navy-600 text-white text-sm font-mono focus:outline-none focus:border-accent-blue"
                  />
                </div>
              </div>
            </div>
            <div className="flex items-center justify-between mt-4">
              <div className="text-sm text-gray-400">
                Revenue at risk/min:{" "}
                <span className="text-white font-semibold font-mono">
                  {usdDisplay.format(revenueAtRisk)}
                </span>
              </div>
              <button
                onClick={handleSaveProfile}
                disabled={loading === "eco"}
                className="px-4 py-2 rounded-md bg-accent-blue/20 text-accent-blue border border-accent-blue/30 hover:bg-accent-blue/30 font-medium text-sm transition-colors disabled:opacity-50"
              >
                {loading === "eco" ? "Saving..." : ecoSaved ? "Saved \u2713" : "Save Profile"}
              </button>
            </div>
          </div>

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
              <div className="bg-navy-900/50 rounded p-3">
                <div className="flex items-center justify-between">
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
                {chaosEnabled && chaosP99 !== null && (
                  <div className="mt-2 pt-2 border-t border-navy-700">
                    {chaosP99 < 2000 ? (
                      <div className="animate-pulse">
                        <span className="text-xs text-accent-amber font-medium">
                          Warming up...
                        </span>
                        <span className="text-xs text-gray-400 ml-1 font-mono">
                          p99: {Math.round(chaosP99)}ms (need &gt;2000ms)
                        </span>
                      </div>
                    ) : (
                      <div>
                        <span className="text-xs text-accent-green font-medium">
                          Ready
                        </span>
                        <span className="text-xs text-gray-400 ml-1 font-mono">
                          p99: {Math.round(chaosP99)}ms
                        </span>
                      </div>
                    )}
                  </div>
                )}
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
