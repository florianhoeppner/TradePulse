"use client";

import { motion } from "framer-motion";
import type { TimelineStepData } from "@/lib/types";
import TimelineStep from "./TimelineStep";

interface DualTrackProps {
  steps: TimelineStepData[];
}

export default function DualTrack({ steps }: DualTrackProps) {
  const shortTermSteps = steps.filter((s) => s.track === "short-term");
  const longTermSteps = steps.filter((s) => s.track !== "short-term");

  // If no short-term steps, render single timeline
  if (shortTermSteps.length === 0) {
    return (
      <div>
        {steps.map((step, i) => (
          <TimelineStep key={step.id} step={step} isLast={i === steps.length - 1} />
        ))}
      </div>
    );
  }

  const allShortTermDone = shortTermSteps.every((s) => s.status === "done");
  const isAwaitingApproval = longTermSteps.some(
    (s) => s.id === "awaiting_approval" && s.status === "active"
  );

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      {/* Left column: Short-term */}
      <div
        className={`rounded-lg border p-4 transition-colors ${
          allShortTermDone
            ? "bg-accent-green/5 border-accent-green/20"
            : "bg-navy-800/30 border-navy-700"
        }`}
      >
        <h3 className="text-xs font-semibold uppercase tracking-wider mb-3 text-accent-green">
          Immediate Stabilization
        </h3>
        <p className="text-xs text-gray-500 mb-4">
          Agent acts now
        </p>

        {shortTermSteps.map((step, i) => (
          <TimelineStep
            key={step.id}
            step={step}
            isLast={i === shortTermSteps.length - 1}
          />
        ))}

        {allShortTermDone && (
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            className="mt-4 px-3 py-2 rounded-md bg-accent-green/10 border border-accent-green/20 text-center"
          >
            <span className="text-sm font-semibold text-accent-green">
              Platform: STABLE
            </span>
          </motion.div>
        )}
      </div>

      {/* Right column: Long-term */}
      <div
        className={`rounded-lg border p-4 transition-colors ${
          isAwaitingApproval
            ? "bg-accent-amber/5 border-accent-amber/20"
            : "bg-navy-800/30 border-navy-700"
        }`}
      >
        <h3 className="text-xs font-semibold uppercase tracking-wider mb-3 text-accent-blue">
          Root Cause Resolution
        </h3>
        <p className="text-xs text-gray-500 mb-4">
          Human decides
        </p>

        {longTermSteps.length === 0 ? (
          <div className="text-center py-6 text-gray-500 text-sm">
            Waiting for stabilization to complete...
          </div>
        ) : (
          longTermSteps.map((step, i) => (
            <TimelineStep
              key={step.id}
              step={step}
              isLast={i === longTermSteps.length - 1}
            />
          ))
        )}
      </div>
    </div>
  );
}
