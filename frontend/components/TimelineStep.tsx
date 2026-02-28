"use client";

import { motion } from "framer-motion";
import type { TimelineStepData } from "@/lib/types";

const statusConfig = {
  pending: {
    dotClass: "bg-navy-600",
    lineClass: "bg-navy-700",
    textClass: "text-gray-500",
  },
  active: {
    dotClass: "bg-accent-blue animate-pulse",
    lineClass: "bg-accent-blue/30",
    textClass: "text-white",
  },
  done: {
    dotClass: "bg-accent-green",
    lineClass: "bg-accent-green/30",
    textClass: "text-gray-300",
  },
  error: {
    dotClass: "bg-accent-red",
    lineClass: "bg-accent-red/30",
    textClass: "text-accent-red",
  },
};

const statusIcons: Record<string, string> = {
  pending: "",
  active: "...",
  done: "\u2713",
  error: "\u2717",
};

interface TimelineStepProps {
  step: TimelineStepData;
  isLast: boolean;
}

export default function TimelineStep({ step, isLast }: TimelineStepProps) {
  const config = statusConfig[step.status];

  return (
    <motion.div
      initial={{ opacity: 0, x: -20 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.3 }}
      className="flex gap-4"
    >
      {/* Timeline dot and line */}
      <div className="flex flex-col items-center">
        <div
          className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold ${config.dotClass} ${
            step.status === "active" ? "shadow-lg shadow-accent-blue/30" : ""
          }`}
        >
          {statusIcons[step.status]}
        </div>
        {!isLast && (
          <div className={`w-0.5 flex-1 min-h-[2rem] ${config.lineClass}`} />
        )}
      </div>

      {/* Content */}
      <div className="pb-6 flex-1">
        <div className="flex items-center gap-3">
          <h3 className={`font-semibold ${config.textClass}`}>{step.title}</h3>
          {step.status === "active" && (
            <span className="text-xs px-2 py-0.5 rounded-full bg-accent-blue/20 text-accent-blue border border-accent-blue/30">
              LIVE
            </span>
          )}
          {step.status === "done" && (
            <span className="text-xs px-2 py-0.5 rounded-full bg-accent-green/10 text-accent-green">
              DONE
            </span>
          )}
          {step.status === "error" && (
            <span className="text-xs px-2 py-0.5 rounded-full bg-accent-red/10 text-accent-red">
              ERROR
            </span>
          )}
        </div>
        {step.subtitle && (
          <p className="text-sm text-gray-400 mt-0.5">{step.subtitle}</p>
        )}
        {step.link && (
          <a
            href={step.link}
            target="_blank"
            rel="noopener noreferrer"
            className="text-xs text-accent-blue hover:underline mt-1 inline-block"
          >
            {step.link}
          </a>
        )}
      </div>
    </motion.div>
  );
}
