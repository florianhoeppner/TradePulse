"use client";

import { useState } from "react";
import { motion } from "framer-motion";

interface ApprovalCardProps {
  jiraUrl: string;
  originalCode: string;
  optimizedCode: string;
  onApprove: () => Promise<void>;
  onReject: () => Promise<void>;
}

export default function ApprovalCard({
  jiraUrl,
  originalCode,
  optimizedCode,
  onApprove,
  onReject,
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
          {showDiff ? "Hide Code Diff" : "View Code Diff"}
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
