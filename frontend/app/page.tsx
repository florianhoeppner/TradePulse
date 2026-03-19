"use client";

import { useState, useEffect } from "react";
import { useAgentStreamContext } from "@/lib/AgentStreamContext";
import { useMarketData } from "@/lib/useMarketData";
import { startAgent, approveAction, rejectAction } from "@/lib/api";
import Navbar from "@/components/Navbar";
import TickerBar from "@/components/TickerBar";
import DualTrack from "@/components/DualTrack";
import ApprovalCard from "@/components/ApprovalCard";
import MetricsChart from "@/components/MetricsChart";
import AgentThinking from "@/components/AgentThinking";
import ImpactCounter from "@/components/ImpactCounter";
import RiskTable from "@/components/RiskTable";


export default function Dashboard() {
  const {
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
  } = useAgentStreamContext();

  const { stocks, isStale } = useMarketData();

  const [actionLoading, setActionLoading] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  // Auto-dismiss error after 6 seconds
  useEffect(() => {
    if (!actionError) return;
    const timer = setTimeout(() => setActionError(null), 6000);
    return () => clearTimeout(timer);
  }, [actionError]);

  const lastThinking = [...consoleLog]
    .reverse()
    .find((e) => e.type === "thinking");

  const handleStart = async () => {
    setActionLoading(true);
    setActionError(null);
    const res = await startAgent();
    setActionLoading(false);
    if (!res.ok) {
      setActionError(res.error ?? "Failed to start agent");
    }
  };

  const handleApprove = async () => {
    setActionError(null);
    const res = await approveAction();
    if (!res.ok) {
      setActionError(res.error ?? "Failed to approve fix");
    }
  };

  const handleReject = async () => {
    setActionError(null);
    const res = await rejectAction();
    if (!res.ok) {
      setActionError(res.error ?? "Failed to reject fix");
    }
  };

  const statusLabel: Record<string, { text: string; color: string }> = {
    idle: { text: "IDLE", color: "text-gray-400" },
    monitoring: { text: "MONITORING", color: "text-accent-blue" },
    anomaly_detected: { text: "ALERT", color: "text-accent-red" },
    cache_activated: { text: "STABILIZING", color: "text-accent-amber" },
    load_shedding_enabled: { text: "STABILIZING", color: "text-accent-amber" },
    backup_pricing_active: { text: "STABILIZING", color: "text-accent-amber" },
    incident_created: { text: "RESPONDING", color: "text-accent-amber" },
    investigating: { text: "INVESTIGATING", color: "text-accent-amber" },
    analyzing: { text: "ANALYZING", color: "text-accent-amber" },
    fix_generated: { text: "FIX READY", color: "text-accent-green" },
    ticket_created: { text: "TICKET CREATED", color: "text-accent-green" },
    awaiting_approval: { text: "AWAITING APPROVAL", color: "text-accent-amber" },
    approved: { text: "APPROVED", color: "text-accent-green" },
    rejected: { text: "REJECTED", color: "text-accent-red" },
    resolved: { text: "RESOLVED", color: "text-accent-green" },
    error: { text: "ERROR", color: "text-accent-red" },
  };

  const status = statusLabel[currentState] ?? statusLabel.idle;

  const isIncident =
    currentState !== "idle" &&
    currentState !== "monitoring" &&
    currentState !== "resolved";

  return (
    <div className="min-h-screen">
      <Navbar isConnected={isConnected} />
      <TickerBar stocks={stocks} isStale={isStale} />

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        {/* Header */}
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-2xl font-bold text-white">
              AI Incident Response
            </h1>
            <p className="text-sm text-gray-400 mt-1">
              Real-time agent monitoring and automated remediation for demo audience
            </p>
          </div>
          <div className="flex items-center gap-4">
            <span
              className={`text-sm font-semibold font-mono ${status.color}`}
            >
              {status.text}
            </span>
            {currentState === "idle" && (
              <button
                onClick={handleStart}
                disabled={actionLoading}
                className="px-4 py-2 rounded-md bg-accent-blue hover:bg-accent-blue/90 text-white font-medium text-sm transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {actionLoading ? "Starting..." : "Start Demo"}
              </button>
            )}
          </div>
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

        {/* Two column layout */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Left: Timeline */}
          <div className="lg:col-span-2 space-y-2">
            {/* Agent thinking */}
            <AgentThinking
              reasoning={
                (lastThinking?.data?.reasoning as string) ?? ""
              }
              isActive={
                currentState !== "idle" &&
                currentState !== "resolved" &&
                currentState !== "error"
              }
            />

            {/* Timeline steps */}
            {steps.length === 0 && currentState === "idle" && (
              <div className="bg-navy-800/30 border border-navy-700 rounded-lg p-8 text-center">
                <p className="text-gray-400">
                  Click &ldquo;Start Demo&rdquo; to begin the AI agent
                  workflow.
                </p>
                <p className="text-gray-500 text-sm mt-2">
                  The agent will monitor latency, detect anomalies, and
                  orchestrate incident response in real time.
                </p>
              </div>
            )}

            <DualTrack
              steps={steps}
              hasRiskAssessment={riskTable !== null}
              riskNeutralized={riskNeutralized}
            />

            {/* Risk Table */}
            {riskTable && (
              <RiskTable
                findings={riskTable.findings}
                totalLow={riskTable.total_low}
                totalHigh={riskTable.total_high}
              />
            )}

            {/* Approval Card */}
            {currentState === "awaiting_approval" && (
              <ApprovalCard
                jiraUrl={jiraUrl}
                originalCode={originalCode}
                optimizedCode={optimizedCode}
                onApprove={handleApprove}
                onReject={handleReject}
                totalRiskLow={riskTable?.total_low}
                totalRiskHigh={riskTable?.total_high}
              />
            )}
          </div>

          {/* Right: Market Data & Metrics */}
          <div className="space-y-4">
            {/* Impact counter — only during incidents */}
            <ImpactCounter
              metrics={metrics}
              isIncident={isIncident}
            />

            {/* p99 Latency Chart */}
            <MetricsChart dataPoints={metrics} />

            {/* Status card */}
            <div className="bg-navy-800/50 border border-navy-700 rounded-lg p-4">
              <h4 className="text-sm font-medium text-gray-400 mb-3">
                Agent Status
              </h4>
              <div className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-gray-500">State</span>
                  <span className={`font-mono ${status.color}`}>
                    {currentState}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">Steps</span>
                  <span className="text-gray-300">{steps.length}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">Events</span>
                  <span className="text-gray-300">{consoleLog.length}</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
