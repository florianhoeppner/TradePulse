"use client";

import { useState } from "react";
import { motion } from "framer-motion";

interface ApprovalCardProps {
  jiraUrl: string;
  originalCode: string;
  optimizedCode: string;
  onApprove: () => Promise<void>;
  onReject: () => Promise<void>;
  totalRiskLow?: number;
  totalRiskHigh?: number;
}

const usdFull = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  maximumFractionDigits: 0,
});

const usdCompact = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  notation: "compact",
  maximumFractionDigits: 1,
});

export default function ApprovalCard({
  jiraUrl,
  originalCode,
  optimizedCode,
  onApprove,
  onReject,
  totalRiskLow,
  totalRiskHigh,
}: ApprovalCardProps) {
  const [showDiff, setShowDiff] = useState(false);
  const [loading, setLoading] = useState<"approve" | "reject" | null>(null);

  const handleApprove = async () => {
    setLoading("approve");
    await onApprove();
    setLoading(null);
  };

  const handleReject = async () => {
    setLoading("reject");
    await onReject();
    setLoading(null);
  };

  const hasRiskData = totalRiskLow != null && totalRiskHigh != null && totalRiskHigh > 0;
  const projectedLow = hasRiskData ? totalRiskLow! * 2 * 12 : 0;
  const projectedHigh = hasRiskData ? totalRiskHigh! * 3 * 12 : 0;

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="border border-accent-blue/40 rounded-lg bg-navy-800/80 p-5 animate-glow"
    >
      <h3 className="text-lg font-semibold text-white mb-2">
        Review the Proposed Fix
      </h3>
      <p className="text-sm text-gray-400 mb-4">
        The AI agent has identified missing resiliency patterns and generated a
        fix. Review and approve to resolve the incident.
      </p>

      {/* Business Case */}
      {hasRiskData && (
        <div className="mb-5 rounded-lg bg-navy-900/70 border border-navy-600 p-4">
          <h4 className="text-xs font-semibold uppercase tracking-wider text-gray-300 mb-3">
            Business Case for This Fix
          </h4>
          <div className="space-y-2">
            <div className="flex justify-between items-center">
              <span className="text-sm text-gray-400">Risk per incident (unmitigated)</span>
              <span className="text-sm font-semibold text-white font-mono">
                {usdCompact.format(totalRiskLow!)} – {usdCompact.format(totalRiskHigh!)}
              </span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-sm text-gray-400">Est. recurrence without fix</span>
              <span className="text-sm font-semibold text-accent-amber font-mono">
                2–3x / month
              </span>
            </div>
            <div className="border-t border-navy-600 pt-2 mt-2">
              <div className="flex justify-between items-center">
                <span className="text-sm text-gray-400">Projected 12-month exposure</span>
                <span className="text-2xl font-bold text-white font-mono">
                  {usdCompact.format(projectedLow)} – {usdCompact.format(projectedHigh)}
                </span>
              </div>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-sm text-gray-400">Cost of this fix</span>
              <span className="text-sm font-semibold text-accent-green font-mono">
                1 engineer-day
              </span>
            </div>
          </div>
        </div>
      )}

      {jiraUrl && (
        <a
          href={jiraUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="text-sm text-accent-blue hover:underline mb-4 inline-block"
        >
          View Jira Ticket &rarr;
        </a>
      )}

      {/* Toggle diff view */}
      <div className="mb-4">
        <button
          onClick={() => setShowDiff(!showDiff)}
          className="text-sm px-3 py-1 rounded border border-navy-600 text-gray-300 hover:bg-navy-700 transition-colors"
        >
          {showDiff ? "Hide Technical Diff" : "View Technical Diff"}
        </button>
      </div>

      {showDiff && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-3 mb-4 max-h-80 overflow-auto scrollbar-thin">
          <div>
            <div className="text-xs text-accent-red mb-1 font-medium">
              Original (Fragile)
            </div>
            <pre className="bg-navy-950 rounded p-3 text-xs overflow-x-auto text-gray-300 border border-navy-700">
              {originalCode || "// Source code not yet retrieved"}
            </pre>
          </div>
          <div>
            <div className="text-xs text-accent-green mb-1 font-medium">
              Optimized (Resilient)
            </div>
            <pre className="bg-navy-950 rounded p-3 text-xs overflow-x-auto text-gray-300 border border-navy-700">
              {optimizedCode || "// Optimized code not yet generated"}
            </pre>
          </div>
        </div>
      )}

      {/* Approval buttons */}
      <div className="flex gap-3">
        <button
          onClick={handleApprove}
          disabled={loading !== null}
          className="flex-1 py-2.5 rounded-md bg-accent-green hover:bg-accent-green/90 text-white font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {loading === "approve" ? "Approving..." : "Approve"}
        </button>
        <button
          onClick={handleReject}
          disabled={loading !== null}
          className="flex-1 py-2.5 rounded-md bg-accent-red/20 hover:bg-accent-red/30 text-accent-red border border-accent-red/30 font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {loading === "reject" ? "Rejecting..." : "Reject"}
        </button>
      </div>
    </motion.div>
  );
}
