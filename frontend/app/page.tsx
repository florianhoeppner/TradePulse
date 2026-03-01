"use client";

import { useAgentStream } from "@/lib/useAgentStream";
import { startAgent, approveAction, rejectAction } from "@/lib/api";
import Navbar from "@/components/Navbar";
import TimelineStep from "@/components/TimelineStep";
import ApprovalCard from "@/components/ApprovalCard";
import MetricsChart from "@/components/MetricsChart";
import AgentThinking from "@/components/AgentThinking";

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
  } = useAgentStream();

  const lastThinking = [...consoleLog]
    .reverse()
    .find((e) => e.type === "thinking");

  const handleStart = async () => {
    await startAgent();
  };

  const handleApprove = async () => {
    await approveAction();
  };

  const handleReject = async () => {
    await rejectAction();
  };

  const statusLabel: Record<string, { text: string; color: string }> = {
    idle: { text: "IDLE", color: "text-gray-400" },
    monitoring: { text: "MONITORING", color: "text-accent-blue" },
    anomaly_detected: { text: "ALERT", color: "text-accent-red" },
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

  return (
    <div className="min-h-screen">
      <Navbar isConnected={isConnected} />

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        {/* Header */}
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-2xl font-bold text-white">
              AI Incident Response
            </h1>
            <p className="text-sm text-gray-400 mt-1">
              Real-time agent monitoring and automated remediation
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
                className="px-4 py-2 rounded-md bg-accent-blue hover:bg-accent-blue/90 text-white font-medium text-sm transition-colors"
              >
                Start Demo
              </button>
            )}
          </div>
        </div>

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

            {steps.map((step, i) => (
              <TimelineStep
                key={step.id}
                step={step}
                isLast={i === steps.length - 1}
              />
            ))}

            {/* Approval Card */}
            {currentState === "awaiting_approval" && (
              <ApprovalCard
                jiraUrl={jiraUrl}
                originalCode={originalCode}
                optimizedCode={optimizedCode}
                onApprove={handleApprove}
                onReject={handleReject}
              />
            )}
          </div>

          {/* Right: Metrics */}
          <div className="space-y-4">
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

            {/* Watched symbols */}
            <div className="bg-navy-800/50 border border-navy-700 rounded-lg p-4">
              <h4 className="text-sm font-medium text-gray-400 mb-3">
                Monitored Symbols
              </h4>
              <div className="flex flex-wrap gap-2">
                {["AAPL", "MSFT", "GOOGL", "JPM", "GS"].map((sym) => (
                  <span
                    key={sym}
                    className="text-xs font-mono px-2 py-1 bg-navy-700 rounded text-gray-300"
                  >
                    {sym}
                  </span>
                ))}
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
