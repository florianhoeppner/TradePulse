"use client";

import { motion } from "framer-motion";
import type { RiskFinding } from "@/lib/types";

interface RiskTableProps {
  findings: RiskFinding[];
  totalLow: number;
  totalHigh: number;
}

const usdCompact = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  notation: "compact",
  maximumFractionDigits: 0,
});

const usdFull = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  maximumFractionDigits: 0,
});

function formatRange(low: number, high: number): string {
  if (low === 0 && high === 0) return usdCompact.format(0);
  if (low === high) return usdCompact.format(low);
  return `${usdCompact.format(low)} – ${usdCompact.format(high)}`;
}

const FINDING_LABELS: Record<string, string> = {
  latency_spike: "Latency spike",
  pricing_source_degradation: "Pricing degradation",
  queue_depth_buildup: "Queue depth buildup",
  cache_miss_rate: "Cache miss rate",
};

function getSlaStatus(finding: RiskFinding): {
  label: string;
  icon: string;
  borderClass: string;
  textClass: string;
} {
  if (finding.sla_relevant) {
    return {
      label: "Yes",
      icon: "\u2705",
      borderClass: "border-l-accent-blue",
      textClass: "text-white",
    };
  }
  if (finding.risk_usd_high > 0) {
    return {
      label: "Marginal",
      icon: "\u26a0\ufe0f",
      borderClass: "border-l-accent-amber",
      textClass: "text-gray-400",
    };
  }
  return {
    label: "No",
    icon: "\u274c",
    borderClass: "border-l-transparent",
    textClass: "text-gray-500",
  };
}

const containerVariants = {
  hidden: {},
  visible: {
    transition: {
      staggerChildren: 0.15,
    },
  },
};

const rowVariants = {
  hidden: { opacity: 0, x: -12 },
  visible: { opacity: 1, x: 0 },
};

export default function RiskTable({ findings, totalLow, totalHigh }: RiskTableProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      className="bg-navy-800/80 border border-navy-700 rounded-lg p-5"
    >
      <h3 className="text-xs font-semibold uppercase tracking-wider text-gray-300 mb-4">
        Economic Risk Assessment
      </h3>

      {/* Desktop table */}
      <div className="hidden md:block">
        <div className="grid grid-cols-[1fr_auto_auto] gap-x-6 gap-y-0 text-xs text-gray-500 mb-2 px-3">
          <span>Finding</span>
          <span className="text-right">Risk Range</span>
          <span className="text-right">SLA Impact</span>
        </div>
        <div className="border-t border-navy-700 mb-2" />

        <motion.div variants={containerVariants} initial="hidden" animate="visible">
          {findings.map((finding) => {
            const sla = getSlaStatus(finding);
            return (
              <motion.div
                key={finding.finding_name}
                variants={rowVariants}
                className={`grid grid-cols-[1fr_auto_auto] gap-x-6 items-center px-3 py-2 border-l-2 ${sla.borderClass} ${sla.textClass}`}
              >
                <span className="flex items-center gap-2">
                  <span className={`w-1.5 h-1.5 rounded-full ${finding.sla_relevant ? "bg-accent-blue" : finding.risk_usd_high > 0 ? "bg-accent-amber" : "bg-gray-600"}`} />
                  {FINDING_LABELS[finding.finding_name] ?? finding.finding_name}
                </span>
                <span className="text-right font-mono text-sm">
                  {formatRange(finding.risk_usd_low, finding.risk_usd_high)}
                </span>
                <span className="text-right whitespace-nowrap">
                  {sla.icon} {sla.label}
                </span>
              </motion.div>
            );
          })}
        </motion.div>

        <div className="border-t border-navy-700 mt-2 pt-3 px-3">
          <div className="grid grid-cols-[1fr_auto_auto] gap-x-6 items-center">
            <span className="text-sm font-semibold text-white">Total Actionable Risk</span>
            <span className="text-right font-mono text-lg font-bold text-white">
              {formatRange(totalLow, totalHigh)}
            </span>
            <span />
          </div>
        </div>
      </div>

      {/* Mobile cards */}
      <motion.div
        variants={containerVariants}
        initial="hidden"
        animate="visible"
        className="md:hidden space-y-2"
      >
        {findings.map((finding) => {
          const sla = getSlaStatus(finding);
          return (
            <motion.div
              key={finding.finding_name}
              variants={rowVariants}
              className={`rounded-md bg-navy-900/50 p-3 border-l-2 ${sla.borderClass}`}
            >
              <div className={`text-sm font-medium ${sla.textClass}`}>
                {FINDING_LABELS[finding.finding_name] ?? finding.finding_name}
              </div>
              <div className="flex justify-between items-center mt-1">
                <span className={`font-mono text-sm ${sla.textClass}`}>
                  {formatRange(finding.risk_usd_low, finding.risk_usd_high)}
                </span>
                <span className="text-xs">
                  {sla.icon} {sla.label}
                </span>
              </div>
            </motion.div>
          );
        })}
        <div className="border-t border-navy-700 pt-3">
          <div className="flex justify-between items-center">
            <span className="text-sm font-semibold text-white">Total Actionable Risk</span>
            <span className="font-mono text-lg font-bold text-white">
              {formatRange(totalLow, totalHigh)}
            </span>
          </div>
        </div>
      </motion.div>
    </motion.div>
  );
}
